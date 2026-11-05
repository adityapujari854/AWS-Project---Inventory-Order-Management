"""Dashboard analytics response schemas."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.order import OrderStatus


class DashboardKpis(BaseModel):
    active_products: int
    total_orders: int
    recognized_revenue: Decimal
    low_stock_products: int


class InventorySummary(BaseModel):
    inventory_value: Decimal
    out_of_stock_products: int
    low_stock_products: int


class OrderStatusCount(BaseModel):
    status: OrderStatus
    count: int


class RecentOrder(BaseModel):
    order_number: str
    customer_name: str
    status: OrderStatus
    total: Decimal
    created_at: datetime


class BestSellingProduct(BaseModel):
    product_id: int
    product_name: str
    units_sold: int
    revenue: Decimal


class SalesTrendPoint(BaseModel):
    date: date
    revenue: Decimal
    orders: int


class MonthlySalesPoint(BaseModel):
    month: str
    revenue: Decimal
    orders: int


class CategorySales(BaseModel):
    category: str
    revenue: Decimal
    units_sold: int


class StockDistribution(BaseModel):
    out_of_stock: int
    low_stock: int
    healthy_stock: int


class DashboardAnalytics(BaseModel):
    kpis: DashboardKpis
    inventory: InventorySummary
    order_statuses: list[OrderStatusCount]
    recent_orders: list[RecentOrder]
    best_selling_products: list[BestSellingProduct]
    sales_trend: list[SalesTrendPoint]
    monthly_sales: list[MonthlySalesPoint]
    sales_by_category: list[CategorySales]
    stock_distribution: StockDistribution
    revenue_period_days: int
