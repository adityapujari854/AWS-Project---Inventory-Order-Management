"""Inventory operation and movement-history endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.inventory import InventoryMovement, MovementType
from app.models.product import Product, ProductStatus
from app.routes.products import get_product_or_404
from app.schemas.inventory import InventoryMovementRead, StockAdjustment, StockChange
from app.schemas.product import ProductRead

router = APIRouter(prefix="/api/products/{product_id}/inventory", tags=["inventory"])


def apply_movement(
    product: Product, movement_type: MovementType, quantity_change: int, note: str | None, db: Session
) -> Product:
    new_quantity = product.quantity + quantity_change
    if new_quantity < 0:
        raise HTTPException(status_code=422, detail="Insufficient stock for this operation")
    product.quantity = new_quantity
    db.add(
        InventoryMovement(
            product=product,
            movement_type=movement_type,
            quantity_change=quantity_change,
            quantity_after=new_quantity,
            note=note,
        )
    )
    db.commit()
    db.refresh(product)
    return product


def active_product(product_id: int, db: Session) -> Product:
    product = get_product_or_404(product_id, db)
    if product.status == ProductStatus.ARCHIVED:
        raise HTTPException(status_code=409, detail="Archived products cannot have stock changes")
    return product


@router.post("/stock-in", response_model=ProductRead, status_code=status.HTTP_200_OK)
def stock_in(product_id: int, payload: StockChange, db: Session = Depends(get_db)) -> Product:
    return apply_movement(active_product(product_id, db), MovementType.STOCK_IN, payload.quantity, payload.note, db)


@router.post("/stock-out", response_model=ProductRead)
def stock_out(product_id: int, payload: StockChange, db: Session = Depends(get_db)) -> Product:
    return apply_movement(active_product(product_id, db), MovementType.STOCK_OUT, -payload.quantity, payload.note, db)


@router.post("/adjust", response_model=ProductRead)
def adjust_stock(product_id: int, payload: StockAdjustment, db: Session = Depends(get_db)) -> Product:
    product = active_product(product_id, db)
    return apply_movement(product, MovementType.ADJUSTMENT, payload.quantity - product.quantity, payload.note, db)


@router.get("/movements", response_model=list[InventoryMovementRead])
def movement_history(product_id: int, db: Session = Depends(get_db)) -> list[InventoryMovement]:
    get_product_or_404(product_id, db)
    return db.scalars(
        select(InventoryMovement)
        .where(InventoryMovement.product_id == product_id)
        .order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.desc())
    ).all()

