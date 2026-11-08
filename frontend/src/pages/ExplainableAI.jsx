import React, { useState, useEffect, useCallback } from "react";
import { HelpCircle, Sparkles, Filter, CheckCircle2, XCircle, ChevronRight, Info } from "lucide-react";
import { api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Modal from "../components/Modal";
import ProductMatchesSection from "../components/ProductMatchesSection";

export default function ExplainableAI() {
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState("");
  const [entityTypeTab, setEntityTypeTab] = useState("lead");
  const [selectedBand, setSelectedBand] = useState("");
  const [eligibilityFilter, setEligibilityFilter] = useState("");
  const [search, setSearch] = useState("");

  const [matches, setMatches] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, page_size: 15, total: 0, total_pages: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [inspectMatch, setInspectMatch] = useState(null);

  useEffect(() => {
    api.get("/products")
      .then((data) => setProducts(data || []))
      .catch((err) => console.error("Failed to load products:", err));
  }, []);

  const fetchMatches = useCallback(async (page = 1) => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams({
      page,
      page_size: pagination.page_size,
      entity_type: entityTypeTab,
    });
    if (selectedProductId) params.append("product_id", selectedProductId);
    if (selectedBand) params.append("band", selectedBand);
    if (eligibilityFilter) params.append("eligibility", eligibilityFilter);
    if (search.trim()) params.append("search", search.trim());

    try {
      const res = await api.get(`/matches?${params.toString()}`);
      setMatches(res.items || []);
      setPagination(res.pagination || { page: 1, page_size: 15, total: 0, total_pages: 0 });
    } catch (err) {
      setError(err.message || "Failed to load explainable AI matches.");
    } finally {
      setLoading(false);
    }
  }, [entityTypeTab, selectedProductId, selectedBand, eligibilityFilter, search, pagination.page_size]);

  useEffect(() => {
    fetchMatches(1);
  }, [fetchMatches]);

  const getBandBadge = (band) => {
    if (band === "HIGH") return <Badge variant="purple">HIGH</Badge>;
    if (band === "MEDIUM") return <Badge variant="info">MEDIUM</Badge>;
    return <Badge variant="default">LOW</Badge>;
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Header */}
      <div className="pb-2 border-b border-hairline">
        <h1 className="t-h1 text-ink flex items-center gap-2">
          <HelpCircle className="w-5 h-5 text-muted" />
          Explainable AI & Propensity Rationale
        </h1>
        <p className="t-body text-muted mt-1">
          Transparent decision lineage: deterministic policy checks, Shapley-aligned ML reason codes, and imputation audits.
        </p>
      </div>

      <div className="p-3 bg-surface-card rounded-xl border border-hairline t-caption text-body flex items-center gap-2.5 shadow-soft">
        <Info className="w-4 h-4 text-muted shrink-0" />
        <span>
          <strong className="text-ink">Explainability Policy: </strong>
          Every score is fully auditable. Propensity models rank interest probability; deterministic rules govern product eligibility.
        </span>
      </div>

      {/* Filters Bar */}
      <div className="bg-surface-card p-4 rounded-2xl border border-hairline shadow-soft space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {/* Entity Tab */}
          <div className="inline-flex p-1 bg-canvas rounded-full border border-hairline">
            <button
              onClick={() => setEntityTypeTab("lead")}
              className={`px-4 py-1 rounded-full text-xs font-semibold transition-all ${
                entityTypeTab === "lead" ? "bg-ink text-canvas shadow-sm" : "text-muted hover:text-ink"
              }`}
            >
              Leads
            </button>
            <button
              onClick={() => setEntityTypeTab("customer")}
              className={`px-4 py-1 rounded-full text-xs font-semibold transition-all ${
                entityTypeTab === "customer" ? "bg-ink text-canvas shadow-sm" : "text-muted hover:text-ink"
              }`}
            >
              Customers
            </button>
          </div>

          {/* Search */}
          <input
            type="text"
            placeholder="Search by name or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-canvas border border-hairline rounded-lg px-3 py-1.5 text-xs text-ink w-full sm:w-60"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-hairline text-xs">
          <div>
            <label className="text-muted block mb-1">Target Product</label>
            <select
              value={selectedProductId}
              onChange={(e) => setSelectedProductId(e.target.value)}
              className="w-full bg-canvas border border-hairline rounded-lg px-2.5 py-1.5 text-xs text-ink"
            >
              <option value="">All Products</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-muted block mb-1">Propensity Band</label>
            <select
              value={selectedBand}
              onChange={(e) => setSelectedBand(e.target.value)}
              className="w-full bg-canvas border border-hairline rounded-lg px-2.5 py-1.5 text-xs text-ink"
            >
              <option value="">All Bands (HIGH, MED, LOW)</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>
          </div>

          <div>
            <label className="text-muted block mb-1">Policy Eligibility</label>
            <select
              value={eligibilityFilter}
              onChange={(e) => setEligibilityFilter(e.target.value)}
              className="w-full bg-canvas border border-hairline rounded-lg px-2.5 py-1.5 text-xs text-ink"
            >
              <option value="">All Statuses</option>
              <option value="ELIGIBLE">Eligible Only</option>
              <option value="INELIGIBLE">Ineligible Only</option>
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-600 rounded-xl t-caption">{error}</div>
      )}

      {/* Matches List with Reason Codes & Checks */}
      <div className="space-y-3">
        {loading ? (
          <div className="p-12 text-center text-muted t-body bg-surface-card rounded-2xl border border-hairline">
            Loading explainable decision records...
          </div>
        ) : matches.length === 0 ? (
          <div className="p-8 text-center text-muted t-caption bg-surface-card rounded-2xl border border-hairline">
            No matches found for the selected criteria.
          </div>
        ) : (
          matches.map((row) => (
            <div
              key={row.id}
              onClick={() => setInspectMatch(row)}
              className="bg-surface-card p-4 rounded-2xl border border-hairline shadow-soft hover:border-indigo-300 cursor-pointer transition-all space-y-3"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="t-body-strong text-ink">{row.entity_name}</span>
                    <span className="text-xs text-muted">({row.product_name})</span>
                  </div>
                  <div className="t-caption text-muted mt-0.5">
                    {row.entity_city || "Pan-India"} • Language: {row.entity_language || "english"}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span className="t-body-strong text-ink">{row.match_score.toFixed(1)}%</span>
                  {getBandBadge(row.band)}
                  <Badge variant={row.eligibility === "ELIGIBLE" ? "success" : "danger"}>
                    {row.eligibility === "ELIGIBLE" ? "Eligible" : "Ineligible"}
                  </Badge>
                  <Button variant="ghost" size="sm" className="ml-1">
                    <span>Inspect Why</span>
                    <ChevronRight className="w-3.5 h-3.5 ml-1" />
                  </Button>
                </div>
              </div>

              {/* Rationale previews: Top reason code + policy summary */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-2 border-t border-hairline text-xs">
                {/* Top Reason Code */}
                <div className="p-2 rounded-lg bg-canvas border border-hairline flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
                  <span className="text-muted truncate">
                    {row.reason_codes?.[0]
                      ? `${row.reason_codes[0].direction === "positive" ? "+" : ""}${row.reason_codes[0].contribution_pp.toFixed(1)}pp: ${row.reason_codes[0].text}`
                      : "Standard model baseline evaluation"}
                  </span>
                </div>

                {/* Eligibility Checks Summary */}
                <div className="p-2 rounded-lg bg-canvas border border-hairline flex items-center gap-2">
                  {row.eligibility === "ELIGIBLE" ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  ) : (
                    <XCircle className="w-3.5 h-3.5 text-rose-600 shrink-0" />
                  )}
                  <span className="text-muted truncate">
                    {row.eligibility_checks?.filter((c) => c.passed).length || 0} of {row.eligibility_checks?.length || 0} policy rules passed
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {pagination.total_pages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-xs text-muted">
            Showing page {pagination.page} of {pagination.total_pages} ({pagination.total} matches)
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page <= 1}
              onClick={() => fetchMatches(pagination.page - 1)}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page >= pagination.total_pages}
              onClick={() => fetchMatches(pagination.page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Why Modal */}
      <Modal
        isOpen={!!inspectMatch}
        onClose={() => setInspectMatch(null)}
        title={inspectMatch?.entity_name ? `Why Rationale: ${inspectMatch.entity_name}` : "Decision Lineage"}
      >
        {inspectMatch && (
          <div className="space-y-4 font-sans">
            <div className="grid grid-cols-2 gap-3 bg-canvas p-4 rounded-xl border border-hairline">
              <div>
                <span className="t-label text-muted block mb-1">Target Product</span>
                <span className="t-body-strong text-ink">{inspectMatch.product_name}</span>
              </div>
              <div>
                <span className="t-label text-muted block mb-1">Fit Score & Band</span>
                <span className="t-body-strong text-ink">
                  {inspectMatch.match_score.toFixed(1)}% ({inspectMatch.band})
                </span>
              </div>
            </div>
            <ProductMatchesSection
              entityType={inspectMatch.entity_type}
              entityId={inspectMatch.entity_id}
            />
          </div>
        )}
      </Modal>
    </div>
  );
}
