import React, { useState, useEffect, useCallback } from "react";
import { useSearchParams, Link } from "react-router-dom";
import {
  MessageSquare,
  PhoneCall,
  Search,
  Filter,
  RefreshCw,
  Sparkles,
  Clock,
  CheckCircle2,
  AlertCircle,
  Tag,
  ArrowRight,
} from "lucide-react";
import { api } from "../api/client";
import Card from "../components/Card";
import Button from "../components/Button";
import Badge from "../components/Badge";
import CallDetailDrawer from "../components/outcomes/CallDetailDrawer";
import { formatDate } from "../utils/format";

export default function Conversations() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [campaigns, setCampaigns] = useState([]);
  const [calls, setCalls] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedCallId, setSelectedCallId] = useState(null);

  // Filters state
  const [filters, setFilters] = useState({
    campaign_id: searchParams.get("campaign_id") || "",
    status: searchParams.get("status") || "",
    outcome: searchParams.get("outcome") || "",
    search: searchParams.get("search") || "",
    page: 1,
  });

  const [pagination, setPagination] = useState({ page: 1, page_size: 20, total: 0, total_pages: 1 });

  // Load campaigns for dropdown filter
  useEffect(() => {
    async function loadCampaigns() {
      try {
        const res = await api.get("/campaigns?page_size=100");
        setCampaigns(res.items || []);
      } catch (err) {
        console.error("Failed to load campaigns list", err);
      }
    }
    loadCampaigns();
  }, []);

  const fetchConversations = useCallback(async () => {
    setLoading(true);
    try {
      const q = new URLSearchParams();
      if (filters.campaign_id) q.set("campaign_id", filters.campaign_id);
      if (filters.status) q.set("status", filters.status);
      if (filters.outcome) q.set("outcome", filters.outcome);
      if (filters.search) q.set("search", filters.search);
      q.set("page", filters.page.toString());
      q.set("page_size", "20");

      const [callsRes, sumRes] = await Promise.all([
        api.get(`/outcomes/calls?${q.toString()}`),
        api.get(`/outcomes/summary?${q.toString()}`).catch(() => null),
      ]);

      setCalls(callsRes.items || []);
      setPagination(callsRes.pagination || { page: 1, page_size: 20, total: 0, total_pages: 1 });
      setSummary(sumRes);
    } catch (err) {
      console.error("Failed to load conversations:", err);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const handleFilterChange = (key, val) => {
    setFilters((prev) => ({ ...prev, [key]: val, page: 1 }));
  };

  const handleResetFilters = () => {
    setFilters({ campaign_id: "", status: "", outcome: "", search: "", page: 1 });
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-hairline">
        <div>
          <div className="flex items-center gap-2.5">
            <MessageSquare className="w-5 h-5 text-primary" />
            <h1 className="t-h1 text-ink">Conversations & Transcripts</h1>
          </div>
          <p className="t-body text-muted mt-0.5 text-xs sm:text-sm">
            Search multi-turn Voice AI conversations, chronological dialog transcripts, qualification outcomes, and objections.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchConversations}
            disabled={loading}
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {/* Summary Chips */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Card className="p-3 bg-surface-card">
            <span className="text-[11px] font-semibold text-muted uppercase tracking-wider block">Total Dispatched</span>
            <span className="text-xl font-bold font-mono text-ink mt-0.5 block">{summary.dispatched || 0}</span>
          </Card>
          <Card className="p-3 bg-emerald-50/50 border-emerald-200">
            <span className="text-[11px] font-semibold text-emerald-800 uppercase tracking-wider block">Connected Calls</span>
            <span className="text-xl font-bold font-mono text-emerald-700 mt-0.5 block">{summary.connected || 0}</span>
          </Card>
          <Card className="p-3 bg-indigo-50/50 border-indigo-200">
            <span className="text-[11px] font-semibold text-indigo-800 uppercase tracking-wider block">Interested Leads</span>
            <span className="text-xl font-bold font-mono text-indigo-700 mt-0.5 block">
              {summary.outcome_counts?.interested || 0}
            </span>
          </Card>
          <Card className="p-3 bg-amber-50/50 border-amber-200">
            <span className="text-[11px] font-semibold text-amber-800 uppercase tracking-wider block">Avg Duration</span>
            <span className="text-xl font-bold font-mono text-amber-700 mt-0.5 block">
              {summary.avg_duration_seconds ? `${Math.round(summary.avg_duration_seconds)}s` : "—"}
            </span>
          </Card>
        </div>
      )}

      {/* Search & Filter Bar */}
      <Card className="p-4">
        <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-muted absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Search recipient name or phone..."
              value={filters.search}
              onChange={(e) => handleFilterChange("search", e.target.value)}
              className="input-base pl-9 text-xs !h-9"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
            <select
              value={filters.campaign_id}
              onChange={(e) => handleFilterChange("campaign_id", e.target.value)}
              className="input-base text-xs !h-9 !w-auto"
            >
              <option value="">All Campaigns</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>

            <select
              value={filters.status}
              onChange={(e) => handleFilterChange("status", e.target.value)}
              className="input-base text-xs !h-9 !w-auto"
            >
              <option value="">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="in-progress">In-Progress</option>
              <option value="no-answer">No Answer</option>
              <option value="blocked">Blocked</option>
              <option value="failed">Failed</option>
            </select>

            <select
              value={filters.outcome}
              onChange={(e) => handleFilterChange("outcome", e.target.value)}
              className="input-base text-xs !h-9 !w-auto"
            >
              <option value="">All Outcomes</option>
              <option value="interested">Interested</option>
              <option value="callback">Callback Requested</option>
              <option value="not_interested">Not Interested</option>
            </select>

            {(filters.campaign_id || filters.status || filters.outcome || filters.search) && (
              <Button variant="text" size="sm" onClick={handleResetFilters} className="text-xs">
                Clear
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Conversations Table */}
      <Card className="p-0 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-xs text-muted">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-primary" />
            Loading conversations...
          </div>
        ) : calls.length === 0 ? (
          <div className="p-12 text-center text-xs text-muted space-y-2">
            <MessageSquare className="w-8 h-8 mx-auto text-muted-soft" />
            <div className="font-medium text-ink">No conversations found</div>
            <p className="max-w-md mx-auto text-[11px]">
              No voice interactions matched your current filter criteria.
            </p>
          </div>
        ) : (
          <div className="w-full overflow-hidden">
            <table className="w-full text-left border-collapse table-fixed text-xs">
              <colgroup>
                <col style={{ width: "22%" }} />
                <col style={{ width: "18%" }} />
                <col style={{ width: "12%" }} />
                <col style={{ width: "14%" }} />
                <col style={{ width: "22%" }} />
                <col style={{ width: "12%" }} />
              </colgroup>
              <thead>
                <tr className="border-b border-hairline bg-surface-strong/50 text-muted text-[11px] font-semibold uppercase tracking-wider">
                  <th className="py-2.5 px-3">Recipient & Contact</th>
                  <th className="py-2.5 px-3">Campaign</th>
                  <th className="py-2.5 px-3">Call Status</th>
                  <th className="py-2.5 px-3">Duration & Outcome</th>
                  <th className="py-2.5 px-3">AI Conversation Summary</th>
                  <th className="py-2.5 px-3 text-right">Transcript</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {calls.map((call) => (
                  <tr key={call.id} className="hover:bg-surface-strong/30">
                    <td className="py-2.5 px-3">
                      <span className="font-semibold text-ink block truncate" title={call.recipient_name}>
                        {call.recipient_name || "Lead"}
                      </span>
                      <span className="text-[11px] font-mono text-muted">{call.phone_masked}</span>
                    </td>

                    <td className="py-2.5 px-3 truncate">
                      <span className="text-ink font-medium truncate block" title={call.campaign_name || "Ad-hoc"}>
                        {call.campaign_name || "Ad-hoc Dispatch"}
                      </span>
                      <span className="text-[10px] text-muted font-mono">
                        {call.created_at ? formatDate(call.created_at) : "—"}
                      </span>
                    </td>

                    <td className="py-2.5 px-3">
                      <Badge
                        variant={
                          call.status === "COMPLETED"
                            ? "success"
                            : call.status === "BLOCKED"
                            ? "warning"
                            : call.status === "FAILED"
                            ? "danger"
                            : "default"
                        }
                        className="text-[10px]"
                      >
                        {call.status}
                      </Badge>
                    </td>

                    <td className="py-2.5 px-3">
                      <div className="font-mono text-ink font-semibold">
                        {call.duration_seconds !== null && call.duration_seconds !== undefined
                          ? `${call.duration_seconds}s`
                          : "—"}
                      </div>
                      {call.outcome?.interest_level && (
                        <span
                          className={`inline-block px-1.5 py-0.2 rounded text-[10px] font-semibold mt-0.5 uppercase ${
                            call.outcome.interest_level === "INTERESTED"
                              ? "bg-indigo-100 text-indigo-800"
                              : "bg-surface-strong text-muted"
                          }`}
                        >
                          {call.outcome.interest_level}
                        </span>
                      )}
                    </td>

                    <td className="py-2.5 px-3 truncate">
                      <span
                        className="text-muted text-[11px] italic truncate block max-w-xs"
                        title={call.outcome?.call_summary || call.outcome?.recommended_next_action || "Transcript processed."}
                      >
                        {call.outcome?.call_summary || call.outcome?.recommended_next_action || "Transcript processed."}
                      </span>
                    </td>

                    <td className="py-2.5 px-3 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setSelectedCallId(call.id)}
                        className="!py-0.5 !px-2 text-xs"
                      >
                        View Dialog <ArrowRight className="w-3 h-3 ml-1" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {pagination.total_pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-hairline bg-surface-strong/30 text-xs">
            <span className="text-muted">
              Showing {calls.length} of {pagination.total} records (Page {filters.page} of {pagination.total_pages})
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={filters.page <= 1}
                onClick={() => setFilters((f) => ({ ...f, page: Math.max(1, f.page - 1) }))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={filters.page >= pagination.total_pages}
                onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Embedded Call Detail & Full Transcript Drawer */}
      <CallDetailDrawer callId={selectedCallId} onClose={() => setSelectedCallId(null)} />
    </div>
  );
}

