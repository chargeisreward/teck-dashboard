const API_BASE = "/api";

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export function getDashboardSummary() {
  return fetchJSON(`${API_BASE}/dashboard/summary`);
}

export function getCompanies() {
  return fetchJSON(`${API_BASE}/companies`);
}

export function getCompany(id) {
  return fetchJSON(`${API_BASE}/companies/${id}`);
}

export function getCompanyFinancials(id) {
  return fetchJSON(`${API_BASE}/companies/${id}/financials`);
}

export function getCompanyForecasts(id) {
  return fetchJSON(`${API_BASE}/companies/${id}/forecasts`);
}

export function getProducts(category) {
  const params = category ? `?category=${encodeURIComponent(category)}` : "";
  return fetchJSON(`${API_BASE}/products${params}`);
}

export function getMarketData(companyId, days = 90) {
  const params = new URLSearchParams();
  if (companyId) params.set("company_id", companyId);
  params.set("days", days);
  return fetchJSON(`${API_BASE}/market-data?${params}`);
}

export function getStorage(storageType) {
  const params = storageType ? `?storage_type=${encodeURIComponent(storageType)}` : "";
  return fetchJSON(`${API_BASE}/storage${params}`);
}

export function getCategories() {
  return fetchJSON(`${API_BASE}/categories`);
}

// ── 新增 API ────────────────────────────────────────────────────

export function getChainLinks() {
  return fetchJSON(`${API_BASE}/chain-links`);
}

export function getChainLink(id) {
  return fetchJSON(`${API_BASE}/chain-links/${id}`);
}

export function getChainLinkCompanies(id) {
  return fetchJSON(`${API_BASE}/chain-links/${id}/companies`);
}

export function getIndustryOverview() {
  return fetchJSON(`${API_BASE}/industry-overview`);
}

export function getSupplyDemand(chainLinkId, period) {
  const params = new URLSearchParams();
  if (chainLinkId) params.set("chain_link_id", chainLinkId);
  if (period) params.set("period", period);
  return fetchJSON(`${API_BASE}/supply-demand?${params}`);
}

export function getIndicators(category) {
  const params = category ? `?category=${encodeURIComponent(category)}` : "";
  return fetchJSON(`${API_BASE}/indicators${params}`);
}

export function getIndicatorCategories() {
  return fetchJSON(`${API_BASE}/indicator-categories`);
}

export function getIndicator(id) {
  return fetchJSON(`${API_BASE}/indicators/${id}`);
}

export function getIndicatorObservations(id, limit = 90) {
  return fetchJSON(`${API_BASE}/indicators/${id}/observations?limit=${limit}`);
}

export function getJudgmentLogs() {
  return fetchJSON(`${API_BASE}/judgment-logs`);
}

export function createJudgmentLog(data) {
  return fetch(`${API_BASE}/judgment-logs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }).then((r) => r.json());
}

export function getScoringDimensions() {
  return fetchJSON(`${API_BASE}/scoring/dimensions`);
}

export function getCompanyScores() {
  return fetchJSON(`${API_BASE}/scoring/scores`);
}

export function getPortfolios() {
  return fetchJSON(`${API_BASE}/portfolios`);
}

export function getPortfolio(id) {
  return fetchJSON(`${API_BASE}/portfolios/${id}`);
}

export function getPortfolioHoldings(id) {
  return fetchJSON(`${API_BASE}/portfolios/${id}/holdings`);
}

export function getPortfolioPerformance(id, limit = 60) {
  return fetchJSON(`${API_BASE}/portfolios/${id}/performance?limit=${limit}`);
}

export function getPortfolioEvaluations(id) {
  return fetchJSON(`${API_BASE}/portfolios/${id}/evaluations`);
}

export function evaluatePortfolio(id) {
  return fetch(`${API_BASE}/portfolios/${id}/evaluate`, { method: "POST" }).then((r) => r.json());
}

// ── 组合跟踪 ───────────────────────────────────────────────────

export function getFolioTracking() {
  return fetchJSON(`${API_BASE}/portfolio/tracking`);
}

export function updateFolioWeight(followId, weight) {
  return fetch(`${API_BASE}/portfolio/weight/${followId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ weight }),
  }).then((r) => r.json());
}

// ── 估值模型 ────────────────────────────────────────────────────

export function getValuationPeerGroups() {
  return fetchJSON(`${API_BASE}/valuation/peer-groups`);
}

export function getValuationCompanies(peerGroup) {
  const params = peerGroup ? `?peer_group=${encodeURIComponent(peerGroup)}` : "";
  return fetchJSON(`${API_BASE}/valuation/companies${params}`);
}

export function calculateValuation(params) {
  return fetch(`${API_BASE}/valuation/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  }).then((r) => r.json());
}

// ── 价格数据 ─────────────────────────────────────────────────────

export function getPriceHistory(ticker, days = 90) {
  return fetchJSON(`${API_BASE}/price/${ticker}?days=${days}`);
}

export function getStockInfo(ticker) {
  return fetchJSON(`${API_BASE}/stock-info/${ticker}`);
}

export function getSmartPrice(companyName, days = 90) {
  return fetchJSON(`${API_BASE}/price/smart/${encodeURIComponent(companyName)}?days=${days}`);
}

export function getHotStocks() {
  return fetchJSON(`${API_BASE}/market/hot-stocks`);
}

// ── 估值模型 v2 (供需感知未来 PE) ─────────────────────────────

export function getChainScores() {
  return fetchJSON(`${API_BASE}/valuation-v2/chain-scores`);
}

export function getCompanyAdjustments(peerGroup) {
  const params = peerGroup ? `?peer_group=${encodeURIComponent(peerGroup)}` : "";
  return fetchJSON(`${API_BASE}/valuation-v2/company-adjustments${params}`);
}

export function calculateFuturePE(params) {
  return fetch(`${API_BASE}/valuation-v2/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  }).then((r) => r.json());
}

// ── 产业数据 API (Industry Data) ──────────────────────────────────

export function getIndustryIndicators(category, source) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (source) params.set("source", source);
  const qs = params.toString();
  return fetchJSON(`${API_BASE}/industry/indicators${qs ? "?" + qs : ""}`);
}

export function getIndustryIndicator(id) {
  return fetchJSON(`${API_BASE}/industry/indicators/${id}`);
}

export function triggerIndustryCollect(source) {
  const params = source ? `?source=${encodeURIComponent(source)}` : "";
  return fetch(`${API_BASE}/industry/collect${params}`, { method: "POST" }).then((r) => r.json());
}

export function getIndustryDataSources() {
  return fetchJSON(`${API_BASE}/industry/data-sources`);
}

// ── 时间线 API ─────────────────────────────────────────────────────

export function getTimeline(limit = 50, offset = 0, eventType) {
  const params = new URLSearchParams();
  params.set("limit", limit);
  params.set("offset", offset);
  if (eventType) params.set("event_type", eventType);
  return fetchJSON(`${API_BASE}/timeline?${params}`);
}

// ── 产业情报统一接口 ───────────────────────────────────────────────

export function getIndustryIntelligence() {
  return fetchJSON(`${API_BASE}/industry-intelligence`);
}

// ── 产业情报新增API ────────────────────────────────────────────

export function getSequenceTimeline(limit = 50, offset = 0) {
  const params = new URLSearchParams();
  params.set("limit", limit);
  params.set("offset", offset);
  return fetchJSON(`${API_BASE}/industry/sequence-timeline?${params}`);
}

export function triggerBatchAnalyze() {
  return fetch(`${API_BASE}/industry/batch-analyze`, { method: "POST" }).then((r) => r.json());
}

export function getCompanyDataBrowse() {
  return fetchJSON(`${API_BASE}/industry/company-data`);
}

// ── 关注 / 核心公司 ────────────────────────────────────────────

export function getFollows() {
  return fetchJSON(`${API_BASE}/user/follows`);
}

export function followCompany(companyId) {
  return fetch(`${API_BASE}/user/follow/${companyId}`, { method: "POST" }).then((r) => {
    if (!r.ok) return r.json().then((e) => { throw new Error(e.detail || "关注失败"); });
    return r.json();
  });
}

export function unfollowCompany(companyId) {
  return fetch(`${API_BASE}/user/follow/${companyId}`, { method: "DELETE" }).then((r) => {
    if (!r.ok) return r.json().then((e) => { throw new Error(e.detail || "取消关注失败"); });
    return r.json();
  });
}

export function getDashboardOverview() {
  return fetchJSON(`${API_BASE}/dashboard/overview`);
}

export function refreshFollowPrices() {
  return fetch(`${API_BASE}/user/follows/refresh-prices`, { method: "POST" }).then((r) => r.json());
}
