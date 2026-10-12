const advisorList = document.querySelector("#advisor-list");
const advisorMessage = document.querySelector("#advisor-message");

function escapeAdvisorHtml(value) {
  return String(value).replace(/[&<>'"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}

function recommendationCard(item) {
  const reorder = item.suggested_reorder_quantity === null
    ? "No quantity suggested"
    : `Suggested reorder: <strong>${item.suggested_reorder_quantity}</strong>`;
  return `<article class="advisor-card severity-${item.severity}"><div class="advisor-card-head"><div><p class="product-sku">${escapeAdvisorHtml(item.sku)}</p><h2>${escapeAdvisorHtml(item.product_name)}</h2></div><span class="severity-label">${item.severity.replace("_", " ")}</span></div><dl><div><dt>In stock</dt><dd>${item.current_quantity}</dd></div><div><dt>Threshold</dt><dd>${item.reorder_threshold}</dd></div><div><dt>Recent sales</dt><dd>${item.recent_sales_units}</dd></div><div><dt>Recent depletion</dt><dd>${item.recent_depletion_units}</dd></div></dl><p>${escapeAdvisorHtml(item.reason)}</p><p class="reorder-suggestion">${reorder}</p></article>`;
}

async function loadAdvisor() {
  try {
    const response = await fetch("/api/advisor?days=30");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Advisor data is unavailable.");
    document.querySelector("#critical-count").textContent = data.summary.critical;
    document.querySelector("#warning-count").textContent = data.summary.warning;
    document.querySelector("#monitor-count").textContent = data.summary.monitor;
    document.querySelector("#history-count").textContent = data.summary.insufficient_history;
    advisorMessage.textContent = `Based on the last ${data.analysis_period_days} days of available data.`;
    advisorList.innerHTML = data.recommendations.length ? data.recommendations.map(recommendationCard).join("") : '<p class="empty-state">No inventory risks detected from the available data.</p>';
    document.querySelector("#advisor-note").textContent = data.data_note;
  } catch (error) {
    advisorMessage.textContent = error.message;
    advisorMessage.classList.add("error");
    advisorList.innerHTML = '<p class="empty-state">Recommendations could not be loaded. Refresh to try again.</p>';
  }
}

loadAdvisor();
