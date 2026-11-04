const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const productList = document.querySelector("#product-image-list");
const message = document.querySelector("#product-image-message");
const searchInput = document.querySelector("#product-search");
const categoryFilter = document.querySelector("#category-filter");
const form = document.querySelector("#product-form");

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}

function showMessage(text, type = "") {
  message.textContent = text;
  message.className = `operation-message ${type}`;
}

function card(product) {
  const image = `<img src="${escapeHtml(catalogueImages.sourceFor(product))}" onerror="catalogueImages.recover(this,'${encodeURIComponent(String(product.sku))}')" alt="${escapeHtml(product.name)}">`;
  const remove = product.image_key ? `<button class="secondary-button remove-image" data-product-id="${product.id}">Remove image</button>` : "";
  return `<article class="product-image-card"><div class="product-thumb">${image}</div><div><p class="product-sku">${escapeHtml(product.sku)} · ${escapeHtml(product.category || "Uncategorised")}</p><h2>${escapeHtml(product.name)}</h2><p>${escapeHtml(product.description || "No description")}</p><p>Stock: <strong>${product.quantity}</strong> · Reorder at ${product.reorder_threshold}</p><button class="secondary-button edit-product" data-product-id="${product.id}">Edit</button><label class="upload-button">${product.image_key ? "Replace image" : "Upload image"}<input class="image-input" data-product-id="${product.id}" type="file" accept="image/jpeg,image/png,image/webp" hidden></label>${remove}</div></article>`;
}

async function loadProducts() {
  try {
    const query = new URLSearchParams({ page: "1", page_size: "100" });
    if (searchInput.value.trim()) query.set("search", searchInput.value.trim());
    if (categoryFilter.value) query.set("category_id", categoryFilter.value);
    const response = await fetch(`/api/products?${query}`);
    if (!response.ok) throw new Error("Could not load products.");
    const data = await response.json();
    productList.innerHTML = data.items.length ? data.items.map(card).join("") : '<p class="empty-state">No active products yet.</p>';
  } catch (error) {
    productList.innerHTML = '<p class="empty-state">Products are unavailable. Refresh to try again.</p>';
  }
}

async function uploadImage(productId, file) {
  const formData = new FormData();
  formData.append("file", file);
  showMessage("Uploading image…");
  const response = await fetch(`/api/products/${productId}/image`, { method: "POST", headers: { "X-CSRF-Token": csrfToken }, body: formData });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Image upload failed.");
  showMessage("Image saved securely.", "success");
}

productList.addEventListener("change", async event => {
  if (!event.target.matches(".image-input") || !event.target.files[0]) return;
  try { await uploadImage(event.target.dataset.productId, event.target.files[0]); await loadProducts(); }
  catch (error) { showMessage(error.message, "error"); }
});

productList.addEventListener("click", async event => {
  if (!event.target.matches(".remove-image")) return;
  try {
    showMessage("Removing image…");
    const response = await fetch(`/api/products/${event.target.dataset.productId}/image`, { method: "DELETE", headers: { "X-CSRF-Token": csrfToken } });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Image removal failed.");
    showMessage("Image removed.", "success");
    await loadProducts();
  } catch (error) { showMessage(error.message, "error"); }
});

async function loadCategories() {
  const response = await fetch("/api/categories");
  if (!response.ok) throw new Error("Could not load categories.");
  const categories = await response.json();
  const options = categories.map(category => `<option value="${category.id}">${escapeHtml(category.name)}</option>`).join("");
  categoryFilter.innerHTML = `<option value="">All categories</option>${options}`;
  document.querySelector("#product-category").innerHTML = `<option value="">Select a category</option>${options}`;
}

function resetForm() {
  form.reset(); form.hidden = true;
  document.querySelector("#product-id").value = "";
  document.querySelector("#product-sku").disabled = false;
  document.querySelector("#product-quantity").disabled = false;
}

async function editProduct(productId) {
  const response = await fetch(`/api/products/${productId}`);
  const product = await response.json();
  form.hidden = false;
  document.querySelector("#product-id").value = product.id;
  document.querySelector("#product-sku").value = product.sku; document.querySelector("#product-sku").disabled = true;
  document.querySelector("#product-name").value = product.name;
  document.querySelector("#product-category").value = product.category_id || "";
  document.querySelector("#product-description").value = product.description || "";
  document.querySelector("#product-price").value = product.price; document.querySelector("#product-cost").value = product.cost;
  document.querySelector("#product-quantity").value = product.quantity; document.querySelector("#product-quantity").disabled = true;
  document.querySelector("#product-threshold").value = product.reorder_threshold;
}

document.querySelector("#new-product").addEventListener("click", () => { resetForm(); form.hidden = false; });
document.querySelector("#cancel-product").addEventListener("click", resetForm);
searchInput.addEventListener("input", loadProducts);
categoryFilter.addEventListener("change", loadProducts);
productList.addEventListener("click", event => { if (event.target.matches(".edit-product")) editProduct(event.target.dataset.productId); });
form.addEventListener("submit", async event => {
  event.preventDefault();
  const id = document.querySelector("#product-id").value;
  const payload = { name: document.querySelector("#product-name").value, category_id: Number(document.querySelector("#product-category").value), description: document.querySelector("#product-description").value || null, price: document.querySelector("#product-price").value, cost: document.querySelector("#product-cost").value, reorder_threshold: Number(document.querySelector("#product-threshold").value) };
  if (!id) { payload.sku = document.querySelector("#product-sku").value; payload.quantity = Number(document.querySelector("#product-quantity").value); }
  const response = await fetch(id ? `/api/products/${id}` : "/api/products", { method: id ? "PATCH" : "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken }, body: JSON.stringify(payload) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) return showMessage(data.detail || "Product could not be saved.", "error");
  showMessage(id ? "Product updated." : "Product created.", "success"); resetForm(); loadProducts();
});
Promise.all([loadCategories(), catalogueImages.load()]).then(loadProducts).catch(error => { productList.innerHTML = `<p class="empty-state">${escapeHtml(error.message)}</p>`; });
