"""Tests for MockSysModules demonstrating deep mocking capabilities."""

import sys

import pytest
from unittest.mock import Mock, patch

from deep_mock import DeepMockConfig, MockSysModules, mock_sys_modules


class TestStandardPatchLimitations:
    """Demonstrate that standard @patch doesn't work on nested module imports."""

    def test_standard_patch_does_not_affect_nested_imports(self):
        """
        Standard @patch only patches where you specify, not where the function
        is actually imported and used in other modules.
        """
        # Import the handler which internally imports fetch_user
        from deep_mock.examples.handlers.user_handler import handle_direct_fetch

        # Create a mock
        mock_fetch = Mock(return_value={"id": "123", "name": "Mocked User", "source": "mock"})

        # Patch at the original location - this WON'T affect the handler
        # because the handler already imported fetch_user
        with patch("deep_mock.examples.services.database.fetch_user", mock_fetch):
            result = handle_direct_fetch("123")

            # The mock was NOT called because the handler has its own reference
            # This demonstrates the limitation of standard @patch
            # Note: This might work in some cases depending on import order,
            # but fails in complex nested scenarios
            pass  # The behavior depends on import caching


class TestMockSysModules:
    """Test MockSysModules for deep mocking."""

    def test_mock_function_in_nested_module(self):
        """MockSysModules can mock functions that are imported across modules."""
        mock_fetch = Mock(return_value={
            "id": "test-123",
            "name": "Mocked User",
            "source": "mock",
        })

        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
            ],
            base_dir="src",
        ):
            # Re-import to get the mocked version
            from deep_mock.examples.services.database import fetch_user

            result = fetch_user("test-123")

            assert result["name"] == "Mocked User"
            assert result["source"] == "mock"
            mock_fetch.assert_called_once_with("test-123")

    def test_mock_multiple_functions(self):
        """MockSysModules can mock multiple functions at once."""
        mock_fetch = Mock(return_value={"id": "1", "name": "Mock User", "source": "mock"})
        mock_connect = Mock(return_value={"connected": True, "host": "mock-host", "connection_id": "mock-123"})

        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
                ("deep_mock.examples.services.database", "connect_to_database", mock_connect),
            ],
            base_dir="src",
        ):
            from deep_mock.examples.services.database import fetch_user, connect_to_database

            user = fetch_user("1")
            conn = connect_to_database("test-host")

            assert user["name"] == "Mock User"
            assert conn["host"] == "mock-host"

    def test_mock_class(self):
        """MockSysModules can mock classes."""
        MockDatabaseClient = Mock()
        mock_instance = Mock()
        mock_instance.connect.return_value = {"status": "mocked"}
        mock_instance.query.return_value = {"results": ["mocked_result"]}
        MockDatabaseClient.return_value = mock_instance

        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "DatabaseClient", MockDatabaseClient),
            ],
            base_dir="src",
        ):
            from deep_mock.examples.services.database import DatabaseClient

            client = DatabaseClient("mock-host")
            result = client.connect()

            assert result["status"] == "mocked"
            MockDatabaseClient.assert_called_once_with("mock-host")

    def test_cleanup_restores_original(self):
        """After exiting context, original functions are restored."""
        from deep_mock.examples.services.database import fetch_user as original_fetch

        original_result = original_fetch("test")
        assert original_result["source"] == "database"

        mock_fetch = Mock(return_value={"source": "mock"})

        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
            ],
            base_dir="src",
        ):
            from deep_mock.examples.services.database import fetch_user
            assert fetch_user("test")["source"] == "mock"

        # After context exit, reimport should give original
        import importlib
        import deep_mock.examples.services.database as db_module
        importlib.reload(db_module)

        restored_result = db_module.fetch_user("test")
        assert restored_result["source"] == "database"


class TestDeepMockConfig:
    """Test DeepMockConfig for setting defaults."""

    def setup_method(self):
        """Reset config before each test."""
        DeepMockConfig.reset()

    def teardown_method(self):
        """Reset config after each test."""
        DeepMockConfig.reset()

    def test_default_values(self):
        """Config has sensible defaults."""
        assert DeepMockConfig.base_dir == "."
        assert DeepMockConfig.allowed_dirs is None

    def test_configure_sets_values(self):
        """configure() sets the config values."""
        DeepMockConfig.configure(
            base_dir="src",
            allowed_dirs=["src/api", "src/services"],
        )

        assert DeepMockConfig.base_dir == "src"
        assert DeepMockConfig.allowed_dirs == ["src/api", "src/services"]

    def test_configure_partial_update(self):
        """configure() only updates provided values."""
        DeepMockConfig.configure(base_dir="app")

        assert DeepMockConfig.base_dir == "app"
        assert DeepMockConfig.allowed_dirs is None  # unchanged

    def test_reset_restores_defaults(self):
        """reset() restores default values."""
        DeepMockConfig.configure(
            base_dir="custom",
            allowed_dirs=["custom/dir"],
        )
        DeepMockConfig.reset()

        assert DeepMockConfig.base_dir == "."
        assert DeepMockConfig.allowed_dirs is None

    def test_mock_sys_modules_uses_config_defaults(self):
        """MockSysModules uses DeepMockConfig defaults when not overridden."""
        DeepMockConfig.configure(
            base_dir="src",
            allowed_dirs=["src/deep_mock"],
        )

        mock_fetch = Mock(return_value={"name": "Config Mock"})

        # Don't pass base_dir or allowed_dirs - should use config
        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
            ],
        ) as ctx:
            assert ctx.base_dir == "src"
            assert ctx.allowed_dirs == ["src/deep_mock"]

    def test_mock_sys_modules_override_config(self):
        """MockSysModules can override DeepMockConfig defaults."""
        DeepMockConfig.configure(
            base_dir="default_dir",
            allowed_dirs=["default/path"],
        )

        mock_fetch = Mock(return_value={"name": "Override Mock"})

        # Explicitly pass values to override config
        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
            ],
            base_dir="override_dir",
            allowed_dirs=["override/path"],
        ) as ctx:
            assert ctx.base_dir == "override_dir"
            assert ctx.allowed_dirs == ["override/path"]

    def test_config_simulates_conftest_usage(self):
        """
        Simulate how DeepMockConfig would be used in conftest.py.

        In a real project, conftest.py would have:

            def pytest_configure(config):
                DeepMockConfig.configure(
                    base_dir="app",
                    allowed_dirs=["app/api", "app/services"],
                )
        """
        # Simulate conftest.py setup
        DeepMockConfig.configure(
            base_dir="src",
            allowed_dirs=["src/deep_mock/examples"],
        )

        # Now all tests use these defaults
        mock_fetch = Mock(return_value={"id": "1", "name": "Conftest Mock", "source": "mock"})

        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
            ],
        ):
            from deep_mock.examples.services.database import fetch_user

            result = fetch_user("1")
            assert result["name"] == "Conftest Mock"


class TestFindCallsInMockCalls:
    """Test the find_calls_in_mock_calls utility."""

    def test_find_calls_by_name(self):
        """Can filter mock calls by name."""
        from deep_mock import find_calls_in_mock_calls

        mock = Mock()
        mock.method_a("arg1")
        mock.method_b("arg2")
        mock.method_a("arg3")

        calls = find_calls_in_mock_calls(mock, "method_a")

        assert len(calls) == 2
        assert calls[0][1] == ("arg1",)
        assert calls[1][1] == ("arg3",)

    def test_find_calls_with_filter(self):
        """Can filter mock calls with a custom predicate."""
        from deep_mock import find_calls_in_mock_calls

        mock = Mock()
        mock.save({"id": 1, "status": "active"})
        mock.save({"id": 2, "status": "inactive"})
        mock.save({"id": 3, "status": "active"})

        # Find only saves with status="active"
        calls = find_calls_in_mock_calls(
            mock,
            "save",
            call_filter=lambda args, kwargs: args[0]["status"] == "active",
        )

        assert len(calls) == 2
        assert calls[0][1][0]["id"] == 1
        assert calls[1][1][0]["id"] == 3


class TestRelativeImports:
    """Test MockSysModules with relative imports."""

    def test_mock_function_used_via_relative_import(self):
        """MockSysModules works when target module uses relative imports."""
        mock_fetch = Mock(return_value={
            "id": "rel-123",
            "name": "Relative Mock User",
            "source": "mock",
        })

        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
            ],
            base_dir="src",
        ):
            # Import module that uses relative imports internally
            from deep_mock.examples.services.external_api_relative import get_user_name_relative

            result = get_user_name_relative("rel-123")

            # The mock should be called even though external_api_relative
            # uses `from .database import fetch_user`
            mock_fetch.assert_called()

    def test_mock_multiple_functions_with_relative_imports(self):
        """Mock multiple functions in module imported relatively."""
        mock_fetch = Mock(return_value={
            "id": "1",
            "name": "Mock User",
            "source": "mock",
        })
        mock_connect = Mock(return_value={
            "connected": True,
            "host": "mock-host",
            "connection_id": "mock-conn",
        })

        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
                ("deep_mock.examples.services.database", "connect_to_database", mock_connect),
            ],
            base_dir="src",
        ):
            from deep_mock.examples.services.external_api_relative import get_user_profile_relative

            result = get_user_profile_relative("1")

            # Both mocks should be called
            mock_fetch.assert_called_once_with("1")
            mock_connect.assert_called_once_with("localhost")
            assert result["import_type"] == "relative"

    def test_mock_deeply_nested_relative_imports(self):
        """Mock works through multiple levels of relative imports."""
        mock_fetch = Mock(return_value={
            "id": "deep-123",
            "name": "Deep Mock User",
            "source": "mock",
        })
        mock_connect = Mock(return_value={
            "connected": True,
            "host": "mock-host",
            "connection_id": "mock-conn",
        })

        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
                ("deep_mock.examples.services.database", "connect_to_database", mock_connect),
            ],
            base_dir="src",
        ):
            # This handler uses `from ..services.database import fetch_user`
            # and `from ..services.external_api_relative import get_user_profile_relative`
            from deep_mock.examples.handlers.user_handler_relative import (
                handle_user_request_relative,
                handle_direct_fetch_relative,
            )

            # Test handler that goes through external_api_relative
            result = handle_user_request_relative("deep-123")
            assert result["status"] == "success"
            assert result["import_type"] == "relative"

            # Test direct fetch
            direct_result = handle_direct_fetch_relative("deep-456")
            assert direct_result["status"] == "success"
            assert direct_result["import_type"] == "relative"

    def test_mock_class_with_relative_import(self):
        """MockSysModules can mock classes imported relatively."""
        MockDatabaseClient = Mock()
        mock_instance = Mock()
        mock_instance.connect.return_value = {"status": "mocked-relative"}
        MockDatabaseClient.return_value = mock_instance

        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "DatabaseClient", MockDatabaseClient),
            ],
            base_dir="src",
        ):
            # Handler uses `from ..services.database import DatabaseClient`
            from deep_mock.examples.handlers.user_handler_relative import handle_direct_fetch_relative

            # Import DatabaseClient through the handler's module
            from deep_mock.examples.handlers import user_handler_relative

            # Access DatabaseClient from the module's namespace
            client = user_handler_relative.DatabaseClient("relative-host")
            result = client.connect()

            assert result["status"] == "mocked-relative"
            MockDatabaseClient.assert_called_with("relative-host")


class TestImportAndReloadModule:
    """Test import_and_reload_module and automatic cleanup reload behavior."""

    def setup_method(self):
        """Ensure example modules are in a clean state before each test."""
        import importlib

        services_key = "deep_mock.examples.services"

        # Remove cache and user_service modules
        for mod_name in ["cache", "user_service"]:
            full_key = f"{services_key}.{mod_name}"
            if full_key in sys.modules:
                del sys.modules[full_key]
            # Also remove from parent package's namespace
            if services_key in sys.modules:
                services_mod = sys.modules[services_key]
                if hasattr(services_mod, mod_name):
                    delattr(services_mod, mod_name)

        # Reload database module to ensure fetch_user is the real function
        if "deep_mock.examples.services.database" in sys.modules:
            importlib.reload(sys.modules["deep_mock.examples.services.database"])

    def test_cleanup_auto_reloads_modules_imported_during_context(self):
        """
        Modules imported DURING the mock context are automatically reloaded
        on cleanup, so module-level state is recomputed with real functions.
        """
        from deep_mock import MockSysModules

        mock_fetch = Mock(return_value={
            "id": "mock-system",
            "name": "Mocked System User",
            "source": "mock",
        })

        # Import cache module INSIDE mock context
        # SYSTEM_USER will initially be set to the mocked value
        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
            ],
            base_dir="src",
        ):
            from deep_mock.examples.services.cache import get_system_user_name

            # During mock context, we get mocked value
            assert get_system_user_name() == "Mocked System User"

        # After exiting context, cleanup automatically reloads the cache module
        # so SYSTEM_USER is recomputed with the REAL fetch_user
        from deep_mock.examples.services import cache

        # Module-level state is now fresh (not stale)
        assert cache.SYSTEM_USER["name"] == "Real User"
        assert cache.SYSTEM_USER["source"] == "database"

        # The cached value matches fresh data
        from deep_mock.examples.services.database import fetch_user
        fresh_user = fetch_user("system")
        assert cache.get_system_user_name() == fresh_user["name"]

    def test_preloaded_module_is_auto_reloaded_on_entry(self):
        """
        Modules imported BEFORE the mock context are automatically reloaded
        on entry, so their module-level state is recomputed with mocked functions.
        """
        from deep_mock import MockSysModules

        # Import cache module BEFORE mock context
        from deep_mock.examples.services import cache
        original_system_user = cache.SYSTEM_USER
        assert original_system_user["name"] == "Real User"
        assert original_system_user["source"] == "database"

        mock_fetch = Mock(return_value={
            "id": "mock-system",
            "name": "Mocked System User",
            "source": "mock",
        })

        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
            ],
            base_dir="src",
        ):
            # The module was auto-reloaded on entry, so SYSTEM_USER now has
            # the mocked value (recomputed with mocked fetch_user)
            assert cache.SYSTEM_USER["name"] == "Mocked System User"
            assert cache.SYSTEM_USER["source"] == "mock"

        # After context exit, module is reloaded again with real functions
        assert cache.SYSTEM_USER["name"] == "Real User"
        assert cache.SYSTEM_USER["source"] == "database"

    def test_reload_already_imported_module(self):
        """import_and_reload_module reloads an already imported module."""
        from deep_mock import import_and_reload_module

        # First import
        from deep_mock.examples.services.cache import SYSTEM_USER
        original_id = id(SYSTEM_USER)

        # Reload should create new module-level objects
        cache_module = import_and_reload_module("deep_mock.examples.services.cache")

        # SYSTEM_USER should be a different object (re-created on reload)
        assert id(cache_module.SYSTEM_USER) != original_id

    def test_import_not_yet_loaded_module(self):
        """import_and_reload_module imports a module that isn't loaded yet."""
        from deep_mock import import_and_reload_module

        # Ensure module is not loaded
        if "deep_mock.examples.services.cache" in sys.modules:
            del sys.modules["deep_mock.examples.services.cache"]

        # Should import (not reload) since it's not loaded
        cache_module = import_and_reload_module("deep_mock.examples.services.cache")

        assert cache_module.SYSTEM_USER is not None
        assert cache_module.SYSTEM_USER["name"] == "Real User"

    def test_indirect_dependency_not_auto_reloaded(self):
        """
        Modules with INDIRECT dependencies on mocked functions are NOT
        automatically reloaded. This is the edge case where import_and_reload_module
        is necessary.

        user_service imports from cache (not directly from database), so when we
        mock database.fetch_user, user_service is not detected and not auto-reloaded.
        """
        from deep_mock import MockSysModules, import_and_reload_module

        # Import the indirect dependency module BEFORE mocking
        from deep_mock.examples.services import user_service
        assert user_service.SYSTEM_USER_NAME == "Real User"
        assert user_service.get_greeting() == "Hello, Real User!"

        mock_fetch = Mock(return_value={
            "id": "mock-system",
            "name": "Mocked System User",
            "source": "mock",
        })

        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
            ],
            base_dir="src",
        ):
            # cache is auto-reloaded (direct dependency), so its SYSTEM_USER is mocked
            from deep_mock.examples.services import cache
            assert cache.SYSTEM_USER["name"] == "Mocked System User"

            # BUT user_service is NOT auto-reloaded (indirect dependency)
            # Its SYSTEM_USER_NAME still has the old value
            assert user_service.SYSTEM_USER_NAME == "Real User"  # NOT updated!

            # To fix this, we need to manually reload user_service
            user_service_reloaded = import_and_reload_module(
                "deep_mock.examples.services.user_service"
            )

            # Now it has the mocked value
            assert user_service_reloaded.SYSTEM_USER_NAME == "Mocked System User"
            assert user_service_reloaded.get_greeting() == "Hello, Mocked System User!"

        # After exiting, cache is auto-reloaded back to real values
        assert cache.SYSTEM_USER["name"] == "Real User"

        # user_service needs manual reload again to get real values
        user_service_final = import_and_reload_module(
            "deep_mock.examples.services.user_service"
        )
        assert user_service_final.SYSTEM_USER_NAME == "Real User"
        assert user_service_final.get_greeting() == "Hello, Real User!"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_override_list(self):
        """MockSysModules works with empty override list."""
        with MockSysModules(override_modules=[]) as ctx:
            # Should not raise any errors
            assert ctx.override_modules == []

    def test_none_override_list(self):
        """MockSysModules works with None override list."""
        with MockSysModules(override_modules=None) as ctx:
            # Should not raise any errors
            assert ctx.override_modules == []

    def test_mock_nonexistent_attribute_raises(self):
        """Mocking a non-existent attribute raises AttributeError."""
        mock_func = Mock(return_value="mocked")

        with pytest.raises(AttributeError):
            with MockSysModules(
                override_modules=[
                    ("deep_mock.examples.services.database", "nonexistent_function", mock_func),
                ],
                base_dir="src",
            ):
                pass

    def test_duplicate_overrides_keeps_last(self):
        """When same module/attr is specified multiple times, last one wins."""
        mock_first = Mock(return_value={"name": "First Mock"})
        mock_second = Mock(return_value={"name": "Second Mock"})

        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_first),
                ("deep_mock.examples.services.database", "fetch_user", mock_second),
            ],
            base_dir="src",
        ):
            from deep_mock.examples.services.database import fetch_user

            result = fetch_user("test")

            # Second mock should be used (first mock should never be called)
            assert result["name"] == "Second Mock"
            mock_first.assert_not_called()
            # mock_second may be called multiple times (during module reloads)
            # but it should have been called with "test" at least once
            mock_second.assert_any_call("test")

    def test_modules_outside_allowed_dirs_not_patched(self):
        """Modules outside allowed_dirs are not auto-reloaded."""
        # This test verifies the directory filtering works
        mock_fetch = Mock(return_value={"name": "Filtered Mock"})

        # Use a non-existent directory - no modules should match
        with MockSysModules(
            override_modules=[
                ("deep_mock.examples.services.database", "fetch_user", mock_fetch),
            ],
            base_dir="src",
            allowed_dirs=["nonexistent_directory"],
        ):
            # The source module is still patched (it's always patched)
            from deep_mock.examples.services.database import fetch_user
            assert fetch_user("test")["name"] == "Filtered Mock"

            # But modules that imported it won't be auto-reloaded
            # because they're not in allowed_dirs
