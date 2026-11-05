"""Print consistency checks for the local fictional demonstration dataset."""

from __future__ import annotations

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models.inventory import InventoryMovement
from app.models.order import Order
from app.models.product import Product
from app.routes.analytics import dashboard_analytics
from app.services.advisor import build_inventory_advice


def main() -> None:
    with SessionLocal() as db:
        product_count = db.scalar(select(func.count()).select_from(Product)) or 0
        order_count = db.scalar(select(func.count()).select_from(Order).where(Order.order_number.like("DEMO-2026-%"))) or 0
        movement_count = db.scalar(select(func.count()).select_from(InventoryMovement)) or 0
        mismatches = []
        for product in db.scalars(select(Product)).all():
            recorded = db.scalar(select(func.coalesce(func.sum(InventoryMovement.quantity_change), 0)).where(
                InventoryMovement.product_id == product.id
            )) or 0
            if recorded != product.quantity:
                mismatches.append(product.sku)
        analytics = dashboard_analytics(days=180, db=db)
        advisor = build_inventory_advice(db, days=30)
        print({
            "products": product_count,
            "demo_orders": order_count,
            "movements": movement_count,
            "stock_reconciliation_mismatches": mismatches,
            "recognized_revenue": str(analytics.kpis.recognized_revenue),
            "monthly_points": len(analytics.monthly_sales),
            "category_sales": len(analytics.sales_by_category),
            "advisor_recommendations": len(advisor.recommendations),
        })


if __name__ == "__main__":
    main()
