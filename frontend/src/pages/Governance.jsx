import React, { useState, useEffect, useCallback } from "react";
import { ShieldCheck, Filter, AlertTriangle, RefreshCw, Calendar, User, Clock } from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Badge from "../components/Badge";
import Button from "../components/Button";

export default function Governance() {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "SUPER_ADMIN";

  const [logs, setLogs] = useState([]);
  const [controls, setControls] = useState(null);
  const [pagination, setPagination] = useState({ page: 1, page_size: 20, total: 0, total_pages: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [actionFilter, setActionFilter] = useState("");
  const [entityTypeFilter, setEntityTypeFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");

  const fetchAuditLogs = useCallback(async (page = 1) => {
    if (!isSuperAdmin) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");

    const params = new URLSearchParams({ page, page_size: pagination.page_size });
    if (actionFilter) params.append("action", actionFilter);
    if (entityTypeFilter) params.append("entity_type", entityTypeFilter);
    if (actorFilter.trim()) params.append("actor", actorFilter.trim());

    try {
      const res = await api.get(`/audit?${params.toString()}`);
      setLogs(res.items || []);
      setPagination(res.pagination || { page: 1, page_size: 20, total: 0, total_pages: 0 });
      if (res.compliance_controls) setControls(res.compliance_controls);
    } catch (err) {
      console.error("Audit log error:", err);
      setError(err.message || "Failed to load audit trail.");
    } finally {
      setLoading(false);
    }
  }, [isSuperAdmin, actionFilter, entityTypeFilter, actorFilter, pagination.page_size]);

  useEffect(() => {
    fetchAuditLogs(1);
  }, [fetchAuditLogs]);

  if (!isSuperAdmin) {
    return (
      <div className="p-8 bg-surface-card rounded-2xl border border-hairline text-center space-y-3 font-sans">
        <ShieldCheck className="w-10 h-10 text-muted mx-auto" />
        <h2 className="t-h2 text-ink">Access Restricted</h2>
        <p className="t-caption text-muted max-w-md mx-auto">
          Governance & Audit logs contain immutable security records and are restricted to Super Administrators.
        </p>
      </div>
    );
  }

  const getActionBadge = (action = "") => {
    const act = action.toLowerCase();
    if (act.includes("import") || act.includes("sample")) return <Badge variant="info">{action}</Badge>;
    if (act.includes("score")) return <Badge variant="purple">{action}</Badge>;
    if (act.includes("send") || act.includes("launch")) return <Badge variant="success">{action}</Badge>;
    if (act.includes("block") || act.includes("fail")) return <Badge variant="danger">{action}</Badge>;
    return <Badge variant="default">{action}</Badge>;
  };

  const formatDetails = (details = {}) => {
    const d = details.detail || details.details || details;
    if (d.file_name) return `File: "${d.file_name}" (${d.imported_count || 0} imported)`;
    if (d.name) return `Product: "${d.name}"`;
    if (d.total_scored !== undefined) return `Scored ${d.total_scored} profiles against active catalog`;
    if (d.campaign_name) return `Campaign: "${d.campaign_name}" (${d.recipient_count || 0} recipients)`;
    if (d.reason) return `Reason: ${d.reason}`;
    if (d.phone) return `Recipient: ${d.phone} (${d.status || ""})`;
    if (d.channel) return `Channel: ${d.channel}`;
    return Object.keys(d).length > 0 ? JSON.stringify(d).slice(0, 80) : "—";
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-hairline">
        <div>
          <h1 className="t-h1 text-ink flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-muted" />
            Governance & Audit Logs
          </h1>
          <p className="t-body text-muted mt-1">
            Read-only immutable activity trail. Tracks scoring, campaign events, dispatch controls, imports, and catalog updates.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => fetchAuditLogs(1)} disabled={loading}>
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh Audit Trail</span>
        </Button>
      </div>

      {/* Compliance Controls Card */}
      {controls && (
        <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-hairline">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <h2 className="t-body-strong text-ink">Active Policy Controls Enforced at Dispatch</h2>
            </div>
            <span className="text-[11px] font-mono text-muted-soft">
              Source: Real Environment Configuration
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 pt-1">
            <div className="p-3 bg-canvas rounded-xl border border-hairline">
              <span className="text-muted text-[11px] block mb-1">TEST_MODE</span>
              <span className={`font-semibold text-xs ${controls.test_mode ? "text-amber-700" : "text-emerald-700"}`}>
                {controls.test_mode ? "Enabled (Allowlist Only)" : "Disabled (Live Dispatch)"}
              </span>
            </div>

            <div className="p-3 bg-canvas rounded-xl border border-hairline">
              <span className="text-muted text-[11px] block mb-1">Calling Window</span>
              <span className="font-semibold text-xs text-ink">{controls.calling_window}</span>
            </div>

            <div className="p-3 bg-canvas rounded-xl border border-hairline">
              <span className="text-muted text-[11px] block mb-1">Contact Cap</span>
              <span className="font-semibold text-xs text-ink">{controls.contact_cap}</span>
            </div>

            <div className="p-3 bg-canvas rounded-xl border border-hairline">
              <span className="text-muted text-[11px] block mb-1">DPDP Consent</span>
              <span className="font-semibold text-xs text-emerald-700">Strictly Enforced</span>
            </div>

            <div className="p-3 bg-canvas rounded-xl border border-hairline">
              <span className="text-muted text-[11px] block mb-1">DND Flag Check</span>
              <span className="font-semibold text-xs text-rose-700">Blocked at Dispatch</span>
            </div>
          </div>
        </div>
      )}

      {/* Filters Bar */}
      <div className="bg-surface-card p-4 rounded-2xl border border-hairline shadow-soft flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-muted shrink-0" />
          <span className="text-xs font-semibold text-ink">Filters:</span>
        </div>

        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="bg-canvas border border-hairline rounded-lg px-2.5 py-1 text-xs text-ink"
        >
          <option value="">All Actions</option>
          <option value="data_import_confirmed">data_import_confirmed</option>
          <option value="sample_data_loaded">sample_data_loaded</option>
          <option value="scoring_run_completed">scoring_run_completed</option>
          <option value="campaign_launched">campaign_launched</option>
          <option value="campaign_created">campaign_created</option>
          <option value="product_created">product_created</option>
          <option value="product_updated">product_updated</option>
          <option value="product_activated">product_activated</option>
          <option value="product_deactivated">product_deactivated</option>
          <option value="scoring_settings_updated">scoring_settings_updated</option>
        </select>

        <select
          value={entityTypeFilter}
          onChange={(e) => setEntityTypeFilter(e.target.value)}
          className="bg-canvas border border-hairline rounded-lg px-2.5 py-1 text-xs text-ink"
        >
          <option value="">All Entity Types</option>
          <option value="lead">Lead</option>
          <option value="customer">Customer</option>
          <option value="product">Product</option>
          <option value="campaign">Campaign</option>
          <option value="scoring">Scoring</option>
          <option value="data_import">Data Import</option>
          <option value="workspace">Workspace</option>
        </select>

        <input
          type="text"
          placeholder="Filter by actor name..."
          value={actorFilter}
          onChange={(e) => setActorFilter(e.target.value)}
          className="bg-canvas border border-hairline rounded-lg px-2.5 py-1 text-xs text-ink w-44"
        />

        {(actionFilter || entityTypeFilter || actorFilter) && (
          <button
            onClick={() => { setActionFilter(""); setEntityTypeFilter(""); setActorFilter(""); }}
            className="text-xs text-muted hover:text-ink underline ml-auto"
          >
            Clear filters
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-600 rounded-xl t-caption">{error}</div>
      )}

      {/* Audit Logs Table */}
      <div className="bg-surface-card rounded-2xl border border-hairline overflow-hidden shadow-soft">
        <div className="w-full overflow-hidden">
          <table className="w-full text-left text-xs table-fixed border-collapse">
            <colgroup>
              <col style={{ width: "18%" }} />
              <col style={{ width: "20%" }} />
              <col style={{ width: "16%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "32%" }} />
            </colgroup>
            <thead className="bg-canvas border-b border-hairline text-muted text-[11px] font-semibold uppercase tracking-wider">
              <tr>
                <th className="py-2 px-2.5">Timestamp</th>
                <th className="py-2 px-2.5">Actor</th>
                <th className="py-2 px-2.5">Action</th>
                <th className="py-2 px-2.5">Entity</th>
                <th className="py-2 px-2.5">Detail Summary</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-muted">
                    Loading audit trail...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-muted">
                    No audit records match the current filters.
                  </td>
                </tr>
              ) : (
                logs.map((item) => {
                  const rawTime = item.at || item.created_at;
                  const timeStr = rawTime
                    ? new Date(rawTime).toLocaleString([], {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })
                    : "—";

                  return (
                    <tr key={item.id} className="hover:bg-canvas/50 transition-colors">
                      <td className="py-2 px-2.5 font-mono text-[11px] text-muted truncate">
                        {timeStr}
                      </td>
                      <td className="py-2 px-2.5 truncate">
                        <div className="font-semibold text-ink text-xs truncate">{item.actor_name || "System"}</div>
                        <div className="text-[10px] text-muted-soft truncate">{item.actor_email}</div>
                      </td>
                      <td className="py-2 px-2.5 truncate">{getActionBadge(item.action)}</td>
                      <td className="py-2 px-2.5 font-mono text-[11px] truncate">
                        <span className="uppercase text-muted-soft">{item.entity_type || "—"}</span>
                      </td>
                      <td className="py-2 px-2.5 text-muted truncate" title={JSON.stringify(item.details)}>
                        {formatDetails(item.details)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pagination.total_pages > 1 && (
          <div className="p-3.5 bg-canvas border-t border-hairline flex items-center justify-between text-xs">
            <span className="text-muted">
              Page {pagination.page} of {pagination.total_pages} ({pagination.total} audit events)
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={pagination.page <= 1}
                onClick={() => fetchAuditLogs(pagination.page - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={pagination.page >= pagination.total_pages}
                onClick={() => fetchAuditLogs(pagination.page + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
