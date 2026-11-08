import React, { useState, useEffect, useCallback } from "react";
import { Sparkles, RefreshCw, AlertTriangle, Info } from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import DataTable from "../components/DataTable";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Modal from "../components/Modal";
import ProductMatchesSection from "../components/ProductMatchesSection";
import ProductMatchesFilterBar from "../components/ProductMatchesFilterBar";
import { formatLanguage, getLanguageVariant } from "../utils/format";

export default function ProductMatches() {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "SUPER_ADMIN";

  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState("");
  const [entityTypeTab, setEntityTypeTab] = useState("lead");
  const [matches, setMatches] = useState([]);
  const [summary, setSummary] = useState(null);
  const [latestRun, setLatestRun] = useState(null);
  const [isStale, setIsStale] = useState(false);

  // Filters
  const [selectedBands, setSelectedBands] = useState([]);
  const [eligibilityFilter, setEligibilityFilter] = useState("");
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState("");

  const [pagination, setPagination] = useState({ page: 1, page_size: 15, total: 0, total_pages: 0 });
  const [loading, setLoading] = useState(true);
  const [scoringRunning, setScoringRunning] = useState(false);
  const [error, setError] = useState("");
  const [selectedMatch, setSelectedMatch] = useState(null);

  const loadMeta = useCallback(async () => {
    try {
      const [prodsData, runsData] = await Promise.all([
        api.get("/products"),
        api.get("/scoring/runs?page=1&page_size=1"),
      ]);
      setProducts(prodsData || []);
      const runs = runsData?.items || [];
      const run = runs[0] || null;
      setLatestRun(run);
      if (run?.finished_at) {
        const runFinished = new Date(run.finished_at).getTime();
        setIsStale((prodsData || []).some((p) => p.updated_at && new Date(p.updated_at).getTime() > runFinished));
      }
    } catch (err) { console.error("Failed loading metadata:", err); }
  }, []);

  useEffect(() => { loadMeta(); }, [loadMeta]);

  const fetchMatches = useCallback(
    async (page = 1) => {
      setLoading(true);
      setError("");
      const params = new URLSearchParams({ page, page_size: pagination.page_size, entity_type: entityTypeTab });
      if (selectedProductId) params.append("product_id", selectedProductId);
      if (eligibilityFilter) params.append("eligibility", eligibilityFilter);
      if (search.trim()) params.append("search", search.trim());
      if (minScore) params.append("min_score", minScore);
      selectedBands.forEach((b) => params.append("band", b));

      const summaryParams = new URLSearchParams({ entity_type: entityTypeTab });
      if (selectedProductId) summaryParams.append("product_id", selectedProductId);

      try {
        const [matchRes, summaryRes] = await Promise.all([
          api.get(`/matches?${params.toString()}`),
          api.get(`/matches/summary?${summaryParams.toString()}`),
        ]);
        setMatches(matchRes.items || []);
        setPagination(matchRes.pagination || { page: 1, page_size: 15, total: 0, total_pages: 0 });
        setSummary(summaryRes);
      } catch (err) { setError(err.message || "Failed to load product matches"); } finally { setLoading(false); }
    },
    [entityTypeTab, selectedProductId, selectedBands, eligibilityFilter, search, minScore, pagination.page_size]
  );

  useEffect(() => { fetchMatches(1); }, [fetchMatches]);

  const handleTriggerScoring = async () => {
    setScoringRunning(true);
    setError("");
    try {
      await api.post("/scoring/run", { entity_type: "both" });
      await loadMeta();
      await fetchMatches(1);
    } catch (err) { setError(err.message || "Scoring run failed."); } finally { setScoringRunning(false); }
  };

  const toggleBand = (b) => setSelectedBands((prev) => (prev.includes(b) ? prev.filter((x) => x !== b) : [...prev, b]));
  const resetFilters = () => { setSelectedProductId(""); setSelectedBands([]); setEligibilityFilter(""); setSearch(""); setMinScore(""); };

  const getBandBadge = (band) => {
    if (band === "HIGH") return <Badge variant="purple" className="text-[10px] px-1.5 py-0.5">HIGH</Badge>;
    if (band === "MEDIUM") return <Badge variant="info" className="text-[10px] px-1.5 py-0.5">MEDIUM</Badge>;
    return <Badge variant="default" className="text-[10px] px-1.5 py-0.5">LOW</Badge>;
  };

  const columns = [
    {
      header: entityTypeTab === "lead" ? "Lead Name" : "Customer Name",
      width: "24%",
      render: (row) => (
        <div className="truncate">
          <div className="font-semibold text-ink text-xs truncate">{row.entity_name || "Unknown"}</div>
          <div className="text-[10px] text-muted flex items-center gap-1.5 mt-0.5 truncate">
            <span>{row.entity_city || "Pan-India"}</span>
            {row.entity_language && (
              <Badge variant={getLanguageVariant(row.entity_language)} dot={false} className="text-[9px] px-1 py-0">
                {formatLanguage(row.entity_language)}
              </Badge>
            )}
          </div>
        </div>
      ),
    },
    {
      header: "Product",
      accessor: "product_name",
      width: "18%",
      render: (row) => (
        <span className="text-xs font-medium text-ink truncate block" title={row.product_name}>
          {row.product_name}
        </span>
      ),
    },
    {
      header: "Fit Score",
      width: "20%",
      render: (row) => (
        <div className="flex items-center gap-2">
          <div className="w-12 sm:w-16 h-1.5 rounded-full bg-surface-strong overflow-hidden shrink-0">
            <div className="h-full bg-ink/75 rounded-full" style={{ width: `${Math.min(row.match_score, 100)}%` }} />
          </div>
          <span className="font-mono text-xs font-semibold text-ink">{row.match_score.toFixed(1)}%</span>
        </div>
      ),
    },
    {
      header: "Band",
      width: "12%",
      render: (row) => getBandBadge(row.band),
    },
    {
      header: "Policy Eligibility",
      width: "14%",
      render: (row) => (
        <Badge variant={row.eligibility === "ELIGIBLE" ? "success" : "danger"} className="text-[10px] px-1.5 py-0.5">
          {row.eligibility === "ELIGIBLE" ? "Eligible" : "Not Eligible"}
        </Badge>
      ),
    },
    {
      header: "Compliance",
      width: "12%",
      className: "text-right",
      render: (row) => (
        <div className="flex items-center justify-end gap-1">
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${row.consent ? "text-emerald-700 bg-emerald-500/10 font-medium" : "text-muted-soft bg-surface-strong"}`}>
            {row.consent ? "Consent" : "No Cons."}
          </span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${row.dnd ? "text-rose-700 bg-rose-500/10 font-medium" : "text-muted bg-surface-strong"}`}>
            {row.dnd ? "DND" : "Clr"}
          </span>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5 w-full min-w-0 max-w-full font-sans">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-hairline">
        <div>
          <h1 className="t-h1 text-ink flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-muted" /> Product Matches & Propensity
          </h1>
          <p className="t-body text-muted mt-1">Deterministic policy rule evaluation combined with calibrated ML fit ranking.</p>
        </div>
        {isSuperAdmin && (
          <div className="flex items-center gap-3">
            {latestRun && (
              <span className="t-caption text-muted hidden sm:inline">
                Last run: {new Date(latestRun.finished_at || latestRun.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            <Button id="run-scoring-btn" variant="primary" onClick={handleTriggerScoring} disabled={scoringRunning}>
              <RefreshCw className={`w-4 h-4 mr-1.5 ${scoringRunning ? "animate-spin" : ""}`} />
              <span>{scoringRunning ? "Scoring..." : "Run Scoring"}</span>
            </Button>
          </div>
        )}
      </div>

      {isStale && (
        <div className="p-3.5 bg-amber-500/10 border border-amber-500/20 rounded-xl flex items-start gap-3 text-amber-900 t-caption">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div><strong className="text-amber-950">Catalog changes detected: </strong>Eligibility rules modified since last run. Run scoring to update fit and eligibility.</div>
        </div>
      )}

      <div className="p-3 bg-surface-card rounded-xl border border-hairline t-caption text-body flex items-center gap-2.5 shadow-soft">
        <Info className="w-4 h-4 text-muted shrink-0" />
        <span><strong className="text-ink">Ethical Standard: </strong>Fit score ranks likelihood of interest. Eligibility is decided by policy rules. A human approves every offer.</span>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="inline-flex p-1 bg-surface-card rounded-full border border-hairline shadow-soft">
          <button onClick={() => setEntityTypeTab("lead")} className={`px-5 py-1.5 rounded-full t-body-strong transition-all ${entityTypeTab === "lead" ? "bg-ink text-canvas shadow-sm" : "text-muted hover:text-ink"}`}>
            Leads ({summary && entityTypeTab === "lead" ? summary.total : "..."})
          </button>
          <button onClick={() => setEntityTypeTab("customer")} className={`px-5 py-1.5 rounded-full t-body-strong transition-all ${entityTypeTab === "customer" ? "bg-ink text-canvas shadow-sm" : "text-muted hover:text-ink"}`}>
            Customers ({summary && entityTypeTab === "customer" ? summary.total : "..."})
          </button>
        </div>
        <div className="flex items-center gap-2">
          <label className="t-caption text-muted shrink-0">Product Filter:</label>
          <select value={selectedProductId} onChange={(e) => setSelectedProductId(e.target.value)} className="bg-surface-card border border-hairline rounded-lg px-3 py-1.5 t-body text-ink">
            <option value="">All Active Products</option>
            {products.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
          </select>
        </div>
      </div>

      <ProductMatchesFilterBar
        summary={summary}
        search={search}
        setSearch={setSearch}
        eligibilityFilter={eligibilityFilter}
        setEligibilityFilter={setEligibilityFilter}
        minScore={minScore}
        setMinScore={setMinScore}
        selectedBands={selectedBands}
        toggleBand={toggleBand}
        resetFilters={resetFilters}
        entityTypeTab={entityTypeTab}
        selectedProductId={selectedProductId}
      />

      {error && <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-600 rounded-xl t-caption">{error}</div>}

      <DataTable
        columns={columns}
        data={matches}
        loading={loading}
        pagination={pagination}
        onPageChange={(p) => fetchMatches(p)}
        onRowClick={(row) => setSelectedMatch(row)}
        emptyMessage={summary?.total === 0 ? "Run scoring to generate matches across all active products." : "No product matches found."}
      />

      <Modal isOpen={!!selectedMatch} onClose={() => setSelectedMatch(null)} title={selectedMatch?.entity_name || "Match Details"}>
        {selectedMatch && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 bg-canvas p-4 rounded-xl border border-hairline">
              <div><span className="t-label text-muted block mb-1">Target Product</span><span className="t-body-strong text-ink">{selectedMatch.product_name}</span></div>
              <div><span className="t-label text-muted block mb-1">Fit Score & Band</span><span className="t-body-strong text-ink">{selectedMatch.match_score.toFixed(1)}% ({selectedMatch.band})</span></div>
            </div>
            <ProductMatchesSection entityType={selectedMatch.entity_type} entityId={selectedMatch.entity_id} />
          </div>
        )}
      </Modal>
    </div>
  );
}
