"""Route-level functional tests that do not require a Windows loopback socket."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.datastructures import Headers, UploadFile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.config import Settings
from app.main import STATIC_DIRECTORY, app, dashboard, health_check
from app.routes.auth import login_page
from app.models.inventory import InventoryMovement
from app.models.admin import AdminUser, AuthSession
from app.models.category import Category
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.supplier import Supplier, SupplierProduct
from app.routes.inventory import movement_history, stock_in, stock_out
from app.routes.analytics import dashboard_analytics
from app.routes import analytics as analytics_routes
from app.routes import advisor as advisor_routes
from app.routes import categories as category_routes
from app.routes import inventory as inventory_routes
from app.routes import orders as order_routes
from app.routes import products as product_routes
from app.routes import suppliers as supplier_routes
from app.routes.orders import create_order, update_order_status
from app.routes.advisor import inventory_advisor
from app.routes.products import (
    archive_product,
    create_product as create_product_route,
    get_product,
    list_products,
    remove_product_image,
    restore_product,
    upload_product_image,
)
from app.routes.categories import create_category, delete_category, list_categories, update_category
from app.routes.suppliers import create_supplier, link_supplier_product
from app.schemas.inventory import StockChange
from app.schemas.order import OrderCreate, OrderItemCreate, OrderStatusUpdate
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.supplier import SupplierCreate
from app.security import (
    authenticate_admin,
    bootstrap_admin,
    create_authenticated_session,
    get_current_admin,
    logout_session,
    require_admin,
    verify_csrf,
    verify_password,
)
from app.services.storage import ImageStorageError, ImageStorageUnavailable
from app.services.catalogue import seed_sample_catalogue
from app.services.demo_data import seed_demo_data

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    database_session = TestingSessionLocal()
    database_session.query(AuthSession).delete()
    database_session.query(AdminUser).delete()
    database_session.query(OrderItem).delete()
    database_session.query(Order).delete()
    database_session.query(InventoryMovement).delete()
    database_session.query(SupplierProduct).delete()
    database_session.query(Product).delete()
    database_session.query(Category).delete()
    database_session.query(Supplier).delete()
    database_session.commit()
    yield database_session
    database_session.close()


def create_product(db, **overrides):
    payload = {
        "sku": "WM-001",
        "name": "Wireless Mouse",
        "category": "Accessories",
        "price": "29.99",
        "cost": "12.50",
        "quantity": 10,
        "reorder_threshold": 5,
    }
    payload.update(overrides)
    return create_product_route(ProductCreate(**payload), db)


def make_request(session=None, headers=None):
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": headers or [],
            "session": session if session is not None else {},
            "app": app,
        }
    )


class FakeImageStorage:
    def __init__(self, max_size=1024):
        self.settings = SimpleNamespace(s3_max_image_size_bytes=max_size)
        self.uploaded = {}
        self.deleted = []
        self.sequence = 0

    def object_key(self, product_id, extension):
        self.sequence += 1
        return f"product-images/products/{product_id}/image-{self.sequence}.{extension}"

    def upload(self, key, image):
        self.uploaded[key] = image

    def delete(self, key):
        self.deleted.append(key)
        self.uploaded.pop(key, None)

    def presigned_url(self, key):
        return f"https://example.invalid/private/{key}?expires=900"


def upload_file(name, content_type, content):
    return UploadFile(file=BytesIO(content), filename=name, headers=Headers({"content-type": content_type}))


def test_health_check_returns_service_status():
    response = health_check()

    assert response["status"] == "ok"
    assert response["service"] == "InventoryHub"


def test_production_settings_reject_local_database_and_insecure_session_configuration(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://app:password@db.example.internal:3306/inventoryhub")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")

    assert Settings().is_sqlite is False

    monkeypatch.setenv("DATABASE_URL", "sqlite:///./inventory.db")
    with pytest.raises(ValueError, match="managed database"):
        Settings()

    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://app:password@db.example.internal:3306/inventoryhub")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    with pytest.raises(ValueError, match="SESSION_COOKIE_SECURE"):
        Settings()


def test_dashboard_is_available():
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "app": app, "session": {}})
    response = dashboard(request)

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


def test_login_uses_the_mounted_stylesheet_and_has_no_stray_identity_mark(db):
    request = Request({"type": "http", "method": "GET", "path": "/auth/login", "headers": [], "app": app, "session": {}})
    response = login_page(request, db)

    assert app.url_path_for("static", path="css/app.css") == "/static/css/app.css"
    assert (Path(STATIC_DIRECTORY) / "css" / "app.css").is_file()
    assert b'href="/static/css/app.css"' in response.body
    assert b">IH<" not in response.body


def test_product_can_be_created_and_listed(db):
    created = create_product(db)
    response = list_products(search="mouse", page=1, page_size=20, db=db)

    assert created.sku == "WM-001"
    assert response.total == 1
    assert response.items[0].quantity == 10


def test_categories_validate_products_filtering_and_safe_deletion(db):
    accessories = create_category(CategoryCreate(name="Computer Accessories"), db)
    hardware = create_category(CategoryCreate(name="Computer Hardware"), db)
    product = create_product(db, category_id=accessories.id, category=None)

    filtered = list_products(category_id=accessories.id, page=1, page_size=20, db=db)
    updated = update_category(accessories.id, CategoryUpdate(name="Accessories"), db)
    with pytest.raises(HTTPException) as delete_error:
        delete_category(accessories.id, db)
    with pytest.raises(HTTPException) as invalid_error:
        create_product_route(ProductCreate(sku="BAD-001", name="Bad category", price="1", cost="1", category_id=999), db)
    with pytest.raises(HTTPException) as duplicate_error:
        create_category(CategoryCreate(name="Computer Hardware"), db)

    assert filtered.total == 1
    assert product.category == "Computer Accessories"
    assert updated.name == "Accessories"
    assert get_product(product.id, db).category == "Accessories"
    assert delete_error.value.status_code == 409
    assert invalid_error.value.status_code == 422
    assert duplicate_error.value.status_code == 409
    assert [category.name for category in list_categories(db)] == ["Accessories", "Computer Hardware"]


def test_catalogue_seed_is_idempotent_and_preserves_existing_stock(db):
    mouse = create_product(db, sku="WM-001", name="Wireless Mouse", quantity=91, category=None)
    first = seed_sample_catalogue(db)
    second = seed_sample_catalogue(db)

    assert first["categories"] == 12
    assert first["products"] == 49
    assert second == {"categories": 0, "suppliers": 0, "products": 0, "supplier_links": 0}
    assert db.query(Category).count() == 12
    assert db.query(Product).count() == 50
    assert db.get(Product, mouse.id).quantity == 91
    assert db.get(Product, mouse.id).category == "Computer Accessories"


def test_demo_seed_is_idempotent_and_reconciles_inventory(db):
    first = seed_demo_data(db)
    second = seed_demo_data(db)

    assert first["orders_added"] == 40
    assert first["inventory_profile_applied"] == 1
    assert second["orders_added"] == 0
    assert db.query(Product).count() == 50
    assert db.query(Supplier).count() == 10
    assert db.query(Order).filter(Order.order_number.like("DEMO-2026-%")).count() == 40
    assert db.query(OrderItem).count() >= 80
    for product in db.query(Product).all():
        assert sum(movement.quantity_change for movement in product.movements) == product.quantity

    analytics = dashboard_analytics(days=180, db=db)
    assert analytics.kpis.total_orders == 40
    assert analytics.kpis.recognized_revenue > 0
    assert len(analytics.monthly_sales) >= 6
    assert analytics.sales_by_category
    assert analytics.stock_distribution.out_of_stock == 3


def test_stock_changes_create_a_movement_history(db):
    product = create_product(db)
    stock_in_result = stock_in(product.id, StockChange(quantity=3, note="Supplier delivery"), db)
    stock_in_quantity = stock_in_result.quantity
    stock_out_result = stock_out(product.id, StockChange(quantity=11), db)
    history = movement_history(product.id, db)

    assert stock_in_quantity == 13
    assert stock_out_result.quantity == 2
    assert stock_out_result.is_low_stock is True
    assert [movement.quantity_change for movement in history] == [-11, 3]


def test_stock_out_cannot_make_inventory_negative(db):
    product = create_product(db, quantity=2)

    with pytest.raises(HTTPException) as error:
        stock_out(product.id, StockChange(quantity=3), db)

    assert error.value.status_code == 422
    assert error.value.detail == "Insufficient stock for this operation"


def test_archived_product_is_hidden_and_cannot_change_stock(db):
    product = create_product(db)
    archive_product(product.id, db)
    listing = list_products(page=1, page_size=20, db=db)

    with pytest.raises(HTTPException) as error:
        stock_in(product.id, StockChange(quantity=1), db)

    assert listing.total == 0
    assert error.value.status_code == 409


def test_archived_product_can_be_restored_without_changing_stock(db):
    product = create_product(db, quantity=8)
    archive_product(product.id, db)
    restored = restore_product(product.id, db)

    assert restored.status == "active"
    assert restored.quantity == 8


def test_supplier_can_be_created_and_linked_to_a_product(db):
    product = create_product(db)
    supplier = create_supplier(SupplierCreate(name="Acme Distribution", email="orders@acme.test"), db)
    link_supplier_product(supplier.id, product.id, db)

    assert supplier.name == "Acme Distribution"
    assert db.query(SupplierProduct).count() == 1


def test_processing_order_deducts_stock_and_writes_movements(db):
    product = create_product(db, quantity=10)
    order = create_order(
        OrderCreate(customer_name="Asha Patel", items=[OrderItemCreate(product_id=product.id, quantity=4)]), db
    )
    initial_status = order.status
    processing = update_order_status(order.id, OrderStatusUpdate(status="processing"), db)
    current_product = get_product(product.id, db)
    movements = movement_history(product.id, db)

    assert initial_status == "pending"
    assert processing.stock_deducted is True
    assert current_product.quantity == 6
    assert movements[0].movement_type == "order_out"


def test_processing_order_rejects_overselling_without_changing_stock(db):
    product = create_product(db, quantity=2)
    order = create_order(
        OrderCreate(customer_name="Asha Patel", items=[OrderItemCreate(product_id=product.id, quantity=3)]), db
    )

    with pytest.raises(HTTPException) as error:
        update_order_status(order.id, OrderStatusUpdate(status="processing"), db)

    assert error.value.status_code == 422
    assert get_product(product.id, db).quantity == 2


def test_cancelling_processing_order_returns_stock(db):
    product = create_product(db, quantity=5)
    order = create_order(
        OrderCreate(customer_name="Asha Patel", items=[OrderItemCreate(product_id=product.id, quantity=2)]), db
    )
    update_order_status(order.id, OrderStatusUpdate(status="processing"), db)
    cancelled = update_order_status(order.id, OrderStatusUpdate(status="cancelled"), db)

    assert cancelled.stock_deducted is False
    assert get_product(product.id, db).quantity == 5


def set_order_status(db, order, *statuses):
    for order_status in statuses:
        update_order_status(order.id, OrderStatusUpdate(status=order_status), db)


def test_dashboard_returns_zero_values_for_an_empty_database(db):
    analytics = dashboard_analytics(days=3, db=db)

    assert analytics.kpis.active_products == 0
    assert analytics.kpis.total_orders == 0
    assert analytics.kpis.recognized_revenue == Decimal("0")
    assert analytics.inventory.inventory_value == Decimal("0")
    assert analytics.recent_orders == []
    assert analytics.best_selling_products == []
    assert len(analytics.order_statuses) == 5
    assert len(analytics.sales_trend) == 3
    assert all(point.revenue == Decimal("0") for point in analytics.sales_trend)


def test_dashboard_calculates_kpis_inventory_sales_and_orders(db):
    keyboard = create_product(
        db, sku="KB-001", name="Keyboard", price="10.00", cost="4.00", quantity=10, reorder_threshold=5
    )
    mouse = create_product(
        db, sku="MS-001", name="Mouse", price="15.00", cost="6.00", quantity=1, reorder_threshold=2
    )
    delivered = create_order(
        OrderCreate(customer_name="Asha", items=[OrderItemCreate(product_id=keyboard.id, quantity=2)]), db
    )
    set_order_status(db, delivered, "processing", "shipped", "delivered")
    shipped = create_order(
        OrderCreate(customer_name="Ben", items=[OrderItemCreate(product_id=mouse.id, quantity=1)]), db
    )
    set_order_status(db, shipped, "processing", "shipped")
    pending = create_order(
        OrderCreate(customer_name="Casey", items=[OrderItemCreate(product_id=keyboard.id, quantity=1)]), db
    )
    cancelled = create_order(
        OrderCreate(customer_name="Dana", items=[OrderItemCreate(product_id=keyboard.id, quantity=1)]), db
    )
    set_order_status(db, cancelled, "cancelled")

    delivered.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    shipped.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    pending.created_at = datetime.now(timezone.utc)
    cancelled.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()

    analytics = dashboard_analytics(days=3, db=db)
    status_counts = {item.status.value: item.count for item in analytics.order_statuses}

    assert analytics.kpis.active_products == 2
    assert analytics.kpis.total_orders == 4
    assert analytics.kpis.recognized_revenue == Decimal("35.00")
    assert analytics.kpis.low_stock_products == 1
    assert analytics.inventory.inventory_value == Decimal("32.00")
    assert analytics.inventory.out_of_stock_products == 1
    assert status_counts == {"pending": 1, "processing": 0, "shipped": 1, "delivered": 1, "cancelled": 1}
    assert [order.order_number for order in analytics.recent_orders] == [pending.order_number, cancelled.order_number, shipped.order_number, delivered.order_number]
    assert analytics.best_selling_products[0].product_name == "Keyboard"
    assert analytics.best_selling_products[0].units_sold == 2
    assert analytics.best_selling_products[1].product_name == "Mouse"
    assert sum(point.revenue for point in analytics.sales_trend) == Decimal("35.00")
    assert sum(point.orders for point in analytics.sales_trend) == 2


def test_dashboard_rejects_invalid_sales_trend_period(db):
    with pytest.raises(HTTPException) as error:
        dashboard_analytics(days=0, db=db)

    assert error.value.status_code == 422


def test_inventory_advisor_handles_empty_inventory_and_insufficient_history(db):
    empty_advice = inventory_advisor(days=30, db=db)
    product = create_product(db, sku="NEW-001", name="New Product", quantity=20, reorder_threshold=5)
    advice = inventory_advisor(days=30, db=db)

    assert empty_advice.recommendations == []
    assert empty_advice.summary.critical == 0
    assert len(advice.recommendations) == 1
    assert advice.recommendations[0].product_id == product.id
    assert advice.recommendations[0].severity == "insufficient_history"
    assert advice.recommendations[0].suggested_reorder_quantity is None


def test_inventory_advisor_prioritizes_stock_risk_and_excludes_cancelled_orders(db):
    out_of_stock = create_product(db, sku="OUT-001", name="Out of stock", quantity=0, reorder_threshold=5)
    low_stock = create_product(db, sku="LOW-001", name="Low stock", quantity=5, reorder_threshold=3)
    near_threshold = create_product(db, sku="NEAR-001", name="Near threshold", quantity=7, reorder_threshold=5)
    shipped_order = create_order(
        OrderCreate(customer_name="Asha", items=[OrderItemCreate(product_id=low_stock.id, quantity=2)]), db
    )
    cancelled_order = create_order(
        OrderCreate(customer_name="Ben", items=[OrderItemCreate(product_id=low_stock.id, quantity=1)]), db
    )
    set_order_status(db, shipped_order, "processing", "shipped")
    set_order_status(db, cancelled_order, "cancelled")
    stock_out(near_threshold.id, StockChange(quantity=1), db)
    quantity_before = get_product(low_stock.id, db).quantity
    order_count_before = db.query(Order).count()

    advice = inventory_advisor(days=30, db=db)
    recommendations = {item.product_id: item for item in advice.recommendations}

    assert advice.recommendations[0].product_id == out_of_stock.id
    assert recommendations[out_of_stock.id].severity == "critical"
    assert recommendations[out_of_stock.id].suggested_reorder_quantity == 6
    assert recommendations[low_stock.id].severity == "warning"
    assert recommendations[low_stock.id].current_quantity == 3
    assert recommendations[low_stock.id].recent_sales_units == 2
    assert recommendations[low_stock.id].recent_depletion_units == 2
    assert recommendations[low_stock.id].suggested_reorder_quantity == 1
    assert recommendations[near_threshold.id].severity == "monitor"
    assert recommendations[near_threshold.id].recent_depletion_units == 1
    assert recommendations[near_threshold.id].suggested_reorder_quantity is None
    assert get_product(low_stock.id, db).quantity == quantity_before
    assert db.query(Order).count() == order_count_before


def test_inventory_advisor_rejects_invalid_analysis_period(db):
    with pytest.raises(HTTPException) as error:
        inventory_advisor(days=0, db=db)

    assert error.value.status_code == 422


def test_bootstrap_hashes_password_and_rejects_duplicate_admins(db):
    admin = bootstrap_admin("aditya", "StrongPassword!1", db)

    assert admin.password_hash != "StrongPassword!1"
    assert verify_password("StrongPassword!1", admin.password_hash) is True
    with pytest.raises(ValueError):
        bootstrap_admin("another-admin", "StrongPassword!1", db)


def test_credentials_sessions_csrf_and_logout(db):
    admin = bootstrap_admin("aditya", "StrongPassword!1", db)
    assert authenticate_admin("aditya", "StrongPassword!1", db).id == admin.id
    assert authenticate_admin("aditya", "wrong-password", db) is None

    request = make_request()
    create_authenticated_session(admin, request, db)
    assert get_current_admin(request, db).id == admin.id

    request.scope["headers"] = [(b"x-csrf-token", request.session["csrf_token"].encode())]
    verify_csrf(request)
    logout_session(request, db)
    with pytest.raises(HTTPException) as error:
        get_current_admin(request, db)
    assert error.value.status_code == 401


def test_missing_session_or_csrf_is_rejected_without_business_changes(db):
    product = create_product(db, quantity=2)
    request = make_request()

    with pytest.raises(HTTPException) as auth_error:
        get_current_admin(request, db)
    with pytest.raises(HTTPException) as csrf_error:
        verify_csrf(request)

    assert auth_error.value.status_code == 401
    assert csrf_error.value.status_code == 403
    assert get_product(product.id, db).quantity == 2


def test_protected_routes_use_authentication_and_csrf_dependencies():
    routers = [
        product_routes.router,
        inventory_routes.router,
        order_routes.router,
        supplier_routes.router,
        analytics_routes.router,
        advisor_routes.router,
        category_routes.router,
    ]
    for router in routers:
        dependency_calls = {dependency.dependency for dependency in router.dependencies}
        assert require_admin in dependency_calls
        assert verify_csrf in dependency_calls


def test_authenticated_administrator_can_open_dashboard(db):
    admin = bootstrap_admin("aditya", "StrongPassword!1", db)
    request = make_request()
    request.scope["method"] = "GET"
    create_authenticated_session(admin, request, db)

    response = dashboard(request, db)

    assert response.status_code == 200
    assert b"Built by Aditya" in response.body


def test_valid_product_image_upload_persists_key_and_returns_presigned_url(db):
    product = create_product(db)
    storage = FakeImageStorage()
    image = upload_product_image(
        product.id, upload_file("mouse.png", "image/png", b"\x89PNG\r\n\x1a\nimage-data"), db, storage
    )
    stored_product = db.get(Product, product.id)

    assert stored_product.image_key == "product-images/products/1/image-1.png"
    assert stored_product.image_content_type == "image/png"
    assert stored_product.image_size_bytes == 18
    assert image.image_url.startswith("https://example.invalid/private/")
    assert "image_url" not in stored_product.__dict__


def test_replacing_and_removing_an_image_only_deletes_its_associated_key(db):
    product = create_product(db)
    storage = FakeImageStorage()
    first = upload_product_image(product.id, upload_file("mouse.png", "image/png", b"\x89PNG\r\n\x1a\na"), db, storage)
    second = upload_product_image(product.id, upload_file("mouse.webp", "image/webp", b"RIFFxxxxWEBPdata"), db, storage)
    removed = remove_product_image(product.id, db, storage)

    assert first.image_key in storage.deleted
    assert second.image_key in storage.deleted
    assert removed.image_key is None
    assert db.get(Product, product.id).image_key is None


def test_invalid_and_oversized_product_images_are_rejected(db):
    product = create_product(db)
    storage = FakeImageStorage(max_size=16)

    with pytest.raises(HTTPException) as invalid_error:
        upload_product_image(product.id, upload_file("file.exe", "application/octet-stream", b"not-an-image"), db, storage)
    with pytest.raises(HTTPException) as size_error:
        upload_product_image(product.id, upload_file("large.png", "image/png", b"\x89PNG\r\n\x1a\nmore-than-eight"), db, storage)
    with pytest.raises(HTTPException) as signature_error:
        upload_product_image(product.id, upload_file("fake.png", "image/png", b"not-a-png"), db, storage)

    assert invalid_error.value.status_code == 422
    assert size_error.value.status_code == 422
    assert signature_error.value.status_code == 422
    assert storage.uploaded == {}


def test_image_storage_configuration_and_service_failures_are_safe(db):
    product = create_product(db)

    class UnavailableStorage(FakeImageStorage):
        def upload(self, key, image):
            raise ImageStorageUnavailable()

    class FailingStorage(FakeImageStorage):
        def upload(self, key, image):
            raise ImageStorageError()

    image = upload_file("mouse.png", "image/png", b"\x89PNG\r\n\x1a\na")
    with pytest.raises(HTTPException) as unavailable_error:
        upload_product_image(product.id, image, db, UnavailableStorage())
    with pytest.raises(HTTPException) as service_error:
        upload_product_image(
            product.id, upload_file("mouse.png", "image/png", b"\x89PNG\r\n\x1a\na"), db, FailingStorage()
        )

    assert unavailable_error.value.status_code == 503
    assert service_error.value.status_code == 502
    assert db.get(Product, product.id).image_key is None
