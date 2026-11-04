"""Product API schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.product import ProductStatus


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64, examples=["WM-001"])
    name: str = Field(min_length=1, max_length=160, examples=["Wireless Mouse"])
    description: str | None = Field(default=None, max_length=500)
    category_id: int | None = Field(default=None, ge=1)
    category: str | None = Field(default=None, max_length=100)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    cost: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    quantity: int = Field(default=0, ge=0)
    reorder_threshold: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    category_id: int | None = Field(default=None, ge=1)
    category: str | None = Field(default=None, max_length=100)
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    cost: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    reorder_threshold: int | None = Field(default=None, ge=0)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    description: str | None
    category_id: int | None
    category: str | None
    price: Decimal
    cost: Decimal
    quantity: int
    reorder_threshold: int
    image_key: str | None
    image_content_type: str | None
    image_size_bytes: int | None
    image_url: str | None = None
    status: ProductStatus
    is_low_stock: bool
    created_at: datetime
    updated_at: datetime


class ProductList(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    page_size: int

