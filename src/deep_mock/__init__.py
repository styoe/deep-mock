"""
deep-mock: A Python mocking library for deep module-level mocking
"""

from deep_mock.deep_mock import (
    DeepMockConfig,
    MockSysModules,
    fake_useless_decorator,
    find_calls_in_mock_calls,
    import_and_reload_module,
    mock_sys_modules,
    print_all_mock_calls,
)

__version__ = "0.1.0"
__all__ = [
    "DeepMockConfig",
    "MockSysModules",
    "__version__",
    "fake_useless_decorator",
    "find_calls_in_mock_calls",
    "import_and_reload_module",
    "mock_sys_modules",
    "print_all_mock_calls",
]
