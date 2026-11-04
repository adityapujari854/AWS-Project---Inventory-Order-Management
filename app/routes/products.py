"""Product management and private image endpoints."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.category import Category
from app.models.product import Product, ProductStatus
from app.schemas.product import ProductCreate, ProductList, ProductRead, ProductUpdate
from app.security import require_admin, verify_csrf
from app.services.storage import (
    ImageStorageError,
    ImageStorageUnavailable,
    ProductImageStorage,
    get_product_image_storage,
    validate_image,
)

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[Depends(require_admin), Depends(verify_csrf)])
logger = logging.getLogger(__name__)


def get_product_or_404(product_id: int, db: Session) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def _apply_category(product: Product, category_id: int | None, legacy_category: str | None, db: Session) -> None:
    """Apply an authoritative category ID while retaining the legacy text label."""
    if category_id is not None:
        category = db.get(Category, category_id)
        if category is None:
            raise HTTPException(status_code=422, detail="Selected category does not exist")
        product.category_id = category.id
        product.category = category.name
    elif legacy_category is not None:
        product.category = legacy_category.strip() or None


def product_read(product: Product, storage: ProductImageStorage | None = None) -> ProductRead:
    """Return a product with a short-lived image URL when private storage is available."""
    response = ProductRead.model_validate(product)
    if product.image_key and storage is not None:
        try:
            response.image_url = storage.presigned_url(product.image_key)
        except (ImageStorageUnavailable, ImageStorageError):
            logger.warning("Product image URL unavailable for product %s", product.id)
    return response


def _storage_http_error(error: Exception) -> HTTPException:
    if isinstance(error, ImageStorageUnavailable):
        return HTTPException(status_code=503, detail="Product image storage is not configured")
    return HTTPException(status_code=502, detail="Product image storage is temporarily unavailable")


def _image_mutable_product(product_id: int, db: Session) -> Product:
    product = get_product_or_404(product_id, db)
    if product.status == ProductStatus.ARCHIVED:
        raise HTTPException(status_code=409, detail="Archived products cannot have image changes")
    return product


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> ProductRead:
    values = payload.model_dump(exclude={"category_id", "category"})
    product = Product(**values)
    _apply_category(product, payload.category_id, payload.category, db)
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A product with this SKU already exists") from exc
    db.refresh(product)
    return product_read(product)


@router.get("", response_model=ProductList)
def list_products(
    search: str | None = None,
    category: str | None = None,
    category_id: int | None = None,
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
    if category_id is not None:
        filters.append(Product.category_id == category_id)
    if low_stock_only:
        filters.append(Product.quantity <= Product.reorder_threshold)

    statement = select(Product).where(*filters).order_by(Product.name)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    products = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    storage = get_product_image_storage()
    return ProductList(items=[product_read(product, storage) for product in products], total=total, page=page, page_size=page_size)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductRead:
    return product_read(get_product_or_404(product_id, db), get_product_image_storage())


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)) -> ProductRead:
    product = get_product_or_404(product_id, db)
    values = payload.model_dump(exclude_unset=True, exclude={"category_id", "category"})
    for field, value in values.items():
        setattr(product, field, value)
    if "category_id" in payload.model_fields_set or "category" in payload.model_fields_set:
        _apply_category(product, payload.category_id, payload.category, db)
    db.commit()
    db.refresh(product)
    return product_read(product)


@router.post("/{product_id}/archive", response_model=ProductRead)
def archive_product(product_id: int, db: Session = Depends(get_db)) -> ProductRead:
    product = get_product_or_404(product_id, db)
    product.status = ProductStatus.ARCHIVED
    db.commit()
    db.refresh(product)
    return product_read(product)


@router.post("/{product_id}/restore", response_model=ProductRead)
def restore_product(product_id: int, db: Session = Depends(get_db)) -> ProductRead:
    """Restore an archived product without changing its stock or history."""
    product = get_product_or_404(product_id, db)
    product.status = ProductStatus.ACTIVE
    db.commit()
    db.refresh(product)
    return product_read(product)


@router.post("/{product_id}/image", response_model=ProductRead)
def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage: ProductImageStorage = Depends(get_product_image_storage),
) -> ProductRead:
    """Upload or replace a private product image after strict validation."""
    product = _image_mutable_product(product_id, db)
    try:
        content = file.file.read(storage.settings.s3_max_image_size_bytes + 1)
        image = validate_image(content, file.filename, file.content_type, storage.settings.s3_max_image_size_bytes)
        new_key = storage.object_key(product.id, image.extension)
        storage.upload(new_key, image)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (ImageStorageUnavailable, ImageStorageError) as error:
        raise _storage_http_error(error) from error

    old_key = product.image_key
    product.image_key = new_key
    product.image_content_type = image.content_type
    product.image_size_bytes = len(image.content)
    product.image_updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception as error:
        db.rollback()
        try:
            storage.delete(new_key)
        except (ImageStorageUnavailable, ImageStorageError):
            logger.warning("Could not clean up unlinked product image %s", new_key)
        raise HTTPException(status_code=500, detail="Product image could not be saved") from error
    db.refresh(product)

    if old_key and old_key != new_key:
        try:
            storage.delete(old_key)
        except (ImageStorageUnavailable, ImageStorageError):
            logger.warning("Could not delete replaced product image %s", old_key)
    return product_read(product, storage)


@router.delete("/{product_id}/image", response_model=ProductRead)
def remove_product_image(
    product_id: int,
    db: Session = Depends(get_db),
    storage: ProductImageStorage = Depends(get_product_image_storage),
) -> ProductRead:
    """Remove only the object key currently associated with this product."""
    product = _image_mutable_product(product_id, db)
    if not product.image_key:
        raise HTTPException(status_code=404, detail="Product has no image")
    old_key = product.image_key
    try:
        storage.delete(old_key)
    except (ImageStorageUnavailable, ImageStorageError) as error:
        raise _storage_http_error(error) from error
    product.image_key = None
    product.image_content_type = None
    product.image_size_bytes = None
    product.image_updated_at = None
    db.commit()
    db.refresh(product)
    return product_read(product)

