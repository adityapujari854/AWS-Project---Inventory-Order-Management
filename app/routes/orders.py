"""Order creation, status transitions, and stock handling."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.inventory import InventoryMovement, MovementType
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product, ProductStatus
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate
from app.security import require_admin, verify_csrf

router = APIRouter(prefix="/api/orders", tags=["orders"], dependencies=[Depends(require_admin), Depends(verify_csrf)])

ALLOWED_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


def get_order_or_404(order_id: int, db: Session) -> Order:
    order = db.scalar(select(Order).options(selectinload(Order.items)).where(Order.id == order_id))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)) -> Order:
    requested_quantities: dict[int, int] = {}
    for item in payload.items:
        requested_quantities[item.product_id] = requested_quantities.get(item.product_id, 0) + item.quantity

    products = {
        product.id: product
        for product in db.scalars(select(Product).where(Product.id.in_(requested_quantities))).all()
    }
    if len(products) != len(requested_quantities):
        raise HTTPException(status_code=404, detail="One or more products were not found")
    if any(product.status == ProductStatus.ARCHIVED for product in products.values()):
        raise HTTPException(status_code=409, detail="Archived products cannot be ordered")

    order = Order(order_number="PENDING", customer_name=payload.customer_name, customer_reference=payload.customer_reference)
    db.add(order)
    db.flush()
    order.order_number = f"ORD-{order.id:06d}"

    total = Decimal("0.00")
    for product_id, quantity in requested_quantities.items():
        product = products[product_id]
        line_total = product.price * quantity
        total += line_total
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                quantity=quantity,
                unit_price=product.price,
                line_total=line_total,
            )
        )
    order.total = total
    db.commit()
    return get_order_or_404(order.id, db)


@router.get("", response_model=list[OrderRead])
def list_orders(db: Session = Depends(get_db)) -> list[Order]:
    return db.scalars(select(Order).options(selectinload(Order.items)).order_by(Order.created_at.desc(), Order.id.desc())).all()


@router.get("/{order_id}", response_model=OrderRead)
def get_order(order_id: int, db: Session = Depends(get_db)) -> Order:
    return get_order_or_404(order_id, db)


@router.patch("/{order_id}/status", response_model=OrderRead)
def update_order_status(order_id: int, payload: OrderStatusUpdate, db: Session = Depends(get_db)) -> Order:
    order = get_order_or_404(order_id, db)
    if payload.status not in ALLOWED_TRANSITIONS[order.status]:
        raise HTTPException(status_code=409, detail=f"Cannot change {order.status.value} order to {payload.status.value}")

    if payload.status == OrderStatus.PROCESSING:
        product_ids = [item.product_id for item in order.items]
        products = {
            product.id: product
            for product in db.scalars(select(Product).where(Product.id.in_(product_ids)).with_for_update()).all()
        }
        for item in order.items:
            product = products.get(item.product_id)
            if product is None or product.status == ProductStatus.ARCHIVED or product.quantity < item.quantity:
                raise HTTPException(status_code=422, detail=f"Insufficient stock for {item.product_name}")
        for item in order.items:
            product = products[item.product_id]
            product.quantity -= item.quantity
            db.add(
                InventoryMovement(
                    product=product,
                    movement_type=MovementType.ORDER_OUT,
                    quantity_change=-item.quantity,
                    quantity_after=product.quantity,
                    note=f"Order {order.order_number}",
                )
            )
        order.stock_deducted = True

    if payload.status == OrderStatus.CANCELLED and order.stock_deducted:
        products = {
            product.id: product
            for product in db.scalars(select(Product).where(Product.id.in_([item.product_id for item in order.items]))).all()
        }
        for item in order.items:
            product = products[item.product_id]
            product.quantity += item.quantity
            db.add(
                InventoryMovement(
                    product=product,
                    movement_type=MovementType.ORDER_RETURN,
                    quantity_change=item.quantity,
                    quantity_after=product.quantity,
                    note=f"Cancelled order {order.order_number}",
                )
            )
        order.stock_deducted = False

    order.status = payload.status
    db.commit()
    return get_order_or_404(order.id, db)

