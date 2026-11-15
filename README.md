# InvenTree Supplier Purchase Order Exporter

[![InvenTree Plugin](https://img.shields.io/badge/InvenTree-Plugin-blue.svg)](https://inventree.org)
[![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An [InvenTree](https://inventree.org) data export plugin (**SupplierPurchaseOrderExporter**, slug
`supplier-po-exporter`) which exports the lines of a Purchase Order in the format of the
**TME** and **Mouser** quick order / cart upload tools, or as a generic *part number, quantity* list.

---

## Features

- **Supplier formats**
  - **CSV** – one `part number;quantity` line per item (the quick order format of TME and Mouser),
    independent of the comma / semicolon setting of your spreadsheet.
  - **XLSX / TSV** – two columns, quantity as a number: `SKU`, `Quantity` (TME, generic) or
    `Mouser Part Number`, `Quantity 1` (Mouser BOM import).
- **Auto-detection** of the format from the order supplier: the companies selected in the plugin
  settings, otherwise the supplier name (`TME…`, `Mouser…`, matched as whole words).
- **Without header row** (default) – the file starts directly with the data, ready to upload or paste.
- **Quantity in pieces** – InvenTree stores order quantities in supplier *packs*; the quantity is
  multiplied by the pack quantity of the supplier part (e.g. 5 packs × 100 = 500), as TME and Mouser
  expect pieces. Can be switched off.
- **Merging** of lines with the same part number (quantities summed).
- **Part number** – supplier SKU; if missing: manufacturer MPN, then IPN, part name, line reference
  (a line without SKU is logged, as the supplier may not find it).

---

## Usage

1. Open a **Purchase Order** → **Line Items** tab → **Export** (download icon) in the table toolbar.
2. **Export Format**: CSV or Excel; **Export Plugin**: *SupplierPurchaseOrderExporter*.
3. **Supplier Format**: auto-detect, TME, Mouser or generic; **Include Headers** if needed.
4. Upload the file in the supplier cart (TME: *Quick order / Import from file*, Mouser: *BOM import*).

## Plugin Settings

| Setting | Default | Description |
|---|---|---|
| Default supplier format | Auto-detect | Preselected in the export dialog |
| Include headers by default | off | Preselected in the export dialog |
| TME company / Mouser company | – | Companies which use the TME / Mouser format (otherwise detected by name) |
| Quantity in pieces | on | Multiply the order quantity by the pack quantity of the supplier part |
| Merge duplicate part numbers | on | One line per part number |

---

## Installation

### Local Docker deployment

```bash
./deploy.sh            # copies the plugin to ../inventree-data/plugins/supplier_po_exporter and restarts InvenTree
```

### Via Git / `plugins.txt`

```
inventree-supplier-po-exporter@git+https://github.com/CezarZcezar/inventree-supplier-po-exporter.git
```

Then activate the plugin under **Settings → Plugins**.

---

## Notes

InvenTree always writes a header row and does not pass the export format to the plugin. The plugin
therefore remembers the format in `generate_filename()` (called first) and, for exports without
headers, uses the first data row as the "header".

## Tests

The formatting logic has no InvenTree dependency and is tested on its own:

```bash
python -m unittest discover -s tests -v
```

## License

MIT – see [LICENSE](LICENSE).
