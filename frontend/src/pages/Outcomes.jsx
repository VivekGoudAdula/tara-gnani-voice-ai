import React, { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { BarChart3, RefreshCw, PhoneCall } from "lucide-react";
import Card from "../components/Card";
import Button from "../components/Button";
import Badge from "../components/Badge";
import OutcomesFilterBar from "../components/outcomes/OutcomesFilterBar";
import OutcomesSummaryCards from "../components/outcomes/OutcomesSummaryCards";
import OutcomesDistribution from "../components/outcomes/OutcomesDistribution";
import EvidencePanel from "../components/outcomes/EvidencePanel";
import CallDetailDrawer from "../components/outcomes/CallDetailDrawer";
import { api } from "../api/client";
import { formatDate } from "../utils/format";

export default function Outcomes() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [campaigns, setCampaigns] = useState([]);
  const [summary, setSummary] = useState(null);
  const [calls, setCalls] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, page_size: 20, total: 0, total_pages: 1 });
  const [loading, setLoading] = useState(true);
  const [selectedCallId, setSelectedCallId] = useState(null);

  // Read initial filter values from URL search params
  const [filters, setFilters] = useState({
    campaign_id: searchParams.get("campaign_id") || "",
    test_run_label: searchParams.get("test_run_label") || "",
    status: searchParams.get("status") || "",
    outcome: searchParams.get("outcome") || "",
    search: searchParams.get("search") || "",
    page: 1,
  });

  // Load campaigns for filter dropdown
  useEffect(() => {
    async function fetchCampaigns() {
      try {
        const res = await api.get("/campaigns?page_size=100");
        setCampaigns(res.items || []);
      } catch (err) {
        console.error("Failed to load campaigns list", err);
      }
    }
    fetchCampaigns();
  }, []);

  // Fetch summary and calls data
  const loadData = async () => {
    setLoading(true);
    try {
      const qParams = new URLSearchParams();
      if (filters.campaign_id) qParams.set("campaign_id", filters.campaign_id);
      if (filters.test_run_label) qParams.set("test_run_label", filters.test_run_label);
      if (filters.status) qParams.set("status", filters.status);
      if (filters.outcome) qParams.set("outcome", filters.outcome);
      if (filters.search) qParams.set("search", filters.search);

      // 1. Fetch Summary
      const sumRes = await api.get(`/outcomes/summary?${qParams.toString()}`);
      setSummary(sumRes);

      // 2. Fetch Paginated Calls
      qParams.set("page", filters.page || 1);
      qParams.set("page_size", 20);
      const callRes = await api.get(`/outcomes/calls?${qParams.toString()}`);
      setCalls(callRes.items || []);
      setPagination(callRes.pagination || { page: 1, page_size: 20, total: 0, total_pages: 1 });
    } catch (err) {
      console.error("Failed to fetch outcomes data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [filters]);

  const handleFilterChange = (key, val) => {
    setFilters((prev) => ({ ...prev, [key]: val, page: 1 }));
  };

  const handleResetFilters = () => {
    setFilters({ campaign_id: "", test_run_label: "", status: "", outcome: "", search: "", page: 1 });
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-hairline">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-primary" />
            <h1 className="t-heading-md text-ink">Outcomes & Pipeline Evidence</h1>
          </div>
          <p className="t-body-sm text-muted mt-1">
            Real data captured directly from telephony and voice agent session webhooks. No placeholder estimations.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </div>

      {/* SUPER_ADMIN Evidence Panel */}
      <EvidencePanel
        currentTestRunLabel={filters.test_run_label}
        onSelectLabel={(lbl) => handleFilterChange("test_run_label", lbl)}
      />

      {/* Summary Metrics */}
      <OutcomesSummaryCards summary={summary} />

      {/* Distribution & Integrity Panels */}
      <OutcomesDistribution summary={summary} />

      {/* Filter Bar */}
      <OutcomesFilterBar
        filters={filters}
        onChange={handleFilterChange}
        onReset={handleResetFilters}
        campaigns={campaigns}
      />

      {/* Calls Table */}
      <Card className="p-0 overflow-hidden bg-surface-card">
        <div className="p-4 border-b border-hairline flex items-center justify-between">
          <h3 className="t-heading-xs text-ink flex items-center gap-2">
            <PhoneCall className="w-4 h-4 text-muted" /> Outreach Call Logs ({pagination.total})
          </h3>
          <span className="t-body-xs text-muted">Click row for transcript & lifecycle timeline</span>
        </div>

        <div className="w-full overflow-hidden">
          <table className="w-full text-left border-collapse table-fixed">
            <colgroup>
              <col style={{ width: "22%" }} />
              <col style={{ width: "18%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "10%" }} />
              <col style={{ width: "10%" }} />
              <col style={{ width: "14%" }} />
            </colgroup>
            <thead>
              <tr className="border-b border-hairline bg-surface-strong/50 text-muted text-[11px] font-semibold uppercase tracking-wider">
                <th className="py-2 px-2.5">Recipient</th>
                <th className="py-2 px-2.5">Campaign</th>
                <th className="py-2 px-2.5">Status</th>
                <th className="py-2 px-2.5">Outcome</th>
                <th className="py-2 px-2.5">Duration</th>
                <th className="py-2 px-2.5">Language</th>
                <th className="py-2 px-2.5 text-right">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {calls.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-10 text-center text-muted text-xs">
                    No outreach calls found matching current criteria.
                  </td>
                </tr>
              ) : (
                calls.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => setSelectedCallId(c.id)}
                    className="hover:bg-surface-strong/40 cursor-pointer transition-colors"
                  >
                    <td className="py-2 px-2.5 truncate">
                      <div className="font-semibold text-ink text-xs truncate">{c.recipient_name}</div>
                      <div className="text-[10px] font-mono text-muted">{c.phone_masked}</div>
                    </td>
                    <td className="py-2 px-2.5 text-xs font-medium text-body truncate" title={c.campaign_name}>
                      {c.campaign_name || "—"}
                    </td>
                    <td className="py-2 px-2.5">
                      <Badge
                        variant={
                          c.status === "COMPLETED"
                            ? "success"
                            : c.status === "BLOCKED"
                            ? "warning"
                            : c.status === "FAILED"
                            ? "danger"
                            : "default"
                        }
                        className="text-[10px] px-1.5 py-0.5"
                      >
                        {c.status}
                      </Badge>
                    </td>
                    <td className="py-2 px-2.5 text-xs font-semibold truncate">
                      {c.outcome?.interest_level ? (
                        <span
                          className={
                            c.outcome.interest_level.toLowerCase().includes("interested")
                              ? "text-emerald-700"
                              : c.outcome.interest_level.toLowerCase().includes("callback")
                              ? "text-amber-700"
                              : "text-muted"
                          }
                        >
                          {c.outcome.interest_level}
                        </span>
                      ) : (
                        <span className="text-muted-soft font-normal">—</span>
                      )}
                    </td>
                    <td className="py-2 px-2.5 text-xs font-mono text-ink">
                      {c.duration_seconds !== null && c.duration_seconds !== undefined ? `${c.duration_seconds}s` : "—"}
                    </td>
                    <td className="py-2 px-2.5 text-xs uppercase font-mono text-muted truncate">
                      {c.language_used || "—"}
                    </td>
                    <td className="py-2 px-2.5 text-right text-[11px] text-muted font-mono truncate">
                      {formatDate(c.created_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        {pagination.total_pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-hairline bg-surface-strong/30 t-body-xs">
            <span className="text-muted">
              Page {pagination.page} of {pagination.total_pages} ({pagination.total} total calls)
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={pagination.page <= 1}
                onClick={() => handleFilterChange("page", Math.max(1, pagination.page - 1))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={pagination.page >= pagination.total_pages}
                onClick={() => handleFilterChange("page", pagination.page + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Call Detail Drawer */}
      <CallDetailDrawer callId={selectedCallId} onClose={() => setSelectedCallId(null)} />
    </div>
  );
}
