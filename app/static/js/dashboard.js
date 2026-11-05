const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

function displayValue(selector, value) {
  document.querySelector(selector).textContent = value;
}

function setSectionMessage(selector, message) {
  document.querySelector(selector).innerHTML = `<p class="empty-state">${message}</p>`;
}

function orderRow(order) {
  return `<tr><td>${order.order_number}</td><td>${order.customer_name}</td><td><span class="badge badge-${order.status}">${order.status}</span></td><td>${currency.format(Number(order.total))}</td></tr>`;
}

function renderDashboard(data) {
  displayValue("#metric-products", data.kpis.active_products);
  displayValue("#metric-orders", data.kpis.total_orders);
  displayValue("#metric-revenue", currency.format(Number(data.kpis.recognized_revenue)));
  displayValue("#metric-low-stock", data.kpis.low_stock_products);
  displayValue("#inventory-value", currency.format(Number(data.inventory.inventory_value)));
  displayValue("#inventory-alert-summary", `${data.inventory.out_of_stock_products} out of stock · ${data.inventory.low_stock_products} low stock`);

  const recentOrders = document.querySelector("#recent-orders-body");
  recentOrders.innerHTML = data.recent_orders.length
    ? data.recent_orders.map(orderRow).join("")
    : '<tr><td colspan="4" class="empty-state">No orders yet.</td></tr>';

  const statusList = document.querySelector("#status-list");
  statusList.innerHTML = data.order_statuses.map(item => `<li><span>${item.status}</span><strong>${item.count}</strong></li>`).join("");

  const bestSellers = document.querySelector("#best-sellers");
  bestSellers.innerHTML = data.best_selling_products.length
    ? data.best_selling_products.map(item => `<li><span>${item.product_name}</span><strong>${item.units_sold} units</strong></li>`).join("")
    : '<li class="empty-state">No recognized sales yet.</li>';

  new Chart(document.querySelector("#sales-trend-chart"), {
    type: "line",
    data: {
      labels: data.monthly_sales.map(item => item.month),
      datasets: [
        { label: "Revenue", data: data.monthly_sales.map(item => Number(item.revenue)), borderColor: "#5067d9", backgroundColor: "#5067d933", fill: true, tension: 0.35, yAxisID: "revenue" },
        { label: "Orders", data: data.monthly_sales.map(item => item.orders), borderColor: "#17a779", backgroundColor: "#17a77933", tension: 0.35, yAxisID: "orders" },
      ],
    },
    options: { responsive: true, maintainAspectRatio: false, scales: { revenue: { beginAtZero: true }, orders: { beginAtZero: true, position: "right", grid: { drawOnChartArea: false } } } },
  });
  new Chart(document.querySelector("#category-sales-chart"), { type: "bar", data: { labels: data.sales_by_category.map(item => item.category), datasets: [{ label: "Revenue", data: data.sales_by_category.map(item => Number(item.revenue)), backgroundColor: "#5067d9" }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } } });
  new Chart(document.querySelector("#stock-distribution-chart"), { type: "doughnut", data: { labels: ["Out of stock", "Low stock", "Healthy"], datasets: [{ data: [data.stock_distribution.out_of_stock, data.stock_distribution.low_stock, data.stock_distribution.healthy_stock], backgroundColor: ["#c94a4a", "#d68a20", "#17a779"] }] }, options: { responsive: true, maintainAspectRatio: false } });
}

async function loadDashboard() {
  try {
    const response = await fetch("/api/analytics/dashboard?days=180");
    if (!response.ok) throw new Error("Dashboard data is unavailable.");
    renderDashboard(await response.json());
  } catch (error) {
    document.querySelectorAll("[data-loading]").forEach(element => { element.textContent = "Unavailable"; });
    setSectionMessage("#recent-orders-container", "Dashboard data could not be loaded. Refresh to try again.");
    setSectionMessage("#status-container", "Dashboard data could not be loaded.");
    setSectionMessage("#best-sellers-container", "Dashboard data could not be loaded.");
  }
}

loadDashboard();
