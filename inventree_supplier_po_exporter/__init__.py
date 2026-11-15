"""InvenTree Supplier Purchase Order Exporter plugin."""

import importlib.util

PLUGIN_VERSION = '2.1.0'
__version__ = PLUGIN_VERSION

__all__ = ['PLUGIN_VERSION']

# The plugin class can only be imported inside an InvenTree environment.
# Outside of it (e.g. running the unit tests) only the formatting logic is usable.
if importlib.util.find_spec('InvenTree') is not None:
    from .plugin import SupplierPoExporterPlugin  # noqa: E402,F401

    __all__.append('SupplierPoExporterPlugin')
