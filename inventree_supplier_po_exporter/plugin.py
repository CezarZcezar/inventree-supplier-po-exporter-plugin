"""Supplier Purchase Order Exporter plugin for InvenTree.

Exports purchase order lines in the format of the TME / Mouser quick order and
cart upload tools (or a generic "part number, quantity" list).
"""

from __future__ import annotations

import logging
from collections import OrderedDict

from django.utils.translation import gettext_lazy as _

from rest_framework import serializers

from plugin import InvenTreePlugin
from plugin.mixins import DataExportMixin, SettingsMixin

from . import PLUGIN_VERSION
from .formatting import (
    AUTO,
    GENERIC,
    MOUSER,
    SUPPLIER_FORMATS,
    TME,
    CartLine,
    build_headers,
    build_rows,
    headers_without_header_row,
    merge_lines,
    supplier_from_name,
    to_decimal,
)

logger = logging.getLogger('inventree')

FORMAT_CHOICES = [
    (AUTO, _('Auto-detect from order supplier')),
    (TME, _('TME')),
    (MOUSER, _('Mouser')),
    (GENERIC, _('Generic (part number, quantity)')),
]


class SupplierPoExportOptionsSerializer(serializers.Serializer):
    """Options shown in the InvenTree export dialog."""

    export_supplier_format = serializers.ChoiceField(
        choices=FORMAT_CHOICES,
        default=AUTO,
        label=_('Supplier Format'),
        help_text=_('Target supplier format, or auto-detect it from the purchase order supplier'),
    )

    export_include_headers = serializers.BooleanField(
        default=False,
        label=_('Include Headers'),
        help_text=_('Include a column header row (leave off for a direct upload / copy & paste into the supplier cart)'),
    )


def supplier_company_setting(name: str) -> dict:
    """Setting for selecting the InvenTree company of a supplier."""
    return {
        'name': _('{name} company').format(name=name),
        'description': _('Company which uses the {name} format (optional - otherwise detected by name)').format(name=name),
        'model': 'company.company',
        'model_filters': {'is_supplier': True},
    }


def line_part_number(line) -> tuple[str, str]:
    """(part number, source) for a purchase order line.

    Order: supplier SKU, manufacturer MPN, internal IPN, part name, line reference.
    """
    supplier_part = line.part
    if supplier_part:
        if (supplier_part.SKU or '').strip():
            return supplier_part.SKU.strip(), 'sku'
        mp = supplier_part.manufacturer_part
        if mp and (mp.MPN or '').strip():
            return mp.MPN.strip(), 'mpn'
        part = supplier_part.part
        if part and (part.IPN or '').strip():
            return part.IPN.strip(), 'ipn'
        if part and (part.name or '').strip():
            return part.name.strip(), 'name'
    if (line.reference or '').strip():
        return line.reference.strip(), 'reference'
    return 'UNKNOWN_SKU', 'none'


class SupplierPoExporterPlugin(SettingsMixin, DataExportMixin, InvenTreePlugin):
    """Export purchase order lines for the TME / Mouser cart upload tools."""

    NAME = 'SupplierPurchaseOrderExporter'
    # The slug is kept, so existing plugin settings and activation are not lost
    SLUG = 'supplier-po-exporter'
    TITLE = _('Supplier Purchase Order Exporter')
    DESCRIPTION = _('Export purchase order lines formatted for the TME, Mouser and generic supplier cart imports')
    VERSION = PLUGIN_VERSION
    AUTHOR = 'Cezary Ćwikowski'
    PUBLISH_DATE = '2026-11-15'
    WEBSITE = 'https://github.com/CezarZcezar/inventree-supplier-po-exporter'
    LICENSE = 'MIT'
    MIN_VERSION = '1.0.0'

    ExportOptionsSerializer = SupplierPoExportOptionsSerializer

    SETTINGS = {
        'DEFAULT_SUPPLIER_FORMAT': {
            'name': _('Default supplier format'),
            'description': _('Supplier format preselected in the export dialog'),
            'choices': FORMAT_CHOICES,
            'default': AUTO,
        },
        'DEFAULT_INCLUDE_HEADERS': {
            'name': _('Include headers by default'),
            'description': _('Preselect "Include Headers" in the export dialog'),
            'validator': bool,
            'default': False,
        },
        'TME_COMPANY': supplier_company_setting('TME'),
        'MOUSER_COMPANY': supplier_company_setting('Mouser'),
        'QUANTITY_IN_PIECES': {
            'name': _('Quantity in pieces'),
            'description': _(
                'Multiply the order quantity (in supplier packs) by the pack quantity of the supplier part, '
                'as TME and Mouser expect pieces'
            ),
            'validator': bool,
            'default': True,
        },
        'MERGE_DUPLICATES': {
            'name': _('Merge duplicate part numbers'),
            'description': _('Sum the quantities of lines with the same part number into one line'),
            'validator': bool,
            'default': True,
        },
    }

    def __init__(self):
        """Initialise the plugin."""
        super().__init__()
        self._export_format = ''

    # ------------------------------------------------------------ options

    def get_export_options_serializer(self, **kwargs):
        """Export options, with the defaults taken from the plugin settings."""
        serializer = super().get_export_options_serializer(**kwargs)
        if serializer is not None:
            try:
                serializer.fields['export_supplier_format'].default = self.get_setting('DEFAULT_SUPPLIER_FORMAT') or AUTO
                serializer.fields['export_include_headers'].default = bool(self.get_setting('DEFAULT_INCLUDE_HEADERS'))
            except Exception:
                logger.exception('supplier-po-exporter: could not apply default export options')
        return serializer

    def supports_export(self, model_class, user=None, serializer_class=None, view_class=None, *args, **kwargs) -> bool:
        """Only purchase order lines are supported."""
        from order.models import PurchaseOrderLineItem

        return isinstance(model_class, type) and issubclass(model_class, PurchaseOrderLineItem)

    def generate_filename(self, model_class, export_format: str) -> str:
        """File name of the export.

        InvenTree does not pass the export format to export_data(), but calls this
        method first (in the same process), so the format is remembered here.
        """
        from InvenTree.helpers import current_date

        self._export_format = str(export_format or '').lower()
        return f'Supplier_PO_Export_{current_date().isoformat()}.{self._export_format}'

    # ------------------------------------------------------------- export

    def detect_supplier(self, queryset, context: dict) -> str:
        """Supplier format: explicit option, else the supplier of the order."""
        fmt = str(context.get('export_supplier_format') or AUTO).lower()
        if fmt in SUPPLIER_FORMATS:
            return fmt

        first = queryset.select_related('order__supplier').first() if queryset is not None else None
        supplier = first.order.supplier if first and first.order else None
        if supplier is None:
            return GENERIC

        for fmt, key in ((TME, 'TME_COMPANY'), (MOUSER, 'MOUSER_COMPANY')):
            try:
                configured = self.get_setting(key)
            except Exception:
                configured = None
            if configured and str(configured) == str(supplier.pk):
                return fmt

        return supplier_from_name(supplier.name) or GENERIC

    def cart_lines(self, queryset, output=None) -> list[CartLine]:
        """Part numbers and quantities of the purchase order lines."""
        in_pieces = bool(self.get_setting('QUANTITY_IN_PIECES', backup_value=True))
        queryset = queryset.select_related('part', 'part__manufacturer_part', 'part__part')

        lines = []
        for index, line in enumerate(queryset, start=1):
            sku, source = line_part_number(line)
            quantity = to_decimal(line.quantity)
            if in_pieces and line.part and line.part.pack_quantity_native:
                quantity *= to_decimal(line.part.pack_quantity_native)
            if source != 'sku':
                logger.info('supplier-po-exporter: line %s has no supplier SKU, using %s "%s"', line.pk, source, sku)
            lines.append(CartLine(sku, quantity, source))

            # InvenTree shows progress as "progress / total" (number of rows)
            if output is not None and (index % 25 == 0):
                output.progress = index
                output.save()

        if output is not None:
            output.progress = len(lines)
            output.save()

        return lines

    def export_data(self, queryset, serializer_class, headers, context, output=None, serializer_context=None, **kwargs) -> list:
        """Build the export rows (InvenTree calls update_headers() afterwards)."""
        supplier = self.detect_supplier(queryset, context)
        csv = self._export_format == 'csv'

        lines = self.cart_lines(queryset, output)
        if self.get_setting('MERGE_DUPLICATES', backup_value=True):
            lines = merge_lines(lines)

        rows = build_rows(lines, supplier, csv)
        headers = build_headers(supplier, csv)

        include_headers = context.get('export_include_headers', False)
        if not include_headers:
            headers, rows = headers_without_header_row(rows, headers)

        # update_headers() receives the same context dict
        context['_headers'] = headers
        return rows

    def update_headers(self, headers: OrderedDict, context: dict, **kwargs) -> OrderedDict:
        """Columns of the export (computed in export_data)."""
        return OrderedDict(context.get('_headers') or build_headers(GENERIC, False))
