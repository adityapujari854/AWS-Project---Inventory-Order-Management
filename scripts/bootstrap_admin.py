"""Create the one administrator account from environment variables."""

import os
import sys

from app.database import Base, SessionLocal, engine
from app.models import admin  # noqa: F401 - register the admin model before table creation
from app.security import bootstrap_admin


def main() -> int:
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    if not username or not password:
        print("Set ADMIN_USERNAME and ADMIN_PASSWORD before running this script.")
        return 1
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        bootstrap_admin(username, password, db)
    except ValueError as error:
        print(f"Admin bootstrap failed: {error}")
        return 1
    finally:
        db.close()
    print("Administrator account created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
