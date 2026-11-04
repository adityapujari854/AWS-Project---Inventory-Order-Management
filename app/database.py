"""SQLAlchemy database engine and session helpers."""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

engine_options: dict[str, object] = {"pool_pre_ping": True}
if settings.is_sqlite:
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for future SQLAlchemy models."""


def apply_development_schema_updates() -> None:
    """Apply additive SQLite-only compatibility updates without dropping local data."""
    if not settings.is_sqlite:
        return
    inspector = inspect(engine)
    if "products" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("products")}
    new_columns = {
        "description": "VARCHAR(500)",
        "category_id": "INTEGER REFERENCES categories(id)",
        "image_key": "VARCHAR(512)",
        "image_content_type": "VARCHAR(100)",
        "image_size_bytes": "INTEGER",
        "image_updated_at": "DATETIME",
    }
    with engine.begin() as connection:
        for name, column_type in new_columns.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE products ADD COLUMN {name} {column_type}"))
        category_rows = connection.execute(
            text("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND trim(category) != ''")
        ).scalars().all()
        for category_name in category_rows:
            connection.execute(text("INSERT OR IGNORE INTO categories (name) VALUES (:name)"), {"name": category_name})
        connection.execute(
            text(
                "UPDATE products SET category_id = (SELECT id FROM categories WHERE categories.name = products.category) "
                "WHERE category_id IS NULL AND category IS NOT NULL"
            )
        )


def get_db():
    """Yield one database session per request."""
    database_session = SessionLocal()
    try:
        yield database_session
    finally:
        database_session.close()

