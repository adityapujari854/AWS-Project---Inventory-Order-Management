"""Supplier management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.product import Product
from app.models.supplier import Supplier, SupplierProduct
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
from app.security import require_admin, verify_csrf

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"], dependencies=[Depends(require_admin), Depends(verify_csrf)])


def get_supplier_or_404(supplier_id: int, db: Session) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)) -> Supplier:
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A supplier with this name already exists") from exc
    db.refresh(supplier)
    return supplier


@router.get("", response_model=list[SupplierRead])
def list_suppliers(db: Session = Depends(get_db)) -> list[Supplier]:
    return db.scalars(select(Supplier).order_by(Supplier.name)).all()


@router.patch("/{supplier_id}", response_model=SupplierRead)
def update_supplier(supplier_id: int, payload: SupplierUpdate, db: Session = Depends(get_db)) -> Supplier:
    supplier = get_supplier_or_404(supplier_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A supplier with this name already exists") from exc
    db.refresh(supplier)
    return supplier


@router.post("/{supplier_id}/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def link_supplier_product(supplier_id: int, product_id: int, db: Session = Depends(get_db)) -> None:
    get_supplier_or_404(supplier_id, db)
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if db.scalar(
        select(SupplierProduct).where(
            SupplierProduct.supplier_id == supplier_id, SupplierProduct.product_id == product_id
        )
    ):
        raise HTTPException(status_code=409, detail="Supplier is already linked to this product")
    db.add(SupplierProduct(supplier_id=supplier_id, product_id=product_id))
    db.commit()

