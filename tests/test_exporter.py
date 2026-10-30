"""Unit tests for Supplier PO Exporter Plugin."""

from collections import OrderedDict
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

try:
    from django.conf import settings
    if not settings.configured:
        settings.configure(USE_I18N=False)
except Exception:
    pass

try:
    from inventree_supplier_po_exporter.exporter import (
        SupplierPoExporterPlugin,
        format_quantity,
        get_sku_for_line,
    )
except ImportError:
    try:
        from supplier_po_exporter.exporter import (
            SupplierPoExporterPlugin,
            format_quantity,
            get_sku_for_line,
        )
    except ImportError:
        from exporter import (
            SupplierPoExporterPlugin,
            format_quantity,
            get_sku_for_line,
        )


class DummyModel:
    """Dummy class to simulate models without Django dependencies."""
    pass


class PurchaseOrderLineItem(DummyModel):
    """Simulated PurchaseOrderLineItem model."""
    pass


class OtherModel(DummyModel):
    """Simulated other model."""
    pass


class TestSupplierPoExporterHelpers(unittest.TestCase):
    """Tests for standalone helper functions."""

    def test_format_quantity_integers(self):
        """Test formatting of integer quantities."""
        self.assertEqual(format_quantity(10), "10")
        self.assertEqual(format_quantity(10.0), "10")
        self.assertEqual(format_quantity(Decimal("10.000")), "10")
        self.assertEqual(format_quantity(Decimal("10")), "10")

    def test_format_quantity_decimals(self):
        """Test formatting of fractional quantities."""
        self.assertEqual(format_quantity(Decimal("2.5000")), "2.5")
        self.assertEqual(format_quantity(Decimal("0.75")), "0.75")
        self.assertEqual(format_quantity(1.25), "1.25")

    def test_format_quantity_edge_cases(self):
        """Test edge cases (None, zero, strings)."""
        self.assertEqual(format_quantity(None), "0")
        self.assertEqual(format_quantity(0), "0")
        self.assertEqual(format_quantity("not_a_number"), "not_a_number")

    def test_get_sku_resolution_hierarchy(self):
        """Test the 5-step fallback hierarchy for resolving line item SKU."""
        # 1. Supplier SKU
        line1 = MagicMock()
        line1.part.SKU = "TME-12345"
        line1.part.manufacturer_part.MPN = "MPN-999"
        line1.part.part.IPN = "IPN-001"
        self.assertEqual(get_sku_for_line(line1), "TME-12345")

        # 2. Manufacturer MPN
        line2 = MagicMock()
        line2.part.SKU = ""
        line2.part.manufacturer_part.MPN = "MPN-999"
        line2.part.part.IPN = "IPN-001"
        self.assertEqual(get_sku_for_line(line2), "MPN-999")

        # 3. Internal Part Number (IPN)
        line3 = MagicMock()
        line3.part.SKU = None
        line3.part.manufacturer_part = None
        line3.part.part.IPN = "IPN-001"
        line3.part.part.name = "Resistor 10k"
        self.assertEqual(get_sku_for_line(line3), "IPN-001")

        # 4. Part Name
        line4 = MagicMock()
        line4.part.SKU = None
        line4.part.manufacturer_part = None
        line4.part.part.IPN = ""
        line4.part.part.name = "Capacitor 100nF"
        self.assertEqual(get_sku_for_line(line4), "Capacitor 100nF")

        # 5. Fallback to reference or description
        line5 = MagicMock()
        line5.part = None
        line5.reference = "LINE-REF-42"
        self.assertEqual(get_sku_for_line(line5), "LINE-REF-42")

        line6 = MagicMock()
        line6.part = None
        line6.reference = None
        line6.description = "Custom Solder Paste"
        self.assertEqual(get_sku_for_line(line6), "Custom Solder Paste")

        # None / empty
        self.assertEqual(get_sku_for_line(None), "UNKNOWN_SKU")
        empty_line = MagicMock(part=None, reference=None, description=None)
        self.assertEqual(get_sku_for_line(empty_line), "UNKNOWN_SKU")


class TestSupplierPoExporterPlugin(unittest.TestCase):
    """Tests for SupplierPoExporterPlugin core logic."""

    def setUp(self):
        self.plugin = SupplierPoExporterPlugin()

    def test_plugin_metadata(self):
        """Verify plugin metadata attributes."""
        self.assertEqual(self.plugin.SLUG, "supplier-po-exporter")
        self.assertEqual(self.plugin.NAME, "Supplier PO Exporter")
        self.assertEqual(self.plugin.VERSION, "2.0.0")
        self.assertTrue(bool(self.plugin.DESCRIPTION))

    def test_supports_export(self):
        """Verify export support validation for models."""
        self.assertTrue(self.plugin.supports_export(PurchaseOrderLineItem))
        self.assertFalse(self.plugin.supports_export(OtherModel))
        self.assertFalse(self.plugin.supports_export(None))

    def test_detect_supplier_explicit_context(self):
        """Verify detection when user selects an explicit supplier format."""
        # export_supplier_format prefix
        self.assertEqual(
            self.plugin.detect_supplier(None, {'export_supplier_format': 'tme'}),
            'tme',
        )
        self.assertEqual(
            self.plugin.detect_supplier(None, {'export_supplier_format': 'mouser'}),
            'mouser',
        )
        self.assertEqual(
            self.plugin.detect_supplier(None, {'export_supplier_format': 'generic'}),
            'generic',
        )

        # supplier_format without prefix
        self.assertEqual(
            self.plugin.detect_supplier(None, {'supplier_format': 'TME'}),
            'tme',
        )

    def test_detect_supplier_auto_from_order(self):
        """Verify automatic detection based on Purchase Order supplier name."""
        # TME supplier
        tme_line = MagicMock()
        tme_line.order.supplier.name = "Transfer Multisort Elektronik (TME)"
        self.assertEqual(self.plugin.detect_supplier([tme_line], {'export_supplier_format': 'auto'}), 'tme')

        # Mouser supplier
        mouser_line = MagicMock()
        mouser_line.order.supplier.name = "Mouser Electronics Poland"
        self.assertEqual(self.plugin.detect_supplier([mouser_line], {}), 'mouser')

        # Unknown / other supplier
        digikey_line = MagicMock()
        digikey_line.order.supplier.name = "Digi-Key Corporation"
        self.assertEqual(self.plugin.detect_supplier([digikey_line], {}), 'generic')

        # Empty queryset
        self.assertEqual(self.plugin.detect_supplier([], {}), 'generic')

    def test_update_headers_csv(self):
        """Verify CSV header definitions (single-column with semicolon)."""
        # Without headers (direct copy-paste upload)
        headers = self.plugin.update_headers(
            OrderedDict(),
            {'export_format': 'csv', 'export_supplier_format': 'tme', 'export_include_headers': False},
        )
        self.assertEqual(headers, OrderedDict({'SKU;Quantity': ''}))

        # With headers
        headers_tme = self.plugin.update_headers(
            OrderedDict(),
            {'export_format': 'csv', 'export_supplier_format': 'tme', 'export_include_headers': True},
        )
        self.assertEqual(headers_tme, OrderedDict({'SKU;Quantity': 'SKU;Quantity'}))

        headers_mouser = self.plugin.update_headers(
            OrderedDict(),
            {'export_format': 'csv', 'export_supplier_format': 'mouser', 'export_include_headers': True},
        )
        self.assertEqual(headers_mouser, OrderedDict({'SKU;Quantity': 'Mouser Part Number;Quantity 1'}))

    def test_update_headers_xlsx(self):
        """Verify multi-column header definitions for XLSX/TSV."""
        # Mouser XLSX without headers
        headers_mouser_no_hdr = self.plugin.update_headers(
            OrderedDict(),
            {'export_format': 'xlsx', 'export_supplier_format': 'mouser', 'export_include_headers': False},
        )
        self.assertEqual(
            headers_mouser_no_hdr,
            OrderedDict({'Mouser Part Number': '', 'Quantity 1': ''}),
        )

        # Mouser XLSX with headers
        headers_mouser_hdr = self.plugin.update_headers(
            OrderedDict(),
            {'export_format': 'xlsx', 'export_supplier_format': 'mouser', 'export_include_headers': True},
        )
        self.assertEqual(
            headers_mouser_hdr,
            OrderedDict({'Mouser Part Number': 'Mouser Part Number', 'Quantity 1': 'Quantity 1'}),
        )

        # TME XLSX with headers
        headers_tme_hdr = self.plugin.update_headers(
            OrderedDict(),
            {'export_format': 'xlsx', 'export_supplier_format': 'tme', 'export_include_headers': True},
        )
        self.assertEqual(
            headers_tme_hdr,
            OrderedDict({'SKU': 'SKU', 'Quantity': 'Quantity'}),
        )

    def test_export_data_csv(self):
        """Verify data formatting for CSV exports (semicolon joined)."""
        line1 = MagicMock()
        line1.part.SKU = "NE555P"
        line1.quantity = Decimal("100.000")

        line2 = MagicMock()
        line2.part.SKU = "LM358N"
        line2.quantity = 25

        mock_output = MagicMock()

        data = self.plugin.export_data(
            queryset=[line1, line2],
            serializer_class=MagicMock(),
            headers=OrderedDict(),
            context={'export_format': 'csv', 'export_supplier_format': 'tme'},
            output=mock_output,
        )

        self.assertEqual(len(data), 2)
        self.assertEqual(data[0], {'SKU;Quantity': 'NE555P;100'})
        self.assertEqual(data[1], {'SKU;Quantity': 'LM358N;25'})
        self.assertEqual(mock_output.progress, 100)
        self.assertTrue(mock_output.save.called)

    def test_export_data_xlsx_mouser(self):
        """Verify data formatting for Mouser XLSX exports."""
        line = MagicMock()
        line.part.SKU = "595-NE555P"
        line.quantity = Decimal("50.0")

        data = self.plugin.export_data(
            queryset=[line],
            serializer_class=MagicMock(),
            headers=OrderedDict(),
            context={'export_format': 'xlsx', 'export_supplier_format': 'mouser'},
        )

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0], {'Mouser Part Number': '595-NE555P', 'Quantity 1': '50'})

    def test_export_data_xlsx_tme(self):
        """Verify data formatting for TME XLSX exports."""
        line = MagicMock()
        line.part.SKU = "1N4148-TME"
        line.quantity = 200

        data = self.plugin.export_data(
            queryset=[line],
            serializer_class=MagicMock(),
            headers=OrderedDict(),
            context={'export_format': 'xlsx', 'export_supplier_format': 'tme'},
        )

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0], {'SKU': '1N4148-TME', 'Quantity': '200'})

    def test_generate_filename(self):
        """Verify filename generation."""
        filename = self.plugin.generate_filename(PurchaseOrderLineItem, 'csv')
        self.assertTrue(filename.startswith("Supplier_PO_Export_"))
        self.assertTrue(filename.endswith(".csv"))

    def test_backward_compatibility_aliases(self):
        """Verify legacy aliases map to the unified plugin."""
        try:
            from inventree_supplier_po_exporter.exporter import (
                TmePoExporterComboPlugin,
                MouserPoExporterComboPlugin,
            )
        except ImportError:
            try:
                from supplier_po_exporter.exporter import (
                    TmePoExporterComboPlugin,
                    MouserPoExporterComboPlugin,
                )
            except ImportError:
                from exporter import (
                    TmePoExporterComboPlugin,
                    MouserPoExporterComboPlugin,
                )
        self.assertIs(TmePoExporterComboPlugin, SupplierPoExporterPlugin)
        self.assertIs(MouserPoExporterComboPlugin, SupplierPoExporterPlugin)

    def test_detect_supplier_setting_fallback(self):
        """Verify fallback to plugin setting when context and order are absent."""
        self.plugin.get_setting = MagicMock(return_value="tme")
        self.assertEqual(self.plugin.detect_supplier(None, {}), "tme")

        self.plugin.get_setting = MagicMock(return_value="mouser")
        self.assertEqual(self.plugin.detect_supplier(None, {}), "mouser")

    def test_export_data_empty_queryset(self):
        """Verify export_data handles empty or None querysets gracefully."""
        self.assertEqual(
            self.plugin.export_data(
                queryset=[],
                serializer_class=MagicMock(),
                headers=OrderedDict(),
                context={'export_format': 'csv'},
            ),
            [],
        )
        self.assertEqual(
            self.plugin.export_data(
                queryset=None,
                serializer_class=MagicMock(),
                headers=OrderedDict(),
                context={'export_format': 'xlsx'},
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
