"""Unit tests for the supplier cart formats (no InvenTree / database needed).

Run with:  python -m unittest discover -s tests -v
"""

import unittest
from decimal import Decimal as D

from inventree_supplier_po_exporter.formatting import (
    CSV_KEY,
    GENERIC,
    MOUSER,
    TME,
    CartLine,
    build_headers,
    build_rows,
    format_quantity,
    headers_without_header_row,
    merge_lines,
    numeric_quantity,
    supplier_from_name,
)


class QuantityTests(unittest.TestCase):
    def test_format_quantity(self):
        self.assertEqual(format_quantity(D('10.000')), '10')
        self.assertEqual(format_quantity(D('2.50')), '2.5')
        self.assertEqual(format_quantity(15.0), '15')
        self.assertEqual(format_quantity(D('1E+3')), '1000')
        self.assertEqual(format_quantity(None), '0')

    def test_numeric_quantity(self):
        self.assertEqual(numeric_quantity(D('500.0000')), 500)
        self.assertIsInstance(numeric_quantity(D('500.0000')), int)
        self.assertEqual(numeric_quantity(D('2.5')), 2.5)


class SupplierDetectionTests(unittest.TestCase):
    def test_whole_words(self):
        self.assertEqual(supplier_from_name('TME'), TME)
        self.assertEqual(supplier_from_name('TME Electronic Components'), TME)
        self.assertEqual(supplier_from_name('Mouser Electronics'), MOUSER)
        self.assertIsNone(supplier_from_name('Digikey'))
        # 'tme' inside another word must not match
        self.assertIsNone(supplier_from_name('Atmel Distribution / Stmelec'))
        self.assertIsNone(supplier_from_name(None))


class RowTests(unittest.TestCase):
    lines = [CartLine('RC0603FR-0710KL', D(500)), CartLine('CC0603KRX7R9BB104', D('2.5'))]

    def test_csv_single_column(self):
        rows = build_rows(self.lines, TME, csv=True)
        self.assertEqual(rows, [{CSV_KEY: 'RC0603FR-0710KL;500'}, {CSV_KEY: 'CC0603KRX7R9BB104;2.5'}])
        self.assertEqual(build_headers(TME, csv=True), {CSV_KEY: 'SKU;Quantity'})
        self.assertEqual(build_headers(MOUSER, csv=True), {CSV_KEY: 'Mouser Part Number;Quantity 1'})

    def test_spreadsheet_columns(self):
        rows = build_rows(self.lines, MOUSER, csv=False)
        self.assertEqual(rows[0], {'Mouser Part Number': 'RC0603FR-0710KL', 'Quantity 1': 500})
        self.assertEqual(build_rows(self.lines, GENERIC, csv=False)[1], {'SKU': 'CC0603KRX7R9BB104', 'Quantity': 2.5})

    def test_no_header_row(self):
        rows = build_rows(self.lines, TME, csv=True)
        headers, data = headers_without_header_row(rows, build_headers(TME, csv=True))
        # The first data row becomes the "header", so the file starts with the data
        self.assertEqual(headers, {CSV_KEY: 'RC0603FR-0710KL;500'})
        self.assertEqual(data, [{CSV_KEY: 'CC0603KRX7R9BB104;2.5'}])

    def test_no_header_row_empty(self):
        self.assertEqual(headers_without_header_row([], {CSV_KEY: 'x'}), ({CSV_KEY: ''}, []))

    def test_merge_duplicates(self):
        merged = merge_lines([CartLine('A', D(1)), CartLine('B', D(2)), CartLine('A', D(3))])
        self.assertEqual([(l.sku, l.quantity) for l in merged], [('A', D(4)), ('B', D(2))])


if __name__ == '__main__':
    unittest.main()
