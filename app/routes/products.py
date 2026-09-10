"""Product management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.product import Product, ProductStatus
from app.schemas.product import ProductCreate, ProductList, ProductRead, ProductUpdate

router = APIRouter(prefix="/api/products", tags=["products"])


def get_product_or_404(product_id: int, db: Session) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A product with this SKU already exists") from exc
    db.refresh(product)
    return product


@router.get("", response_model=ProductList)
def list_products(
    search: str | None = None,
    category: str | None = None,
    low_stock_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ProductList:
    filters = [Product.status == ProductStatus.ACTIVE]
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
    if category:
        filters.append(Product.category == category)
    if low_stock_only:
        filters.append(Product.quantity <= Product.reorder_threshold)

    statement = select(Product).where(*filters).order_by(Product.name)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    products = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    return ProductList(items=products, total=total, page=page, page_size=page_size)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    return get_product_or_404(product_id, db)


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)) -> Product:
    product = get_product_or_404(product_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.post("/{product_id}/archive", response_model=ProductRead)
def archive_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    product = get_product_or_404(product_id, db)
    product.status = ProductStatus.ARCHIVED
    db.commit()
    db.refresh(product)
    return product

