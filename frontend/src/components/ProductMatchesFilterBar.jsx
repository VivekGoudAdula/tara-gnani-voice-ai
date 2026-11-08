import React from "react";
import { Search } from "lucide-react";
import Card from "./Card";

export default function ProductMatchesFilterBar({
  summary,
  search,
  setSearch,
  eligibilityFilter,
  setEligibilityFilter,
  minScore,
  setMinScore,
  selectedBands,
  toggleBand,
  resetFilters,
  entityTypeTab,
  selectedProductId,
}) {
  const hasActiveFilters = Boolean(
    search || eligibilityFilter || minScore || selectedBands.length > 0 || selectedProductId
  );

  return (
    <div className="space-y-4 font-sans">
      {/* Summary KPI Cards (Counts always sum to total) */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <Card className="p-3.5 bg-surface-card border-hairline">
            <span className="t-label text-muted block mb-1">Total Scored</span>
            <span className="t-h2 text-ink block">{summary.total.toLocaleString()}</span>
            <span className="t-caption text-muted-soft mt-0.5 block">Avg {summary.avg_score.toFixed(1)}%</span>
          </Card>
          <Card className="p-3.5 bg-surface-card border-hairline">
            <span className="t-label text-muted block mb-1">High Fit</span>
            <span className="t-h2 text-indigo-600 block">{summary.by_band.HIGH || 0}</span>
            <span className="t-caption text-muted-soft mt-0.5 block">≥ {summary.thresholds.threshold_high}%</span>
          </Card>
          <Card className="p-3.5 bg-surface-card border-hairline">
            <span className="t-label text-muted block mb-1">Medium Fit</span>
            <span className="t-h2 text-sky-600 block">{summary.by_band.MEDIUM || 0}</span>
            <span className="t-caption text-muted-soft mt-0.5 block">≥ {summary.thresholds.threshold_low}%</span>
          </Card>
          <Card className="p-3.5 bg-surface-card border-hairline">
            <span className="t-label text-muted block mb-1">Low Fit</span>
            <span className="t-h2 text-muted block">{summary.by_band.LOW || 0}</span>
            <span className="t-caption text-muted-soft mt-0.5 block">&lt; {summary.thresholds.threshold_low}%</span>
          </Card>
          <Card className="p-3.5 bg-surface-card border-hairline">
            <span className="t-label text-muted block mb-1">Eligible</span>
            <span className="t-h2 text-emerald-600 block">{summary.by_eligibility.ELIGIBLE || 0}</span>
            <span className="t-caption text-muted-soft mt-0.5 block">Passed rules</span>
          </Card>
          <Card className="p-3.5 bg-surface-card border-hairline">
            <span className="t-label text-muted block mb-1">Not Eligible</span>
            <span className="t-h2 text-rose-600 block">{summary.by_eligibility.NOT_ELIGIBLE || 0}</span>
            <span className="t-caption text-muted-soft mt-0.5 block">Policy gated</span>
          </Card>
        </div>
      )}

      {/* Filters Bar */}
      <div className="p-4 bg-surface-card rounded-2xl border border-hairline space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search by Name */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-4 h-4 text-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder={`Search ${entityTypeTab}s by name...`}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-canvas border border-hairline rounded-full pl-9 pr-4 py-1.5 t-body text-ink focus:outline-none focus:ring-1 focus:ring-ink"
            />
          </div>

          {/* Eligibility Filter */}
          <select
            value={eligibilityFilter}
            onChange={(e) => setEligibilityFilter(e.target.value)}
            className="bg-canvas border border-hairline rounded-full px-3.5 py-1.5 t-body text-ink focus:outline-none"
          >
            <option value="">All Eligibility</option>
            <option value="ELIGIBLE">Eligible Only</option>
            <option value="NOT_ELIGIBLE">Not Eligible Only</option>
          </select>

          {/* Score Range Min */}
          <select
            value={minScore}
            onChange={(e) => setMinScore(e.target.value)}
            className="bg-canvas border border-hairline rounded-full px-3.5 py-1.5 t-body text-ink focus:outline-none"
          >
            <option value="">Any Fit Score</option>
            <option value="70">≥ 70% Score</option>
            <option value="50">≥ 50% Score</option>
            <option value="30">≥ 30% Score</option>
          </select>

          {/* Band Chips (Multi-select) */}
          <div className="flex items-center gap-1.5 pl-2">
            <span className="t-caption text-muted mr-1">Bands:</span>
            {["HIGH", "MEDIUM", "LOW"].map((b) => {
              const active = selectedBands.includes(b);
              return (
                <button
                  key={b}
                  onClick={() => toggleBand(b)}
                  className={`px-3 py-1 rounded-full t-label transition-colors ${
                    active ? "bg-ink text-canvas" : "bg-canvas border border-hairline text-muted hover:text-ink"
                  }`}
                >
                  {b}
                </button>
              );
            })}
          </div>

          {hasActiveFilters && (
            <button onClick={resetFilters} className="t-caption text-muted hover:text-ink underline ml-auto">
              Reset Filters
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
