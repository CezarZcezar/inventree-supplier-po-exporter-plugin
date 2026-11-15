"""Supplier cart formats for purchase order lines.

This module has no Django / InvenTree imports, so it can be unit tested on its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

TME = 'tme'
MOUSER = 'mouser'
GENERIC = 'generic'
AUTO = 'auto'

SUPPLIER_FORMATS = (TME, MOUSER, GENERIC)

#: Column names per supplier format: (part number column, quantity column)
COLUMNS = {
    TME: ('SKU', 'Quantity'),
    MOUSER: ('Mouser Part Number', 'Quantity 1'),
    GENERIC: ('SKU', 'Quantity'),
}

#: Key of the single column used for the semicolon separated CSV format
CSV_KEY = 'line'

# Supplier names are matched as whole words ("TME", "TME Electronic Components", "Mouser Electronics")
NAME_PATTERNS = {
    TME: re.compile(r'\btme\b', re.IGNORECASE),
    MOUSER: re.compile(r'\bmouser\b', re.IGNORECASE),
}


def supplier_from_name(name: str | None) -> str | None:
    """Detect the supplier format from a company name."""
    for fmt, pattern in NAME_PATTERNS.items():
        if pattern.search(name or ''):
            return fmt
    return None


def to_decimal(value) -> Decimal:
    """Convert a quantity to Decimal (0 for invalid values)."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)


def format_quantity(quantity) -> str:
    """Format a quantity without trailing zeros: 10.000 -> '10', 2.50 -> '2.5'."""
    if quantity is None:
        return '0'
    value = to_decimal(quantity)
    if value == value.to_integral_value():
        return str(value.quantize(Decimal(1)))
    return format(value.normalize(), 'f')


def numeric_quantity(quantity):
    """Quantity as int (whole numbers) or float, for spreadsheet cells."""
    value = to_decimal(quantity)
    return int(value) if value == value.to_integral_value() else float(value)


@dataclass
class CartLine:
    """One line of the supplier cart."""

    sku: str
    quantity: Decimal
    #: Where the part number came from: 'sku', 'mpn', 'ipn', 'name', 'reference' or 'none'
    source: str = 'sku'


def merge_lines(lines: list[CartLine]) -> list[CartLine]:
    """Sum the quantities of lines with the same part number (keeps the order)."""
    merged: dict[str, CartLine] = {}
    for line in lines:
        if line.sku in merged:
            merged[line.sku].quantity += line.quantity
        else:
            merged[line.sku] = CartLine(line.sku, line.quantity, line.source)
    return list(merged.values())


def build_rows(lines: list[CartLine], supplier: str, csv: bool) -> list[dict]:
    """Rows for the export.

    CSV: a single column with "part number;quantity" (the format of the TME and
    Mouser quick order / upload tools, independent of the comma / semicolon setting
    of the spreadsheet). XLSX / TSV etc.: two columns, quantity as a number.
    """
    sku_col, qty_col = COLUMNS.get(supplier, COLUMNS[GENERIC])
    if csv:
        return [{CSV_KEY: f'{line.sku};{format_quantity(line.quantity)}'} for line in lines]
    return [{sku_col: line.sku, qty_col: numeric_quantity(line.quantity)} for line in lines]


def build_headers(supplier: str, csv: bool) -> dict:
    """{column key: header label} for the export."""
    sku_col, qty_col = COLUMNS.get(supplier, COLUMNS[GENERIC])
    if csv:
        return {CSV_KEY: f'{sku_col};{qty_col}'}
    return {sku_col: sku_col, qty_col: qty_col}


def headers_without_header_row(rows: list[dict], headers: dict) -> tuple[dict, list[dict]]:
    """Make the file start directly with the data.

    InvenTree always writes a header row. To export without one, the first data
    row is used as the "header" and removed from the data.
    """
    if not rows:
        return {key: '' for key in headers}, []
    first = rows[0]
    return {key: first.get(key, '') for key in headers}, rows[1:]
