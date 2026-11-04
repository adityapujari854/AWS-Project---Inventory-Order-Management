"""Authenticated category management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.category import Category
from app.models.product import Product
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.security import require_admin, verify_csrf

router = APIRouter(prefix="/api/categories", tags=["categories"], dependencies=[Depends(require_admin), Depends(verify_csrf)])


def _category_or_404(category_id: int, db: Session) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.get("", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db)) -> list[Category]:
    return db.scalars(select(Category).order_by(Category.name)).all()


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)) -> Category:
    category = Category(name=payload.name.strip())
    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A category with this name already exists") from exc
    db.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)) -> Category:
    category = _category_or_404(category_id, db)
    category.name = payload.name.strip()
    try:
        db.flush()
        db.query(Product).filter(Product.category_id == category.id).update({Product.category: category.name})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A category with this name already exists") from exc
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)) -> None:
    category = _category_or_404(category_id, db)
    assigned_products = db.scalar(select(func.count()).select_from(Product).where(Product.category_id == category.id)) or 0
    if assigned_products:
        raise HTTPException(status_code=409, detail="Reassign products before deleting this category")
    db.delete(category)
    db.commit()
