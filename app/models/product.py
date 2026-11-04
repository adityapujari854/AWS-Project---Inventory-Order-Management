"""Product database model."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProductStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Product(Base):
    """A sellable inventory item."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    reorder_threshold: Mapped[int] = mapped_column(Integer, default=0)
    image_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ProductStatus] = mapped_column(SqlEnum(ProductStatus), default=ProductStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    movements: Mapped[list["InventoryMovement"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    category_record: Mapped["Category | None"] = relationship(back_populates="products")

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.reorder_threshold

