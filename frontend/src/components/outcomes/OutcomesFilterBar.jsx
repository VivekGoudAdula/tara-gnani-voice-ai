import React from "react";
import { Filter, RotateCcw, Search } from "lucide-react";
import Button from "../Button";
import Input from "../Input";

export default function OutcomesFilterBar({
  filters,
  onChange,
  onReset,
  campaigns = [],
}) {
  return (
    <div className="p-4 rounded-xl bg-surface-card border border-hairline space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-hairline">
        <div className="flex items-center gap-2 t-heading-xs text-ink">
          <Filter className="w-4 h-4 text-muted" /> Filter Outreach Outcomes
        </div>
        <Button variant="ghost" size="sm" onClick={onReset} className="text-muted hover:text-ink">
          <RotateCcw className="w-3.5 h-3.5 mr-1" /> Reset Filters
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {/* Search */}
        <div>
          <label className="block t-label text-xs text-muted mb-1">Search</label>
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 top-2.5" />
            <Input
              type="text"
              placeholder="Name or phone..."
              value={filters.search || ""}
              onChange={(e) => onChange("search", e.target.value)}
              className="pl-8 text-xs py-1.5 h-8 w-full"
            />
          </div>
        </div>

        {/* Campaign */}
        <div>
          <label className="block t-label text-xs text-muted mb-1">Campaign</label>
          <select
            value={filters.campaign_id || ""}
            onChange={(e) => onChange("campaign_id", e.target.value)}
            className="input-base text-xs py-1 px-2.5 h-8 w-full"
          >
            <option value="">All Campaigns</option>
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        {/* Test Run Tag */}
        <div>
          <label className="block t-label text-xs text-muted mb-1">Test Run Tag</label>
          <Input
            type="text"
            placeholder="e.g. phase5-evidence"
            value={filters.test_run_label || ""}
            onChange={(e) => onChange("test_run_label", e.target.value)}
            className="text-xs py-1.5 h-8 w-full font-mono"
          />
        </div>

        {/* Status */}
        <div>
          <label className="block t-label text-xs text-muted mb-1">Call Status</label>
          <select
            value={filters.status || ""}
            onChange={(e) => onChange("status", e.target.value)}
            className="input-base text-xs py-1 px-2.5 h-8 w-full"
          >
            <option value="">All Statuses</option>
            {["DISPATCHED", "IN_PROGRESS", "COMPLETED", "NO_ANSWER", "BUSY", "BLOCKED", "FAILED"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        {/* Outcome */}
        <div>
          <label className="block t-label text-xs text-muted mb-1">Outcome</label>
          <select
            value={filters.outcome || ""}
            onChange={(e) => onChange("outcome", e.target.value)}
            className="input-base text-xs py-1 px-2.5 h-8 w-full"
          >
            <option value="">All Outcomes</option>
            <option value="interested">Interested</option>
            <option value="callback">Callback</option>
            <option value="not_interested">Not Interested</option>
          </select>
        </div>
      </div>
    </div>
  );
}
