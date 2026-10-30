import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="inventree-supplier-po-exporter",
    version="2.0.0",
    author="Cezary",
    author_email="cwikowski.czarek123@gmail.com",
    description="InvenTree plugin for exporting Purchase Orders (TME, Mouser, and Generic).",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/CezarZcezar/inventree-supplier-po-exporter",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        "tablib",
    ],
    entry_points={
        "inventree_plugins": [
            "SupplierPoExporterPlugin = inventree_supplier_po_exporter.exporter:SupplierPoExporterPlugin",
        ]
    },
)
