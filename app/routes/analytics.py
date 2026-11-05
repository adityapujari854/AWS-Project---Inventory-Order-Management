"""Database-backed dashboard analytics."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product, ProductStatus
from app.schemas.analytics import (
    BestSellingProduct,
    CategorySales,
    DashboardAnalytics,
    DashboardKpis,
    InventorySummary,
    MonthlySalesPoint,
    OrderStatusCount,
    RecentOrder,
    SalesTrendPoint,
    StockDistribution,
)
from app.security import require_admin, verify_csrf

router = APIRouter(prefix="/api/analytics", tags=["analytics"], dependencies=[Depends(require_admin), Depends(verify_csrf)])

# Stock is deducted at processing, but it becomes recognized revenue only when shipped or delivered.
RECOGNIZED_REVENUE_STATUSES = (OrderStatus.SHIPPED, OrderStatus.DELIVERED)


@router.get("/dashboard", response_model=DashboardAnalytics)
def dashboard_analytics(
    days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)
) -> DashboardAnalytics:
    """Return the aggregates required by the operations dashboard."""
    if not 1 <= days <= 365:
        raise HTTPException(status_code=422, detail="days must be between 1 and 365")
    active_product_filter = Product.status == ProductStatus.ACTIVE
    low_stock_filter = Product.quantity <= Product.reorder_threshold
    revenue_filter = Order.status.in_(RECOGNIZED_REVENUE_STATUSES)

    active_products = db.scalar(select(func.count()).select_from(Product).where(active_product_filter)) or 0
    total_orders = db.scalar(select(func.count()).select_from(Order)) or 0
    recognized_revenue = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(revenue_filter)) or Decimal("0")
    low_stock_products = db.scalar(
        select(func.count()).select_from(Product).where(active_product_filter, low_stock_filter)
    ) or 0
    out_of_stock_products = db.scalar(
        select(func.count()).select_from(Product).where(active_product_filter, Product.quantity == 0)
    ) or 0
    inventory_value = db.scalar(
        select(func.coalesce(func.sum(Product.quantity * Product.cost), 0)).where(active_product_filter)
    ) or Decimal("0")

    status_counts = dict(db.execute(select(Order.status, func.count()).group_by(Order.status)).all())
    order_statuses = [OrderStatusCount(status=status, count=status_counts.get(status, 0)) for status in OrderStatus]

    recent_orders = [
        RecentOrder(
            order_number=order.order_number,
            customer_name=order.customer_name,
            status=order.status,
            total=order.total,
            created_at=order.created_at,
        )
        for order in db.scalars(select(Order).order_by(Order.created_at.desc(), Order.id.desc()).limit(5)).all()
    ]

    best_selling_products = [
        BestSellingProduct(product_id=row.product_id, product_name=row.product_name, units_sold=row.units_sold, revenue=row.revenue)
        for row in db.execute(
            select(
                OrderItem.product_id,
                OrderItem.product_name,
                func.sum(OrderItem.quantity).label("units_sold"),
                func.sum(OrderItem.line_total).label("revenue"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .where(revenue_filter)
            .group_by(OrderItem.product_id, OrderItem.product_name)
            .order_by(func.sum(OrderItem.quantity).desc(), func.sum(OrderItem.line_total).desc())
            .limit(5)
        ).all()
    ]

    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)
    trend_rows = db.execute(
        select(
            func.date(Order.created_at).label("sale_date"),
            func.sum(Order.total).label("revenue"),
            func.count(Order.id).label("orders"),
        )
        .where(revenue_filter, Order.created_at >= start_date)
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
    ).all()
    trend_by_date = {
        date.fromisoformat(str(row.sale_date)): (row.revenue, row.orders)
        for row in trend_rows
        if row.sale_date is not None
    }
    sales_trend = [
        SalesTrendPoint(
            date=current_date,
            revenue=trend_by_date.get(current_date, (Decimal("0"), 0))[0],
            orders=trend_by_date.get(current_date, (Decimal("0"), 0))[1],
        )
        for current_date in (start_date + timedelta(days=offset) for offset in range(days))
    ]
    monthly_buckets: dict[str, tuple[Decimal, int]] = {}
    for point in sales_trend:
        month = point.date.strftime("%Y-%m")
        revenue, orders = monthly_buckets.get(month, (Decimal("0"), 0))
        monthly_buckets[month] = (revenue + point.revenue, orders + point.orders)
    monthly_sales = [
        MonthlySalesPoint(month=month, revenue=values[0], orders=values[1])
        for month, values in sorted(monthly_buckets.items())
    ]
    category_rows = db.execute(
        select(
            func.coalesce(Product.category, "Uncategorised").label("category"),
            func.sum(OrderItem.line_total).label("revenue"),
            func.sum(OrderItem.quantity).label("units_sold"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(revenue_filter, Order.created_at >= start_date)
        .group_by(func.coalesce(Product.category, "Uncategorised"))
        .order_by(func.sum(OrderItem.line_total).desc())
    ).all()
    sales_by_category = [CategorySales(category=row.category, revenue=row.revenue, units_sold=row.units_sold) for row in category_rows]
    healthy_stock = db.scalar(
        select(func.count()).select_from(Product).where(active_product_filter, Product.quantity > Product.reorder_threshold)
    ) or 0

    return DashboardAnalytics(
        kpis=DashboardKpis(
            active_products=active_products,
            total_orders=total_orders,
            recognized_revenue=recognized_revenue,
            low_stock_products=low_stock_products,
        ),
        inventory=InventorySummary(
            inventory_value=inventory_value,
            out_of_stock_products=out_of_stock_products,
            low_stock_products=low_stock_products,
        ),
        order_statuses=order_statuses,
        recent_orders=recent_orders,
        best_selling_products=best_selling_products,
        sales_trend=sales_trend,
        monthly_sales=monthly_sales,
        sales_by_category=sales_by_category,
        stock_distribution=StockDistribution(
            out_of_stock=out_of_stock_products,
            low_stock=low_stock_products - out_of_stock_products,
            healthy_stock=healthy_stock,
        ),
        revenue_period_days=days,
    )
