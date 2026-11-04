# Product catalogue and category management

InventoryHub now stores categories in a `categories` table and links products with `products.category_id`. The older text `products.category` label remains synchronized for compatibility with existing product data and API consumers.

## Local SQLite migration

On the next local application startup, the SQLite compatibility update adds `description` and `category_id` columns. It creates category records from existing non-empty category labels and links matching products without changing stock, prices, orders, images, or movements.

For MySQL/RDS production, do not rely on application startup. Apply a reviewed migration before deploying:

1. Create `categories` with a unique `name` and timestamps.
2. Add nullable `products.description` and nullable `products.category_id` with a foreign key to `categories.id`.
3. Create categories from existing distinct non-empty product labels.
4. Backfill `category_id` by matching category names.
5. Verify all active products, then enforce any future non-null category rule only after data review.

## APIs

- `GET /api/categories`
- `POST /api/categories`
- `PATCH /api/categories/{category_id}`
- `DELETE /api/categories/{category_id}`

All category APIs require the existing admin session and CSRF protection. A category cannot be deleted while products use it. Product create/update accepts `category_id`; invalid IDs return a validation error. Product listing supports `category_id` alongside the existing search and low-stock filters.

## Sample catalogue

Run this from the repository root:

```text
python -m scripts.seed_catalogue
```

The seed adds twelve categories, six fictional suppliers, and 50 fictional products across computer hardware and IT equipment categories. `WM-001` Wireless Mouse is included without duplication. Existing products are never overwritten; a matching seeded product only receives a category link when it has none. Running the command again adds nothing.

The seed intentionally has no reset command. To remove demonstration data, use a disposable local database copy or delete only records you explicitly identify through the normal application workflow.
