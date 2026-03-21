# ruff: noqa: E501
import importlib
import os
import sys
from types import ModuleType
from typing import Any, Callable
from unittest.mock import Mock


class DeepMockConfig:
    """Global configuration for deep_mock defaults. Set these in conftest.py."""

    base_dir: str = "."
    allowed_dirs: list[str] | None = None

    @classmethod
    def configure(
        cls,
        base_dir: str | None = None,
        allowed_dirs: list[str] | None = None,
    ):
        """Configure default values for deep_mock."""
        if base_dir is not None:
            cls.base_dir = base_dir
        if allowed_dirs is not None:
            cls.allowed_dirs = allowed_dirs

    @classmethod
    def reset(cls):
        """Reset configuration to defaults."""
        cls.base_dir = "."
        cls.allowed_dirs = None


def _reload_module_in_place(module_name: str) -> None:
    """
    Reload a module and update the old module object in-place.

    This ensures existing references to the module see the updated attributes,
    unlike importlib.reload() which creates a new module object.
    """
    if module_name not in sys.modules:
        return

    old_module = sys.modules[module_name]

    # Reload creates a new module object
    new_module = importlib.reload(old_module)

    # If reload returned a different object, copy attributes to old module
    if new_module is not old_module:
        # Clear old attributes (except special ones)
        old_attrs = list(old_module.__dict__.keys())
        for attr in old_attrs:
            if not attr.startswith('__'):
                try:
                    delattr(old_module, attr)
                except (AttributeError, TypeError):
                    pass

        # Copy new attributes to old module
        for attr, value in new_module.__dict__.items():
            if not attr.startswith('__'):
                try:
                    setattr(old_module, attr, value)
                except (AttributeError, TypeError):
                    pass

        # Restore old module in sys.modules (reload might have replaced it)
        sys.modules[module_name] = old_module


# As the name says, just an empty decorator to be used as a fake
def fake_useless_decorator(func):
    def inner(*args, **kwargs):
        return func(*args, **kwargs)

    return inner


# Utility method to help us filter out calls in a mock
def find_calls_in_mock_calls(
    mock,
    call_name: str,
    call_filter: Callable[[tuple, dict[str, Any]], bool] | None = None,
):
    res = []
    for mock_call_name, mock_call_args, mock_call_kwargs in mock.mock_calls:
        # Check name
        if call_name != mock_call_name:
            continue

        # Check filter
        if call_filter is not None and not call_filter(
            mock_call_args, mock_call_kwargs
        ):
            continue

        res.append((mock_call_name, mock_call_args, mock_call_kwargs))

    return res


# Finds all loaded modules that have imported a specific attribute from a module
def _find_modules_with_imported_attr(
    source_module_name: str,
    attr_name: str,
) -> list[str]:
    """
    Find all loaded modules that have imported `attr_name` from `source_module_name`.

    This handles both absolute and relative imports by checking if the attribute
    in the importing module points to the same object as in the source module.
    """
    res = []

    # Get the source module and original attribute
    if source_module_name not in sys.modules:
        return res

    source_module = sys.modules[source_module_name]
    if not hasattr(source_module, attr_name):
        return res

    original_attr = getattr(source_module, attr_name)

    # Check all loaded modules for this attribute
    for mod_name, mod in list(sys.modules.items()):
        if mod is None:
            continue
        if mod_name == source_module_name:
            continue

        try:
            if hasattr(mod, attr_name):
                mod_attr = getattr(mod, attr_name)
                # Check if it's the same object (was imported from source)
                if mod_attr is original_attr:
                    res.append(mod_name)
        except Exception:
            continue

    return res


# Mocks the sys.modules and returns a cleanup function
def mock_sys_modules(
    override_modules: list[tuple[str, str, Mock]] = [],
    base_dir: str = ".",
    allowed_dirs: list[str] | None = None,
) -> Callable:
    importlib.invalidate_caches()

    # Deduplicate override_modules, keeping last occurrence
    modules = []
    for override_module in override_modules:
        module_found = False
        for module_name, module_prop, module_mock in modules:
            if module_name == override_module[0] and module_prop == override_module[1]:
                modules.remove((module_name, module_prop, module_mock))
                modules.append(override_module)
                module_found = True
                break
        if not module_found:
            modules.append(override_module)

    # Import the modules we need to mock so they are present in sys.modules
    for module_name, module_prop, module_mock in modules:
        importlib.import_module(module_name, module_name)

    # Track modules present before patching to detect new imports during context
    modules_before = set(sys.modules.keys())

    # Track what to restore on cleanup: list of (module_name, attr_name, original_value)
    cleanup_list = []

    # Store original values and mocks for later reference
    originals = {}  # (module_name, attr_name) -> original_value
    mocks = {}  # (module_name, attr_name) -> mock_value

    # Track pre-existing modules that need reload after all patches are applied
    preexisting_modules_to_reload = set()

    for module_name, module_prop, module_mock in modules:
        source_module = sys.modules[module_name]

        # Save original value from source module
        original_value = getattr(source_module, module_prop)
        originals[(module_name, module_prop)] = original_value
        mocks[(module_name, module_prop)] = module_mock

        # Find all modules that imported this attribute BEFORE we patch
        importing_modules = _find_modules_with_imported_attr(module_name, module_prop)

        # Patch the source module
        cleanup_list.append((module_name, module_prop, original_value))
        setattr(source_module, module_prop, module_mock)

        # Patch all modules that imported this attribute (handles relative imports)
        for importing_mod_name in importing_modules:
            try:
                importing_mod = sys.modules[importing_mod_name]
                cleanup_list.append((importing_mod_name, module_prop, original_value))
                setattr(importing_mod, module_prop, module_mock)
                # Mark for reload to recompute module-level state with mocked functions
                preexisting_modules_to_reload.add(importing_mod_name)
            except Exception:
                continue

    # Reload pre-existing modules so their module-level state is recomputed with mocks
    for mod_name in preexisting_modules_to_reload:
        try:
            _reload_module_in_place(mod_name)
        except Exception:
            continue

    # Build cleanup function to restore original values
    def _cleanup():
        importlib.invalidate_caches()

        # Find modules imported DURING the context that have our mocked attributes
        modules_after = set(sys.modules.keys())
        new_modules = modules_after - modules_before

        # Track which new modules need to be reloaded (they imported mocked attributes)
        modules_to_reload = set()

        for new_mod_name in new_modules:
            if new_mod_name not in sys.modules:
                continue
            new_mod = sys.modules[new_mod_name]
            if new_mod is None:
                continue

            # Check if this new module has any of our mocked attributes
            for (src_mod_name, attr_name), mock_value in mocks.items():
                try:
                    if hasattr(new_mod, attr_name):
                        mod_attr = getattr(new_mod, attr_name)
                        if mod_attr is mock_value:
                            # This module imported our mock, mark for reload
                            modules_to_reload.add(new_mod_name)
                            # Also restore the attribute immediately
                            original = originals[(src_mod_name, attr_name)]
                            setattr(new_mod, attr_name, original)
                except Exception:
                    continue

        # Restore all tracked modules (pre-existing modules)
        for mod_name, attr_name, original_value in cleanup_list:
            try:
                if mod_name in sys.modules:
                    setattr(sys.modules[mod_name], attr_name, original_value)
            except Exception:
                continue

        # Reload modules that were imported during the context
        # This recomputes module-level state with restored (real) functions
        for mod_name in modules_to_reload:
            try:
                _reload_module_in_place(mod_name)
            except Exception:
                continue

        # Also reload pre-existing modules that were reloaded on entry
        for mod_name in preexisting_modules_to_reload:
            try:
                _reload_module_in_place(mod_name)
            except Exception:
                continue

    return _cleanup


def import_and_reload_module(module_name: str) -> ModuleType:
    """
    Import a module, or reload it if already imported.

    Useful for resetting module-level state after mocking. For example, if a module
    executes code at import time that depends on a mocked function, you may need to
    reload it after the mock context to get fresh state with the real implementation.

    Example:
        # Module has: DEFAULT_USER = fetch_user("system") at import time
        # After mocking fetch_user in a test, reload to reset DEFAULT_USER
        cache_module = import_and_reload_module("myapp.services.cache")
    """
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])
        return sys.modules[module_name]

    importlib.import_module(module_name, module_name)
    return sys.modules[module_name]


class MockSysModules:
    mock_sys_modules_cleanup: Callable | None = None

    def __init__(
        self,
        override_modules: list[tuple[str, str, Any]] | None = None,
        base_dir: str | None = None,
        allowed_dirs: list[str] | None = None,
    ):
        self.override_modules = override_modules or []
        # Use provided values or fall back to config defaults
        self.base_dir = base_dir if base_dir is not None else DeepMockConfig.base_dir
        self.allowed_dirs = allowed_dirs if allowed_dirs is not None else DeepMockConfig.allowed_dirs

    def __enter__(self):
        self.mock_sys_modules_cleanup = mock_sys_modules(
            self.override_modules,
            base_dir=self.base_dir,
            allowed_dirs=self.allowed_dirs,
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.mock_sys_modules_cleanup:
            self.mock_sys_modules_cleanup()


# Utility method that will print out all mock calls
# It can help us debug and write tests
def print_all_mock_calls(mock):
    print("--------------------------------")
    print("     Printing all mock calls    ")
    print("--------------------------------")

    for call_name, call_args, call_kwargs in mock.mock_calls:
        print(f"Call name   - type: {type(call_name)}", call_name)
        print(f"Call args   - type: {type(call_args)}", call_args)
        print(f"Call kwargs - type: {type(call_kwargs)}", call_kwargs)
        print("--------------------------------")

    print("--------------------------------")