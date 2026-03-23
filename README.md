# deep-mock

A Python mocking library that simplifies patching and handles edge cases that `unittest.mock.patch` cannot solve.

## The Problem

Python's standard `unittest.mock.patch` has limitations:

1. **You must patch at the right location** - If `module_b` imports `func` from `module_a`, you need to patch `module_b.func`, not `module_a.func`. This gets complicated with multiple imports.

2. **Module-level state is not recomputed** - If a module computes values at import time using the function you're mocking, those values remain stale:

```python
# checkout.py
from myapp.config import load_tax_rate

SALES_TAX = load_tax_rate()  # Computed ONCE at import time
```

Even if you patch `load_tax_rate`, `SALES_TAX` still has the original value.

3. **Indirect dependencies are invisible** - If `module_c` imports from `module_b` which imports from `module_a`, patching `module_a` won't affect `module_c`'s module-level state.

## The Solution

`deep-mock` solves all of these problems:

- **Patch once, apply everywhere** - Patches propagate to all modules that imported the mocked function
- **Auto-reload modules** - Module-level state is automatically recomputed with mocked values
- **Handle edge cases** - `import_and_reload_module` for indirect dependencies

## Installation

```bash
pip install deep-mock
```

## Quick Start

```python
from unittest.mock import Mock
from deep_mock import MockSysModules

mock_fetch = Mock(return_value={"id": "1", "name": "Test User"})

with MockSysModules([
    ("myapp.database", "fetch_user", mock_fetch),
]):
    # All modules that import fetch_user now use the mock
    # Module-level state is recomputed with the mock
    from myapp.services import user_service
    assert user_service.get_user("1")["name"] == "Test User"

# After exiting, everything is restored to original
```

## Examples

### Example 1: Simple Patching

The most basic use case - mock a function and all its imports are automatically patched.

```python
from unittest.mock import Mock
from deep_mock import MockSysModules

# Create your mock
mock_db_connect = Mock(return_value={"connected": True})

# Use MockSysModules context manager
with MockSysModules([
    ("myapp.database", "connect", mock_db_connect),
]):
    from myapp.api import handler

    result = handler.process_request()

    # Assert the mock was called
    mock_db_connect.assert_called_once()
```

### Example 2: Module-Level State (Direct Dependencies)

When a module computes values at import time, `deep-mock` automatically reloads it.

```python
# myapp/checkout.py
from myapp.config import load_tax_rate

# This runs ONCE at import time
SALES_TAX = load_tax_rate()

def get_sales_tax():
    return SALES_TAX
```

```python
# test_checkout.py
from unittest.mock import Mock
from deep_mock import MockSysModules

def test_sales_tax_is_mocked():
    mock_load_tax_rate = Mock(return_value=0.15)

    with MockSysModules([
        ("myapp.config", "load_tax_rate", mock_load_tax_rate),
    ]):
        from myapp.checkout import get_sales_tax

        # SALES_TAX was recomputed with the mock!
        assert get_sales_tax() == 0.15

    # After exiting, SALES_TAX is restored to real value
```

### Example 3: Indirect Dependencies (Edge Case)

When module C depends on module B which depends on module A, and you mock something in A:

```python
# myapp/config.py
def load_tax_rate():
    return 0.08

# myapp/checkout.py
from myapp.config import load_tax_rate
SALES_TAX = load_tax_rate()

def get_sales_tax():
    return SALES_TAX

# myapp/pricing.py
from myapp.checkout import get_sales_tax

# Indirect dependency - imports from checkout, not config
PRICE_LABEL = f"Tax rate: {get_sales_tax() * 100}%"
```

```python
# test_indirect.py
from unittest.mock import Mock
from deep_mock import MockSysModules, import_and_reload_module

def test_indirect_dependency():
    mock_load_tax_rate = Mock(return_value=0.15)

    # Import pricing BEFORE mocking
    from myapp import pricing
    assert pricing.PRICE_LABEL == "Tax rate: 8.0%"

    with MockSysModules([
        ("myapp.config", "load_tax_rate", mock_load_tax_rate),
    ]):
        # checkout is auto-reloaded (direct dependency)
        from myapp.checkout import get_sales_tax
        assert get_sales_tax() == 0.15

        # pricing is NOT auto-reloaded (indirect dependency)
        # Its PRICE_LABEL still has the old value!
        assert pricing.PRICE_LABEL == "Tax rate: 8.0%"

        # Use import_and_reload_module to fix this
        pricing = import_and_reload_module("myapp.pricing")
        assert pricing.PRICE_LABEL == "Tax rate: 15.0%"
```

### Example 4: Mocking Multiple Functions

```python
from unittest.mock import Mock
from deep_mock import MockSysModules

mock_fetch = Mock(return_value={"id": "1", "name": "Test"})
mock_save = Mock(return_value=True)
mock_delete = Mock(return_value=True)

with MockSysModules([
    ("myapp.database", "fetch_user", mock_fetch),
    ("myapp.database", "save_user", mock_save),
    ("myapp.database", "delete_user", mock_delete),
]):
    # All three functions are mocked everywhere
    pass
```

### Example 5: Mocking Classes

```python
from unittest.mock import Mock
from deep_mock import MockSysModules

# Create a mock class
MockDatabaseClient = Mock()
mock_instance = Mock()
mock_instance.connect.return_value = {"status": "connected"}
mock_instance.query.return_value = [{"id": 1}]
MockDatabaseClient.return_value = mock_instance

with MockSysModules([
    ("myapp.database", "DatabaseClient", MockDatabaseClient),
]):
    from myapp.services import data_service

    result = data_service.get_all_records()
    MockDatabaseClient.assert_called_once()
```

## Configuration with conftest.py

Set project-wide defaults in your `conftest.py`:

```python
# conftest.py
from deep_mock import DeepMockConfig

def pytest_configure(config):
    DeepMockConfig.configure(
        base_dir="src",  # Base directory to scan for imports
        allowed_dirs=["src/myapp"],  # Only scan these directories
    )
```

Now all `MockSysModules` usage will use these defaults:

```python
# test_something.py
from deep_mock import MockSysModules

# Uses conftest.py defaults automatically
with MockSysModules([("myapp.database", "fetch_user", mock)]):
    pass

# Override for specific test if needed
with MockSysModules(
    [("myapp.database", "fetch_user", mock)],
    base_dir="other_dir",
):
    pass
```

## Debugging Mock Calls

Use the debugging utilities to inspect mock calls:

```python
from unittest.mock import Mock
from deep_mock import MockSysModules, print_all_mock_calls, find_calls_in_mock_calls

mock_db = Mock()

with MockSysModules([("myapp.database", "db", mock_db)]):
    from myapp.services import user_service
    user_service.create_user({"name": "Alice"})
    user_service.create_user({"name": "Bob"})

    # Print all calls for debugging
    print_all_mock_calls(mock_db)

    # Find specific calls
    save_calls = find_calls_in_mock_calls(
        mock_db,
        "save",
        call_filter=lambda args, kwargs: args[0]["name"] == "Alice"
    )
```

## API Reference

### `MockSysModules`

Context manager for mocking with automatic module reloading.

```python
class MockSysModules:
    def __init__(
        self,
        override_modules: list[tuple[str, str, Any]] | None = None,
        base_dir: str | None = None,
        allowed_dirs: list[str] | None = None,
    ):
        """
        Args:
            override_modules: List of (module_name, attribute_name, mock) tuples.
                - module_name: Full module path (e.g., "myapp.database")
                - attribute_name: Name of the function/class to mock (e.g., "fetch_user")
                - mock: The mock object to replace it with

            base_dir: Base directory to scan for modules that import the mocked
                attributes. Defaults to DeepMockConfig.base_dir or ".".

            allowed_dirs: List of directories to limit scanning to. If None,
                scans all directories under base_dir. Defaults to
                DeepMockConfig.allowed_dirs.
        """
```

**Behavior:**

1. **On enter (`__enter__`):**
   - Patches the specified attributes in the source modules
   - Finds all loaded modules that imported these attributes
   - Patches those modules too
   - Reloads all affected modules so module-level state is recomputed with mocks

2. **On exit (`__exit__`):**
   - Restores all original attributes
   - Reloads all affected modules so module-level state is recomputed with real values
   - Also reloads modules that were imported during the context

---

### `mock_sys_modules`

Function version of `MockSysModules`. Returns a cleanup function.

```python
def mock_sys_modules(
    override_modules: list[tuple[str, str, Any]] | None = None,
    base_dir: str = ".",
    allowed_dirs: list[str] | None = None,
) -> Callable[[], None]:
    """
    Apply mocks and return a cleanup function.

    Args:
        override_modules: List of (module_name, attribute_name, mock) tuples.
        base_dir: Base directory to scan for imports.
        allowed_dirs: Directories to limit scanning to.

    Returns:
        A cleanup function that restores original values and reloads modules.

    Example:
        cleanup = mock_sys_modules([("myapp.db", "fetch", mock)])
        try:
            # ... test code ...
        finally:
            cleanup()
    """
```

---

### `import_and_reload_module`

Import a module, or reload it if already imported. Essential for handling indirect dependencies.

```python
def import_and_reload_module(module_name: str) -> ModuleType:
    """
    Import or reload a module, returning the module object.

    This is necessary for modules with INDIRECT dependencies on mocked functions.
    These modules import from other modules (not directly from the mocked module),
    so they are not automatically detected and reloaded by MockSysModules.

    Args:
        module_name: Full module path (e.g., "myapp.services.user_service")

    Returns:
        The imported/reloaded module object.

    Example:
        # user_service imports from cache, which imports from database
        # When we mock database.fetch_user, user_service is not auto-reloaded

        with MockSysModules([("myapp.database", "fetch_user", mock)]):
            # Manually reload to recompute module-level state
            user_service = import_and_reload_module("myapp.services.user_service")
            assert user_service.CACHED_VALUE == "mocked value"
    """
```

**When to use:**

- Module has module-level state computed from an indirect dependency
- Module was imported before entering `MockSysModules` and has indirect dependencies
- You need to force a reload at a specific point in your test

---

### `DeepMockConfig`

Global configuration for `deep-mock` defaults. Configure once in `conftest.py`.

```python
class DeepMockConfig:
    base_dir: str = "."
    allowed_dirs: list[str] | None = None

    @classmethod
    def configure(
        cls,
        base_dir: str | None = None,
        allowed_dirs: list[str] | None = None,
    ):
        """
        Set default values for MockSysModules.

        Args:
            base_dir: Default base directory for scanning modules.
            allowed_dirs: Default directories to limit scanning to.

        Example:
            # In conftest.py
            def pytest_configure(config):
                DeepMockConfig.configure(
                    base_dir="src",
                    allowed_dirs=["src/myapp", "src/lib"],
                )
        """

    @classmethod
    def reset(cls):
        """Reset configuration to defaults."""
```

---

### `find_calls_in_mock_calls`

Filter mock call history by name and optional predicate.

```python
def find_calls_in_mock_calls(
    mock,
    call_name: str,
    call_filter: Callable[[tuple, dict[str, Any]], bool] | None = None,
) -> list[tuple[str, tuple, dict]]:
    """
    Find specific calls in a mock's call history.

    Args:
        mock: The mock object to inspect.
        call_name: Name of the method call to find (e.g., "save", "().query").
        call_filter: Optional function (args, kwargs) -> bool to filter calls.

    Returns:
        List of (call_name, args, kwargs) tuples matching the criteria.

    Example:
        # Find all 'save' calls where the first arg has status='active'
        calls = find_calls_in_mock_calls(
            mock_db,
            "save",
            call_filter=lambda args, kwargs: args[0]["status"] == "active"
        )
        assert len(calls) == 2
    """
```

---

### `print_all_mock_calls`

Debug utility to print all calls made to a mock.

```python
def print_all_mock_calls(mock):
    """
    Print all calls made to a mock object for debugging.

    Prints each call with:
    - Call name (e.g., "", "().method", "().method().chain")
    - Call args (tuple)
    - Call kwargs (dict)

    Example output:
        --------------------------------
             Printing all mock calls
        --------------------------------
        Call name   - type: <class 'str'> ().collection
        Call args   - type: <class 'tuple'> ('users',)
        Call kwargs - type: <class 'dict'> {}
        --------------------------------
    """
```

---

### `fake_useless_decorator`

A pass-through decorator for replacing real decorators in tests.

```python
def fake_useless_decorator(func):
    """
    A decorator that does nothing - just returns the function as-is.

    Useful for mocking decorators that have side effects you want to avoid
    in tests (e.g., caching, authentication, rate limiting).

    Example:
        with MockSysModules([
            ("myapp.decorators", "require_auth", fake_useless_decorator),
            ("myapp.decorators", "cache_result", fake_useless_decorator),
        ]):
            # Decorators are now no-ops
            from myapp.api import handler
            handler.protected_endpoint()  # No auth check
    """
```

## License

MIT
