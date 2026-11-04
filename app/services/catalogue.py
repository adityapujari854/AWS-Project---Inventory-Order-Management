"""Idempotent, fictional catalogue data for local InventoryHub demonstrations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product
from app.models.supplier import Supplier, SupplierProduct

CATEGORY_NAMES = (
    "Computer Accessories", "Computer Hardware", "Networking", "Monitors & Displays", "Audio", "Office Supplies",
    "Processors", "Graphics Cards", "Motherboards", "RAM & Memory", "Storage Devices", "Cooling & Fans",
)

SAMPLE_PRODUCTS = (
    ("WM-001", "Wireless Mouse", "Computer Accessories", "Ergonomic wireless mouse with quiet scroll wheel.", "29.99", "12.50", 10, 5, "Northstar Distribution"),
    ("KB-101", "Compact Mechanical Keyboard", "Computer Accessories", "Tenkeyless mechanical keyboard with white backlight.", "74.99", "38.00", 18, 6, "Northstar Distribution"),
    ("WB-102", "1080p USB Webcam", "Computer Accessories", "Full-HD USB webcam with privacy shutter.", "49.99", "24.00", 12, 4, "Northstar Distribution"),
    ("UD-103", "USB-C Docking Station", "Computer Accessories", "Dual-display USB-C dock with Ethernet and power delivery.", "119.99", "70.00", 7, 3, "Vertex Technology Supply"),
    ("LS-104", "Aluminum Laptop Stand", "Computer Accessories", "Adjustable ventilated stand for 13 to 16 inch laptops.", "39.99", "16.00", 22, 7, "Northstar Distribution"),
    ("SSD-201", "1TB NVMe SSD", "Computer Hardware", "PCIe Gen4 internal solid-state drive.", "89.99", "52.00", 14, 5, "Vertex Technology Supply"),
    ("RAM-202", "16GB DDR4 Memory Kit", "Computer Hardware", "Two-module desktop memory kit.", "54.99", "31.00", 16, 5, "Vertex Technology Supply"),
    ("PSU-203", "650W 80 Plus Bronze PSU", "Computer Hardware", "Reliable ATX power supply with quiet fan.", "79.99", "45.00", 6, 3, "Vertex Technology Supply"),
    ("FAN-204", "120mm PWM Case Fan", "Computer Hardware", "High-airflow PWM cooling fan.", "14.99", "6.50", 30, 10, "Vertex Technology Supply"),
    ("RTR-301", "Wi-Fi 6 Router", "Networking", "Dual-band Wi-Fi 6 router for small offices.", "109.99", "64.00", 8, 3, "Network Depot"),
    ("SWT-302", "8-Port Gigabit Switch", "Networking", "Unmanaged metal Gigabit Ethernet switch.", "44.99", "22.00", 15, 5, "Network Depot"),
    ("WAP-303", "Ceiling Wi-Fi Access Point", "Networking", "PoE-ready dual-band wireless access point.", "129.99", "76.00", 5, 3, "Network Depot"),
    ("CAB-304", "Cat6 Ethernet Cable 10m", "Networking", "Snagless Cat6 cable for office networking.", "12.99", "4.00", 40, 12, "Network Depot"),
    ("MON-401", "24-inch IPS Monitor", "Monitors & Displays", "Full-HD IPS monitor with adjustable stand.", "159.99", "102.00", 9, 4, "Display Works"),
    ("MON-402", "27-inch QHD Monitor", "Monitors & Displays", "QHD IPS monitor with USB-C input.", "279.99", "188.00", 6, 3, "Display Works"),
    ("MON-403", "34-inch Ultrawide Monitor", "Monitors & Displays", "Curved ultrawide monitor for multitasking.", "429.99", "305.00", 3, 2, "Display Works"),
    ("HDM-404", "2m HDMI 2.1 Cable", "Monitors & Displays", "Certified high-speed HDMI cable.", "19.99", "7.00", 25, 8, "Display Works"),
    ("AUD-501", "USB Noise-Cancelling Headset", "Audio", "Wired headset with boom microphone for calls.", "64.99", "35.00", 11, 4, "Soundline Wholesale"),
    ("AUD-502", "Bluetooth Speaker", "Audio", "Portable water-resistant Bluetooth speaker.", "59.99", "30.00", 13, 5, "Soundline Wholesale"),
    ("AUD-503", "Desktop USB Microphone", "Audio", "Cardioid USB microphone for meetings.", "84.99", "46.00", 7, 3, "Soundline Wholesale"),
    ("AUD-504", "3.5mm Audio Adapter", "Audio", "USB-C to 3.5mm audio adapter.", "11.99", "3.50", 35, 10, "Soundline Wholesale"),
    ("OFF-601", "A4 Copy Paper 500 Sheets", "Office Supplies", "Bright white multipurpose copier paper.", "8.99", "4.20", 50, 15, "Office Basics Co."),
    ("OFF-602", "Ergonomic Desk Chair", "Office Supplies", "Adjustable mesh-back office chair.", "189.99", "112.00", 4, 2, "Office Basics Co."),
    ("OFF-603", "Document Filing Tray", "Office Supplies", "Stackable letter-size desk tray.", "16.99", "7.00", 20, 6, "Office Basics Co."),
    ("OFF-604", "Permanent Marker Pack", "Office Supplies", "Pack of twelve low-odor markers.", "13.99", "5.00", 28, 8, "Office Basics Co."),
)

EXTRA_PRODUCTS = (
    ("CPU-701", "NovaCore i5 14400", "Processors", "Ten-core desktop processor for mainstream systems.", "229.99", "174.00", 8, 3, "Vertex Technology Supply"),
    ("CPU-702", "NovaCore i7 14700", "Processors", "Twenty-core desktop processor for creative workloads.", "379.99", "290.00", 5, 2, "Vertex Technology Supply"),
    ("CPU-703", "RyzenPro 5 7600", "Processors", "Six-core AM5 desktop processor.", "219.99", "165.00", 7, 3, "Vertex Technology Supply"),
    ("GPU-711", "AeroForce RTX 4060", "Graphics Cards", "8GB graphics card for 1080p workstations.", "329.99", "248.00", 4, 2, "Vertex Technology Supply"),
    ("GPU-712", "AeroForce RTX 4070", "Graphics Cards", "12GB graphics card for QHD gaming and design.", "599.99", "472.00", 3, 2, "Vertex Technology Supply"),
    ("GPU-713", "RenderPro A2000", "Graphics Cards", "Compact workstation graphics card with 12GB memory.", "449.99", "350.00", 2, 1, "Vertex Technology Supply"),
    ("MB-721", "B760 Micro-ATX Motherboard", "Motherboards", "DDR5 Micro-ATX motherboard with Wi-Fi 6.", "149.99", "104.00", 6, 2, "Vertex Technology Supply"),
    ("MB-722", "X670 ATX Motherboard", "Motherboards", "AM5 ATX motherboard with PCIe 5.0 storage.", "249.99", "185.00", 4, 2, "Vertex Technology Supply"),
    ("MB-723", "H610 Mini-ITX Motherboard", "Motherboards", "Compact motherboard for office mini PCs.", "109.99", "75.00", 5, 2, "Vertex Technology Supply"),
    ("MEM-731", "32GB DDR5 Memory Kit", "RAM & Memory", "Two-module DDR5 desktop memory kit.", "99.99", "61.00", 10, 4, "Vertex Technology Supply"),
    ("MEM-732", "8GB DDR4 SODIMM", "RAM & Memory", "Laptop memory upgrade module.", "29.99", "16.00", 18, 6, "Vertex Technology Supply"),
    ("MEM-733", "64GB DDR5 Memory Kit", "RAM & Memory", "High-capacity workstation memory kit.", "189.99", "122.00", 3, 2, "Vertex Technology Supply"),
    ("STO-741", "2TB SATA SSD", "Storage Devices", "2.5-inch SATA solid-state drive.", "129.99", "81.00", 9, 3, "Vertex Technology Supply"),
    ("STO-742", "4TB External Backup Drive", "Storage Devices", "USB external hard drive for local backups.", "119.99", "74.00", 6, 2, "Vertex Technology Supply"),
    ("STO-743", "512GB NVMe SSD", "Storage Devices", "Compact PCIe Gen4 upgrade drive.", "54.99", "30.00", 15, 5, "Vertex Technology Supply"),
    ("COL-751", "240mm Liquid CPU Cooler", "Cooling & Fans", "All-in-one liquid cooler for desktop processors.", "94.99", "56.00", 4, 2, "Vertex Technology Supply"),
    ("COL-752", "Tower CPU Air Cooler", "Cooling & Fans", "Quiet dual-heatpipe tower cooler.", "39.99", "19.00", 12, 4, "Vertex Technology Supply"),
    ("COL-753", "ARGB Fan 3-Pack", "Cooling & Fans", "Three PWM case fans with addressable lighting.", "44.99", "23.00", 9, 3, "Vertex Technology Supply"),
    ("ACC-761", "Wireless Presenter", "Computer Accessories", "USB receiver presentation clicker with laser pointer.", "24.99", "11.00", 16, 5, "Northstar Distribution"),
    ("NET-762", "2.5GbE USB Adapter", "Networking", "USB-C wired network adapter for modern laptops.", "34.99", "18.00", 11, 4, "Network Depot"),
    ("DSP-763", "27-inch 4K Monitor", "Monitors & Displays", "4K IPS monitor with ergonomic stand.", "349.99", "238.00", 4, 2, "Display Works"),
    ("AUD-764", "Wireless Conference Speaker", "Audio", "USB and Bluetooth speakerphone for meeting rooms.", "109.99", "66.00", 5, 2, "Soundline Wholesale"),
    ("OFF-765", "Cable Management Kit", "Office Supplies", "Reusable ties, clips and desk cable sleeves.", "18.99", "8.00", 24, 8, "Office Basics Co."),
    ("CAM-766", "4K USB Webcam", "Computer Accessories", "4K webcam with autofocus and privacy cover.", "99.99", "58.00", 6, 3, "Northstar Distribution"),
    ("NET-767", "16-Port Gigabit Switch", "Networking", "Rack-mountable unmanaged Gigabit Ethernet switch.", "94.99", "55.00", 5, 2, "Network Depot"),
)


def seed_sample_catalogue(db: Session) -> dict[str, int]:
    """Add only missing categories, suppliers, products, and links; never alter stock."""
    categories = {category.name: category for category in db.scalars(select(Category)).all()}
    added_categories = 0
    for name in CATEGORY_NAMES:
        if name not in categories:
            category = Category(name=name)
            db.add(category)
            categories[name] = category
            added_categories += 1
    db.flush()

    all_products = SAMPLE_PRODUCTS + EXTRA_PRODUCTS
    supplier_names = {row[-1] for row in all_products}
    suppliers = {supplier.name: supplier for supplier in db.scalars(select(Supplier)).all()}
    added_suppliers = 0
    for name in supplier_names:
        if name not in suppliers:
            supplier = Supplier(name=name)
            db.add(supplier)
            suppliers[name] = supplier
            added_suppliers += 1
    db.flush()

    existing_products = {product.sku: product for product in db.scalars(select(Product)).all()}
    added_products = 0
    added_links = 0
    for sku, name, category_name, description, price, cost, quantity, threshold, supplier_name in all_products:
        product = existing_products.get(sku)
        if product is None:
            category = categories[category_name]
            product = Product(
                sku=sku, name=name, description=description, category_id=category.id, category=category.name,
                price=price, cost=cost, quantity=quantity, reorder_threshold=threshold,
            )
            db.add(product)
            db.flush()
            existing_products[sku] = product
            added_products += 1
        elif product.category_id is None:
            category = categories[category_name]
            product.category_id = category.id
            product.category = category.name

        link_exists = db.scalar(
            select(SupplierProduct.id).where(
                SupplierProduct.supplier_id == suppliers[supplier_name].id, SupplierProduct.product_id == product.id
            )
        )
        if link_exists is None:
            db.add(SupplierProduct(supplier_id=suppliers[supplier_name].id, product_id=product.id))
            added_links += 1
    db.commit()
    return {"categories": added_categories, "suppliers": added_suppliers, "products": added_products, "supplier_links": added_links}
