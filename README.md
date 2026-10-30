# InvenTree Supplier Purchase Order Exporter

[![InvenTree Plugin](https://img.shields.io/badge/InvenTree-Plugin-blue.svg)](https://inventree.org)
[![Python](https://img.shields.io/badge/Python-3.9%2B-brightgreen.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A unified **InvenTree** data export plugin that exports Purchase Order Line Items formatted specifically for direct cart, quick order, and BOM imports into electronic component supplier portals—including **TME**, **Mouser**, and **Generic** suppliers.

---

## Features

- **Unified Plugin**: Replaces fragmented single-supplier exporters with a single, maintainable InvenTree plugin (`SupplierPoExporterPlugin`, slug `supplier-po-exporter`).
- **Smart Auto-Detection**: Automatically identifies the supplier from the Purchase Order metadata (`order.supplier.name`). If the order is for TME, it outputs TME format; if for Mouser, it outputs Mouser format.
- **Interactive UI Export Options**: Fully integrated into the InvenTree export modal (`ExportOptionsSerializer`), allowing users to manually override the target supplier format or toggle column headers.
- **Supplier-Compatible CSV/XLSX Formatting**:
  - **TME**: Semicolon-delimited (`SKU;Quantity`) CSV output tailored for TME Quick Orders upload tool (circumventing standard comma-delimiter issues).
  - **Mouser**: Standard Mouser BOM columns (`Mouser Part Number`, `Quantity 1`) for Excel and semicolon CSV for Mouser BOM/Cart upload.
  - **Generic**: Clean standard SKU and Quantity pairing for any other supplier or ERP system.
- **Header Toggle**: Allows excluding header rows (default) for seamless copy-pasting directly into supplier order forms without causing header parse errors.
- **Robust 5-Step SKU Resolution**:
  1. `SupplierPart.SKU` (supplier order code)
  2. `ManufacturerPart.MPN` (manufacturer part number)
  3. `Part.IPN` (internal part number)
  4. `Part.name` (part name)
  5. Line item reference / description fallback
- **Quantity Normalization**: Formats numbers cleanly without trailing decimal zeroes (e.g., `10.0000` becomes `10`, `2.50` becomes `2.5`).
- **Live Progress Tracking**: Informs InvenTree's asynchronous background task worker of export progress for large orders.

---

## Installation

### Method 1: Local Docker Volume (Recommended)

InvenTree Docker deployments automatically discover plugins placed in the mounted `inventree-data/plugins/` directory:

1. Copy the plugin package folder into your persistent InvenTree plugins directory:
   ```bash
   mkdir -p inventree-data/plugins/supplier_po_exporter
   cp -r inventree-supplier-po-exporter/inventree_supplier_po_exporter/* inventree-data/plugins/supplier_po_exporter/
   ```

2. Restart the InvenTree server and worker containers:
   ```bash
   docker compose restart inventree-server inventree-worker
   ```

### Method 2: Via Pip / `plugins.txt`

Add the package to your `plugins.txt` file or install it directly inside the environment:

```bash
pip install /path/to/inventree-supplier-po-exporter
```

Then reload the plugins in InvenTree.

---

## Usage

1. Open any **Purchase Order** in InvenTree (`/purchasing/purchase-order/<id>/`).
2. Go to the **Order Items** tab.
3. Click the **Export** button in the table header.
4. In the Export dialog:
   - **Exporter Plugin**: Select **Supplier Purchase Order Exporter**.
   - **Format**: Select **CSV** or **XLSX**.
   - **Supplier Format** (under custom options):
     - `Auto-detect from Order` (Default — automatically detects TME or Mouser from PO supplier).
     - `TME`
     - `Mouser`
     - `Generic (SKU, Quantity)`
   - **Include Headers**: Leave unchecked (default) for direct upload compatibility, or check to include column labels.
5. Click **Download** or **Export**. The exported file is ready to upload directly into the supplier's web cart.

---

## Plugin Settings

Global default settings can be configured in InvenTree Admin Center (**System Settings** &rarr; **Plugins** &rarr; **Supplier PO Exporter**):

| Setting Key | Type | Default | Description |
|---|---|---|---|
| `DEFAULT_SUPPLIER_FORMAT` | Choice | `auto` | Default supplier format (`auto`, `tme`, `mouser`, `generic`). |
| `DEFAULT_INCLUDE_HEADERS` | Boolean | `False` | Whether to include header labels in the first row by default. |

---

## Supplier Formats Overview

| Supplier | CSV Format | XLSX Columns | Notes |
|---|---|---|---|
| **TME** | `SKU;Quantity` (semicolon) | `SKU`, `Quantity` | Tested with TME Quick Orders tool. |
| **Mouser** | `SKU;Quantity` (semicolon) | `Mouser Part Number`, `Quantity 1` | Matches Mouser official BOM import template. |
| **Generic** | `SKU;Quantity` (semicolon) | `SKU`, `Quantity` | Clean key-value pairs suitable for general use. |

---

## Automated Tests

The plugin includes a test suite covering SKU resolution, quantity formatting, supplier auto-detection, header mapping, and export generation:

```bash
# Run tests using Python's unittest runner
python3 -m unittest discover -s tests
```

Tests run standalone with zero external database dependencies and do not pollute production databases.

---

## Backward Compatibility

For installations migrating from earlier versions, the plugin provides backwards-compatible aliases:
- `TmePoExporterComboPlugin`
- `MouserPoExporterComboPlugin`

Both point to `SupplierPoExporterPlugin`.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
