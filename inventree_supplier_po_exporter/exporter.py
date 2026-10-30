"""Supplier Purchase Order Exporter Plugin for InvenTree.

Exports InvenTree Purchase Order line items formatted for direct cart/BOM
import into supplier portals (TME, Mouser, and Generic).
"""

from collections import OrderedDict
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger('inventree')

try:
    from django.utils.translation import gettext_lazy as _
    from rest_framework import serializers
except ImportError:  # pragma: no cover
    serializers = None
    _ = lambda s: s

try:
    from plugin import InvenTreePlugin
    from plugin.mixins import DataExportMixin, SettingsMixin
except ImportError:  # pragma: no cover
    class InvenTreePlugin:
        pass

    class DataExportMixin:
        pass

    class SettingsMixin:
        pass


if serializers:
    class SupplierPoExportOptionsSerializer(serializers.Serializer):
        """Dynamic export options presented in the InvenTree export modal."""

        export_supplier_format = serializers.ChoiceField(
            choices=[
                ('auto', _('Auto-detect from Order')),
                ('tme', _('TME')),
                ('mouser', _('Mouser')),
                ('generic', _('Generic (SKU, Quantity)')),
            ],
            default='auto',
            label=_('Supplier Format'),
            help_text=_(
                'Select target supplier format or auto-detect based on Purchase Order supplier.'
            ),
        )

        export_include_headers = serializers.BooleanField(
            default=False,
            label=_('Include Headers'),
            help_text=_(
                'Include column header row. Leave unchecked for direct supplier quick upload copy/paste.'
            ),
        )
else:  # pragma: no cover
    SupplierPoExportOptionsSerializer = None


def format_quantity(quantity) -> str:
    """Format quantity value cleanly without unnecessary trailing decimals.

    Examples:
        Decimal('10.0000') -> '10'
        Decimal('2.50')     -> '2.5'
        15.0                -> '15'
    """
    if quantity is None:
        return '0'
    try:
        val = Decimal(str(quantity))
        if val == val.to_integral():
            return str(int(val))
        return str(val.normalize())
    except (InvalidOperation, ValueError, TypeError):
        return str(quantity).strip()


def get_sku_for_line(line) -> str:
    """Resolve the most accurate SKU/Part Number for a PurchaseOrderLineItem.

    Resolution hierarchy:
        1. SupplierPart.SKU (supplier specific symbol / order code)
        2. ManufacturerPart.MPN (manufacturer part number)
        3. Part.IPN (internal part number)
        4. Part.name (part name)
        5. Line item reference / description fallback
    """
    if not line:
        return 'UNKNOWN_SKU'

    supplier_part = getattr(line, 'part', None)
    if supplier_part:
        # 1. Supplier-specific SKU
        sku = getattr(supplier_part, 'SKU', None)
        if sku and str(sku).strip():
            return str(sku).strip()

        # 2. Manufacturer Part Number
        mfg_part = getattr(supplier_part, 'manufacturer_part', None)
        if mfg_part:
            mpn = getattr(mfg_part, 'MPN', None)
            if mpn and str(mpn).strip():
                return str(mpn).strip()

        # 3. Internal Part Number (IPN)
        internal_part = getattr(supplier_part, 'part', None)
        if internal_part:
            ipn = getattr(internal_part, 'IPN', None)
            if ipn and str(ipn).strip():
                return str(ipn).strip()

            # 4. Part Name
            part_name = getattr(internal_part, 'name', None)
            if part_name and str(part_name).strip():
                return str(part_name).strip()

    # 5. Fallback to line reference or description
    line_ref = getattr(line, 'reference', None)
    if line_ref and str(line_ref).strip():
        return str(line_ref).strip()

    line_desc = getattr(line, 'description', None)
    if line_desc and str(line_desc).strip():
        return str(line_desc).strip()

    return 'UNKNOWN_SKU'


class SupplierPoExporterPlugin(SettingsMixin, DataExportMixin, InvenTreePlugin):
    """Unified InvenTree plugin for exporting Purchase Order lines to TME, Mouser, and Generic formats."""

    NAME = "Supplier PO Exporter"
    SLUG = "supplier-po-exporter"
    TITLE = _("Supplier Purchase Order Exporter")
    DESCRIPTION = _(
        "Export InvenTree Purchase Order line items formatted for TME, Mouser, and Generic supplier cart imports."
    )
    VERSION = "2.0.0"
    AUTHOR = _("Cezary / Antigravity")

    ExportOptionsSerializer = SupplierPoExportOptionsSerializer

    SETTINGS = {
        'DEFAULT_SUPPLIER_FORMAT': {
            'name': _('Default Supplier Format'),
            'description': _(
                'Default supplier format when not specified in export options.'
            ),
            'choices': [
                ('auto', _('Auto-detect from Order Supplier')),
                ('tme', _('TME')),
                ('mouser', _('Mouser')),
                ('generic', _('Generic')),
            ],
            'default': 'auto',
        },
        'DEFAULT_INCLUDE_HEADERS': {
            'name': _('Include Headers by Default'),
            'description': _(
                'Include column header row in exported files by default.'
            ),
            'validator': bool,
            'default': False,
        },
    }

    def __init__(self):
        """Initialize plugin and state tracking."""
        super().__init__()
        self._last_detected_supplier = 'generic'

    def supports_export(
        self,
        model_class: type,
        user=None,
        serializer_class=None,
        view_class=None,
        *args,
        **kwargs,
    ) -> bool:
        """Verify whether this plugin supports the given model class.

        Supports PurchaseOrderLineItem exports.
        """
        if model_class is None:
            return False

        name = getattr(model_class, '__name__', str(model_class))
        if name == 'PurchaseOrderLineItem':
            return True

        try:
            from order.models import PurchaseOrderLineItem
            return issubclass(model_class, PurchaseOrderLineItem)
        except Exception:
            return False

    def generate_filename(self, model_class, export_format: str) -> str:
        """Generate a clean and informative filename for exported order items."""
        try:
            from InvenTree.helpers import current_date
            date_str = current_date().isoformat()
        except ImportError:
            from datetime import date
            date_str = date.today().isoformat()

        return f"Supplier_PO_Export_{date_str}.{str(export_format).lower()}"

    def detect_supplier(self, queryset, context: dict) -> str:
        """Determine target supplier format: explicit context or auto-detected from order."""
        context = context or {}

        # 1. Explicit option passed via context (with or without 'export_' prefix)
        fmt = (
            context.get('export_supplier_format')
            or context.get('supplier_format')
            or ''
        ).strip().lower()

        if fmt in ['tme', 'mouser', 'generic']:
            return fmt

        # 2. Auto-detection from Purchase Order supplier
        if queryset is not None:
            try:
                first_item = (
                    queryset.first()
                    if hasattr(queryset, 'first')
                    else (queryset[0] if len(queryset) > 0 else None)
                )
                if first_item:
                    order = getattr(first_item, 'order', None)
                    supplier = getattr(order, 'supplier', None) if order else None
                    if supplier:
                        sup_name = (getattr(supplier, 'name', '') or '').lower()
                        if 'tme' in sup_name:
                            return 'tme'
                        if 'mouser' in sup_name:
                            return 'mouser'
            except Exception as e:
                logger.debug("Could not auto-detect supplier from order: %s", e)

        # 3. Check plugin setting if available
        if hasattr(self, 'get_setting'):
            try:
                setting_val = self.get_setting(
                    'DEFAULT_SUPPLIER_FORMAT', backup_value='generic'
                )
                if setting_val and setting_val != 'auto':
                    return str(setting_val).lower()
            except Exception:
                pass

        return 'generic'

    def update_headers(
        self, headers: OrderedDict, context: dict, **kwargs
    ) -> OrderedDict:
        """Define column headers based on target supplier and export format."""
        context = context or {}
        export_format = (context.get('export_format') or '').lower()
        is_csv = (export_format == 'csv')

        supplier = (
            context.get('_resolved_supplier')
            or self.detect_supplier(None, context)
            or getattr(self, '_last_detected_supplier', 'generic')
        )

        include_headers = (
            context.get('export_include_headers')
            if 'export_include_headers' in context
            else context.get('include_headers', False)
        )

        if is_csv:
            if include_headers:
                header_val = (
                    'Mouser Part Number;Quantity 1'
                    if supplier == 'mouser'
                    else 'SKU;Quantity'
                )
                return OrderedDict({'SKU;Quantity': header_val})
            return OrderedDict({'SKU;Quantity': ''})

        # Multi-column formats (XLSX, TSV)
        if supplier == 'mouser':
            if include_headers:
                return OrderedDict({
                    'Mouser Part Number': 'Mouser Part Number',
                    'Quantity 1': 'Quantity 1',
                })
            return OrderedDict({'Mouser Part Number': '', 'Quantity 1': ''})

        if include_headers:
            return OrderedDict({'SKU': 'SKU', 'Quantity': 'Quantity'})
        return OrderedDict({'SKU': '', 'Quantity': ''})

    def export_data(
        self,
        queryset,
        serializer_class,
        headers,
        context,
        output=None,
        serializer_context=None,
        **kwargs,
    ) -> list:
        """Process purchase order lines and format data according to target supplier requirements."""
        context = context or {}
        export_format = (context.get('export_format') or '').lower()
        is_csv = (export_format == 'csv')

        supplier = self.detect_supplier(queryset, context)
        context['_resolved_supplier'] = supplier
        self._last_detected_supplier = supplier

        export_list = []
        if hasattr(queryset, 'count') and not isinstance(queryset, list):
            total_items = queryset.count()
        else:
            total_items = len(queryset) if queryset is not None else 0

        for idx, line in enumerate(queryset or []):
            sku = get_sku_for_line(line)
            qty_str = format_quantity(getattr(line, 'quantity', 0))

            if is_csv:
                # Semicolon-separated single column for supplier upload compatibility
                export_list.append({'SKU;Quantity': f"{sku};{qty_str}"})
            else:
                if supplier == 'mouser':
                    export_list.append({
                        'Mouser Part Number': sku,
                        'Quantity 1': qty_str,
                    })
                else:
                    export_list.append({
                        'SKU': sku,
                        'Quantity': qty_str,
                    })

            # Update database progress for long-running export tasks
            if output and total_items > 0:
                if idx % 25 == 0 or idx == total_items - 1:
                    try:
                        output.progress = int(100 * (idx + 1) / total_items)
                        output.save()
                    except Exception:
                        pass

        return export_list


# Backward compatibility aliases
TmePoExporterComboPlugin = SupplierPoExporterPlugin
MouserPoExporterComboPlugin = SupplierPoExporterPlugin
