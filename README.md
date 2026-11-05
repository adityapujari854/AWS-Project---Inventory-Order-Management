# InventoryHub — AWS Inventory & Order Management

An inventory and order management platform built locally with FastAPI, then deployed to AWS with EC2, RDS MySQL, S3, an Application Load Balancer, Auto Scaling, CloudWatch/SNS, and CloudFormation.

## Current milestone

Workstream 2, Part 2 — a read-only, explainable Inventory Advisor alongside the authenticated InventoryHub interface.

## Dashboard calculation rules

- Recognized revenue and sales trends include only `shipped` and `delivered` orders. Pending, processing, and cancelled orders are excluded.
- Inventory value is active on-hand quantity multiplied by each product's stored cost.
- Low stock means active quantity at or below the product reorder threshold; out of stock means active quantity is zero.
- Trend dates are order creation dates because the current model does not store a status-change timestamp.

## Local setup

1. Create and activate a Python virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set values as needed.
4. Start the app: `uvicorn app.main:app --reload`
5. Open `http://127.0.0.1:8000` and verify `http://127.0.0.1:8000/health`.

Run tests with: `python -m pytest -q -p no:cacheprovider`

SQLite is the default for the foundation. Set `DATABASE_URL` to a MySQL SQLAlchemy connection URL before the later local-MySQL/RDS steps.

## Administrator setup and security

1. Set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and a long random `SESSION_SECRET` in `.env`.
2. Create the initial account once: `python -m scripts.bootstrap_admin`
3. Remove `ADMIN_USERNAME` and `ADMIN_PASSWORD` from `.env` after successful setup, then start the app and sign in at `http://127.0.0.1:8000/auth/login`.

There is no public registration endpoint. Passwords use bcrypt hashes. Browser sessions use a signed, HttpOnly, SameSite cookie containing an opaque token; the token is checked against the database on every protected request. Logout deletes that database session, invalidating it immediately.

Product, inventory, supplier, order, and analytics APIs require authentication. State-changing API requests also require the session-bound `X-CSRF-Token` header. `/health` and login resources remain public for monitoring and sign-in.

For production behind HTTPS, set `ENVIRONMENT=production`, provide a unique `SESSION_SECRET`, and set `SESSION_COOKIE_SECURE=true`. The interactive API docs are intentionally disabled in production. Development does not include login rate limiting; add it at the reverse proxy/WAF layer before any public deployment.

## Private S3 product images

Authenticated administrators can upload, replace, and remove JPEG, PNG, or WebP product images at `/products`. Images are validated for extension, declared media type, file signature, and a configurable size limit before upload. InventoryHub stores only the S3 object key and metadata in the database.

The S3 bucket remains private. Image links are short-lived presigned URLs generated when product data is returned; expiring URLs are never saved to the database. When S3 is not configured, ordinary product and inventory operations still work, while image actions return a clear error.

Set `AWS_REGION`, `S3_BUCKET_NAME`, `S3_PRODUCT_IMAGE_PREFIX`, `S3_PRESIGNED_URL_TTL_SECONDS`, and `S3_MAX_IMAGE_SIZE_BYTES` in `.env`. Use an AWS CLI profile locally or attach an EC2 instance role later—never place AWS access keys in this project. See [the S3 image guide](docs/s3-product-images.md) for bucket setup, image lifecycle, and the least-privilege IAM policy.

## Inventory Advisor

The authenticated, read-only Advisor at `/advisor` reviews the last 30 days of existing application data. It never updates stock, creates orders, or contacts suppliers.

- `critical`: an active product has zero on-hand stock. The suggested units to add bring stock to the larger of twice recognized recent sales or one unit above its configured reorder threshold.
- `warning`: stock is at or below its reorder threshold. The suggested units to add bring stock up to twice recognized recent sales or at least one unit above the threshold.
- `monitor`: stock is close to its threshold and recorded stock-out/order-out movements occurred during the period. No quantity is suggested.
- `insufficient history`: a product has no recognized recent sales and no inventory-movement history. No quantity is suggested.

Recognized sales include only `shipped` and `delivered` orders; cancelled, pending, and processing orders are excluded. Since the current data model records order creation time rather than a status-change time, the advisor uses creation time for the analysis window. These rules are transparent operational signals, not machine-learning predictions or demand forecasts.

## Product catalogue

Products can be assigned to administrator-managed categories and filtered by category in the catalogue UI. Run `python -m scripts.seed_catalogue` to add the idempotent fictional demonstration catalogue. See [product catalogue documentation](docs/product-catalogue.md) for APIs, local migration behavior, and safe seeding details.

Catalogue images are sourced and validated automatically with `python scripts/download_catalogue_images.py`. The command is restartable and preserves valid manifest entries; run `python scripts/verify_catalogue_images.py` to inspect coverage. Optional private S3 seeding is always a dry run unless explicitly confirmed with `python scripts/upload_catalogue_images.py --confirm`.

## Development demo data

For a realistic local portfolio demonstration, run `python -m scripts.seed_demo_data` after configuring a development SQLite database. It first ensures the 50-product fictional catalogue, then adds 40 dated fictional orders, 10 fictional suppliers, supplier-product links, stock receipts, order deductions, cancelled-order returns, and cycle-count adjustments. All demo orders use the `DEMO-2026-` prefix and all initial receipts are labelled `Demo opening receipt`.

The command is idempotent: it creates only missing demo records and never deletes records. It is intentionally blocked when `ENVIRONMENT=production` or when the configured database is not SQLite. Run it only against a development database; it can add auditable demo history and stock state to an otherwise clean local catalogue. Dashboard and Analytics charts derive their values from these saved records—no frontend statistics are hardcoded. Supplier purchase trends are not shown because the current schema does not associate a supplier with an individual inventory receipt.

## Planned milestones

1. Phase 3 pre-deployment stop point: [AWS tooling, parameter, and cost review](docs/aws-phase-3-predeployment-review.md)
2. EC2 preparation: [deployment notes and manual IAM checkpoint](infrastructure/ec2/deployment-notes.md)
3. Reviewed EC2 stack creation, followed by Session Manager deployment verification
