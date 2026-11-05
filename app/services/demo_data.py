"""Development-only, repeatable fictional data for a populated InventoryHub demo."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import InventoryMovement, MovementType
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.supplier import Supplier, SupplierProduct
from app.services.catalogue import seed_sample_catalogue


DEMO_PREFIX = "DEMO-2026-"
DEMO_NOTE = "Demo opening receipt"
SUPPLIER_DETAILS = {
    "Northstar Distribution": ("Maya Chen", "maya.chen@northstar-demo.example", "+1-555-0101", "1200 Aurora Way, Portland, OR"),
    "Vertex Technology Supply": ("Jordan Patel", "jordan.patel@vertex-demo.example", "+1-555-0102", "88 Circuit Park, Austin, TX"),
    "Network Depot": ("Avery Brooks", "avery.brooks@networkdepot-demo.example", "+1-555-0103", "410 Link Avenue, Denver, CO"),
    "Display Works": ("Riley Morgan", "riley.morgan@displayworks-demo.example", "+1-555-0104", "29 Pixel Street, Seattle, WA"),
    "Soundline Wholesale": ("Taylor Kim", "taylor.kim@soundline-demo.example", "+1-555-0105", "715 Studio Road, Nashville, TN"),
    "Office Basics Co.": ("Casey Rivera", "casey.rivera@officebasics-demo.example", "+1-555-0106", "64 Paper Mill Lane, Chicago, IL"),
    "Metro Cable & Power": ("Morgan Lee", "morgan.lee@metro-demo.example", "+1-555-0107", "920 Connector Drive, Phoenix, AZ"),
    "Core Components Lab": ("Jamie Singh", "jamie.singh@core-demo.example", "+1-555-0108", "18 Silicon Court, San Jose, CA"),
    "Ergo Workplace Supply": ("Alex Monroe", "alex.monroe@ergo-demo.example", "+1-555-0109", "31 Workspace Plaza, Boston, MA"),
    "ClearView Peripherals": ("Sam Okafor", "sam.okafor@clearview-demo.example", "+1-555-0110", "300 Vision Boulevard, Raleigh, NC"),
}
CUSTOMERS = (
    "Bluebird Creative Studio", "Cedar Ridge Consulting", "Horizon Legal Group", "Northline Architects",
    "Oak & Iron Workshop", "Pioneer Learning Center", "Quartz Health Systems", "Redwood Media Co.",
    "Summit Accounting Partners", "Tidal Labs", "Union Square Design", "Vista Operations Ltd.",
)
# These targets are applied only to an untouched catalogue profile in a local development database.
STOCK_PROFILE = {"GPU-713": 0, "MON-403": 0, "CPU-702": 0, "PSU-203": 3, "WAP-303": 3,
                 "MB-722": 2, "AUD-503": 3, "COL-751": 2, "CAM-766": 3,
                 "OFF-601": 78, "CAB-304": 64, "AUD-504": 54, "FAN-204": 47}


def _order_blueprints(products: list[Product]) -> list[tuple[str, list[tuple[Product, int]], OrderStatus, datetime]]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    statuses = ([OrderStatus.DELIVERED] * 14 + [OrderStatus.SHIPPED] * 10 + [OrderStatus.PROCESSING] * 6
                + [OrderStatus.PENDING] * 5 + [OrderStatus.CANCELLED] * 5)
    blueprints = []
    for index, status in enumerate(statuses, start=1):
        first = products[(index * 3) % len(products)]
        second = products[(index * 7 + 5) % len(products)]
        items = [(first, 1 + index % 3), (second, 1 + (index // 3) % 2)]
        # Several fast-moving staples produce meaningful advisor demand signals.
        if index % 4 == 0:
            items.append((products[0], 2 + index % 3))
        created_at = now - timedelta(days=180 - round((index - 1) * 4.5))
        blueprints.append((f"{DEMO_PREFIX}{index:04d}", items, status, created_at))
    return blueprints


def _ensure_suppliers(db: Session, products: list[Product]) -> int:
    suppliers = {supplier.name: supplier for supplier in db.scalars(select(Supplier)).all()}
    added = 0
    for name, details in SUPPLIER_DETAILS.items():
        supplier = suppliers.get(name)
        if supplier is None:
            supplier = Supplier(name=name, contact_name=details[0], email=details[1], phone=details[2], address=details[3])
            db.add(supplier)
            suppliers[name] = supplier
            added += 1
        else:
            for field, value in zip(("contact_name", "email", "phone", "address"), details):
                if not getattr(supplier, field):
                    setattr(supplier, field, value)
    db.flush()
    extras = [suppliers[name] for name in ("Metro Cable & Power", "Core Components Lab", "Ergo Workplace Supply", "ClearView Peripherals")]
    existing = {(row.supplier_id, row.product_id) for row in db.scalars(select(SupplierProduct)).all()}
    for index, product in enumerate(products):
        supplier = extras[index % len(extras)]
        if (supplier.id, product.id) not in existing:
            db.add(SupplierProduct(supplier_id=supplier.id, product_id=product.id))
    return added


def _can_apply_profile(db: Session, products: list[Product]) -> bool:
    return not db.scalar(select(InventoryMovement.id).limit(1)) and not db.scalar(select(Order.id).limit(1)) and len(products) == 50


def seed_demo_data(db: Session) -> dict[str, int]:
    """Create new demo records only; reruns never duplicate orders or movements.

    Existing product records are retained. An inventory profile is applied only to
    a fresh, catalogue-only database; otherwise movement history reconciles to
    the existing on-hand quantities without altering them.
    """
    catalogue_result = seed_sample_catalogue(db)
    products = list(db.scalars(select(Product).order_by(Product.sku)).all())
    if len(products) < 50:
        raise RuntimeError("The complete 50-product catalogue is required before demo data can be created.")
    suppliers_added = _ensure_suppliers(db, products)
    apply_profile = _can_apply_profile(db, products)
    if apply_profile:
        for product in products:
            if product.sku in STOCK_PROFILE:
                product.quantity = STOCK_PROFILE[product.sku]

    blueprints = _order_blueprints(products)
    existing_numbers = set(db.scalars(select(Order.order_number).where(Order.order_number.like(f"{DEMO_PREFIX}%"))).all())
    new_orders = 0
    net_changes: dict[int, int] = defaultdict(int)
    events: dict[int, list[tuple[datetime, MovementType, int, str]]] = defaultdict(list)
    for number, items, status, created_at in blueprints:
        deducted = status in (OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.DELIVERED)
        if number not in existing_numbers:
            total = sum((product.price * quantity for product, quantity in items), Decimal("0.00"))
            order = Order(order_number=number, customer_name=CUSTOMERS[(new_orders + len(existing_numbers)) % len(CUSTOMERS)],
                          customer_reference=f"PO-DEMO-{number[-4:]}", status=status, total=total, stock_deducted=deducted,
                          created_at=created_at, updated_at=created_at)
            db.add(order)
            db.flush()
            for product, quantity in items:
                order.items.append(OrderItem(product_id=product.id, product_name=product.name, quantity=quantity,
                                             unit_price=product.price, line_total=product.price * quantity))
            new_orders += 1
        for product, quantity in items:
            if deducted:
                events[product.id].append((created_at, MovementType.ORDER_OUT, -quantity, f"Order {number}"))
                net_changes[product.id] -= quantity
        if status == OrderStatus.CANCELLED:
            # A cancelled order is represented as an issued item followed by a returned item, with zero net stock effect.
            for product, quantity in items:
                events[product.id].append((created_at, MovementType.ORDER_OUT, -quantity, f"Order {number} cancelled"))
                events[product.id].append((created_at + timedelta(hours=1), MovementType.ORDER_RETURN, quantity, f"Cancelled order {number}"))

    needs_movements = any(not db.scalar(select(InventoryMovement.id).where(
        InventoryMovement.product_id == product.id, InventoryMovement.note.like(f"{DEMO_NOTE}%")
    )) for product in products)
    if needs_movements:
        supplier_names = list(SUPPLIER_DETAILS)
        for index, product in enumerate(products):
            if db.scalar(select(InventoryMovement.id).where(InventoryMovement.product_id == product.id, InventoryMovement.note.like(f"{DEMO_NOTE}%"))):
                continue
            # Add a small manual reconciliation event for an auditable adjustment history.
            if index % 9 == 0:
                adjustment_at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=90 - index)
                events[product.id].append((adjustment_at, MovementType.ADJUSTMENT, 2, "Demo cycle-count correction"))
                net_changes[product.id] += 2
            net_after_events = net_changes[product.id]
            opening = product.quantity - net_after_events
            if opening < 0:
                raise RuntimeError(f"Demo history would make stock negative for {product.sku}.")
            first_event = min((event[0] for event in events[product.id]), default=datetime.now(timezone.utc))
            timeline = [(first_event - timedelta(days=2), MovementType.STOCK_IN, opening,
                         f"{DEMO_NOTE} from {supplier_names[index % len(supplier_names)]}")] + events[product.id]
            running = 0
            for occurred_at, movement_type, change, note in sorted(timeline, key=lambda row: row[0]):
                running += change
                db.add(InventoryMovement(product_id=product.id, movement_type=movement_type, quantity_change=change,
                                         quantity_after=running, note=note, created_at=occurred_at))

    db.commit()
    return {"catalogue_products_added": catalogue_result["products"], "suppliers_added": suppliers_added,
            "orders_added": new_orders, "inventory_profile_applied": int(apply_profile), "total_demo_orders": len(blueprints)}
