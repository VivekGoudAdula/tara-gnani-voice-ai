import React, { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { ArrowLeft, Pause, Play, Ban, RotateCcw, Edit, RefreshCw, ShieldAlert, PhoneCall, ExternalLink, BarChart3, CheckCircle2, Clock, AlertCircle, RefreshCwOff } from "lucide-react";
import Card from "../components/Card";
import Button from "../components/Button";
import Badge from "../components/Badge";
import CallDetailDrawer from "../components/outcomes/CallDetailDrawer";
import { api } from "../api/client";
import { formatDate } from "../utils/format";

export default function CampaignDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [campaign, setCampaign] = useState(null);
  const [progress, setProgress] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [retries, setRetries] = useState(null);
  const [validationReport, setValidationReport] = useState(null);
  const [recipients, setRecipients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({ total: 0, total_pages: 1 });
  const [actionLoading, setActionLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("recipients");
  const [inspectedCallId, setInspectedCallId] = useState(null);

  const loadData = async () => {
    try {
      const camp = await api.get(`/campaigns/${id}`);
      setCampaign(camp);

      const prog = await api.get(`/campaigns/${id}/progress`);
      setProgress(prog);

      try {
        const ana = await api.get(`/campaigns/${id}/analytics`);
        setAnalytics(ana);
      } catch (e) {
        // Analytics optional fallback
      }

      try {
        const ret = await api.get(`/campaigns/${id}/retries`);
        setRetries(ret);
      } catch (e) {
        // Retries optional fallback
      }

      let q = `/campaigns/${id}/recipients?page=${page}&page_size=50`;
      if (statusFilter) q += `&status=${statusFilter}`;
      const rec = await api.get(q);
      setRecipients(rec.items || []);
      setPagination(rec.pagination || { total: 0, total_pages: 1 });
    } catch (err) {
      console.error("Failed to load campaign data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id, page, statusFilter]);

  // Polling every 10s when active, running, or launching, pausing when document is hidden
  useEffect(() => {
    if (!campaign || !["ACTIVE", "LAUNCHING", "RUNNING"].includes(campaign.status)) return;

    const timer = setInterval(() => {
      if (document.visibilityState === "visible") loadData();
    }, 10000);

    return () => clearInterval(timer);
  }, [campaign?.status, page, statusFilter]);

  const handleAction = async (endpoint, method = "post") => {
    setActionLoading(true);
    try {
      await api[method](`/campaigns/${id}/${endpoint}`);
      await loadData();
    } catch (err) {
      alert(err.message || `Failed to execute ${endpoint}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleValidate = async () => {
    setActionLoading(true);
    try {
      const rep = await api.post(`/campaigns/${id}/validate`);
      setValidationReport(rep);
    } catch (err) {
      alert(err.message || "Failed to validate campaign readiness");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading || !campaign) {
    return <div className="p-12 text-center text-muted t-body-sm">Loading campaign details...</div>;
  }

  const counts = progress?.counts_by_status || {};
  const total = progress?.total_recipients || 0;
  const contacted = (counts.CONTACTED || 0) + (counts.INTERESTED || 0) + (counts.CALLBACK || 0) + (counts.NOT_INTERESTED || 0);

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-hairline">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => navigate("/app/campaigns")}>
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Campaigns
          </Button>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="t-heading-sm text-ink">{campaign.name}</h1>
              <Badge variant={campaign.status === "ACTIVE" || campaign.status === "LAUNCHING" || campaign.status === "RUNNING" ? "info" : campaign.status === "COMPLETED" ? "success" : campaign.status === "SCHEDULED" ? "purple" : "default"}>
                {campaign.status}
              </Badge>
              <span className="t-body-xs font-mono text-muted bg-surface-strong px-2 py-0.5 rounded">
                v{campaign.config_version}
              </span>
              {campaign.test_run_label && (
                <span className="t-body-xs font-mono text-primary bg-primary/10 px-2 py-0.5 rounded">
                  tag: {campaign.test_run_label}
                </span>
              )}
              {campaign.scheduled_start_time && (
                <span className="t-body-xs font-mono text-purple-700 bg-purple-50 border border-purple-200 px-2 py-0.5 rounded flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Scheduled: {formatDate(campaign.scheduled_start_time)}
                </span>
              )}
            </div>
            <p className="t-body-xs text-muted mt-0.5">
              {campaign.product_name} • {campaign.entity_type}s • Updated {formatDate(campaign.updated_at)}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {["ACTIVE", "LAUNCHING", "RUNNING"].includes(campaign.status) && (
            <Button variant="outline" size="sm" onClick={() => handleAction("pause")} disabled={actionLoading}>
              <Pause className="w-3.5 h-3.5 mr-1" /> Pause
            </Button>
          )}
          {campaign.status === "PAUSED" && (
            <Button variant="primary" size="sm" onClick={() => handleAction("resume")} disabled={actionLoading}>
              <Play className="w-3.5 h-3.5 mr-1" /> Resume
            </Button>
          )}
          {["DRAFT", "READY"].includes(campaign.status) && (
            <Button variant="outline" size="sm" onClick={() => navigate(`/app/campaigns/${id}/edit`)}>
              <Edit className="w-3.5 h-3.5 mr-1" /> Edit Wizard
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={handleValidate} disabled={actionLoading} title="Validate pre-flight readiness">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-600" /> Validate
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleAction("retry")} disabled={actionLoading} title="Retry failed or unanswered recipients">
            <RotateCcw className="w-3.5 h-3.5 mr-1" /> Retry Failed
          </Button>
          <Link to={`/app/outcomes?campaign_id=${id}`}>
            <Button variant="outline" size="sm">
              <BarChart3 className="w-3.5 h-3.5 mr-1 text-primary" /> Outcomes & Evidence
            </Button>
          </Link>
          {!["COMPLETED", "CANCELLED"].includes(campaign.status) && (
            <Button variant="text" size="sm" onClick={() => handleAction("cancel")} disabled={actionLoading} className="text-semantic-error">
              <Ban className="w-3.5 h-3.5 mr-1" /> Cancel
            </Button>
          )}
        </div>
      </div>

      {/* Pre-flight Validation Report Banner (if generated) */}
      {validationReport && (
        <Card className={`p-4 border ${validationReport.is_valid ? "bg-emerald-50/50 border-emerald-200" : "bg-rose-50/50 border-rose-200"}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {validationReport.is_valid ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              ) : (
                <AlertCircle className="w-5 h-5 text-rose-600" />
              )}
              <div>
                <h4 className="text-sm font-semibold text-ink">
                  {validationReport.is_valid ? "Campaign Ready for Outreach" : "Campaign Readiness Issues Detected"}
                </h4>
                <p className="text-xs text-muted">
                  {validationReport.total_recipients} total recipients ({validationReport.eligible_recipients} dialable, {validationReport.blocked_estimate} blocked)
                </p>
              </div>
            </div>
            <Button variant="text" size="xs" onClick={() => setValidationReport(null)}>Dismiss</Button>
          </div>
          {validationReport.errors?.length > 0 && (
            <div className="mt-2 text-xs text-rose-700 space-y-1">
              {validationReport.errors.map((err, idx) => (
                <div key={idx}>• {err}</div>
              ))}
            </div>
          )}
          {validationReport.warnings?.length > 0 && (
            <div className="mt-2 text-xs text-amber-700 space-y-1">
              {validationReport.warnings.map((w, idx) => (
                <div key={idx}>⚠ {w}</div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Derived Conversion Ratios & Intelligence Banner */}
      {analytics?.derived_metrics && analytics.calls_dispatched > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Card className="p-3 bg-indigo-50/40 border-indigo-100">
            <span className="t-label text-indigo-900 text-[11px] block">Contact Rate</span>
            <span className="text-xl font-bold font-mono text-indigo-700">
              {Math.round((analytics.derived_metrics.contact_rate || 0) * 100)}%
            </span>
          </Card>
          <Card className="p-3 bg-emerald-50/40 border-emerald-100">
            <span className="t-label text-emerald-900 text-[11px] block">Answer / Connect Rate</span>
            <span className="text-xl font-bold font-mono text-emerald-700">
              {Math.round((analytics.derived_metrics.answer_rate || 0) * 100)}%
            </span>
          </Card>
          <Card className="p-3 bg-sky-50/40 border-sky-100">
            <span className="t-label text-sky-900 text-[11px] block">Lead Qualification Rate</span>
            <span className="text-xl font-bold font-mono text-sky-700">
              {Math.round((analytics.derived_metrics.qualification_rate || 0) * 100)}%
            </span>
          </Card>
          <Card className="p-3 bg-amber-50/40 border-amber-100">
            <span className="t-label text-amber-900 text-[11px] block">Avg Call Duration</span>
            <span className="text-xl font-bold font-mono text-amber-700">
              {analytics.duration_stats?.avg_seconds || 0}s
            </span>
          </Card>
        </div>
      )}


      {/* Progress Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: "Total Audience", count: total, color: "text-ink" },
          { label: "Calling / In-Flight", count: counts.CALLING || 0, color: "text-sky-600" },
          { label: "Contacted", count: contacted, color: "text-emerald-700 font-bold" },
          { label: "Interested", count: counts.INTERESTED || 0, color: "text-emerald-600" },
          { label: "No Answer / Busy", count: counts.NO_ANSWER || 0, color: "text-amber-600" },
          { label: "Blocked Compliance", count: counts.BLOCKED || 0, color: "text-semantic-error font-medium" },
        ].map((m, i) => (
          <Card key={i} className="p-3 bg-surface-card">
            <span className="t-label text-muted text-[11px] truncate block">{m.label}</span>
            <span className={`text-2xl font-bold font-mono mt-0.5 block ${m.color}`}>{m.count}</span>
          </Card>
        ))}
      </div>

      {/* Blocked Reasons Breakdown Card (if any blocked) */}
      {Object.keys(progress?.blocked_reasons_breakdown || {}).length > 0 && (
        <Card className="p-4 bg-amber-50/50 border-amber-200">
          <div className="flex items-center gap-2 mb-2 t-label text-amber-900 font-semibold">
            <ShieldAlert className="w-4 h-4 text-amber-600" />
            Compliance Gate Breakdown (Calls Safeguarded)
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(progress.blocked_reasons_breakdown).map(([reason, count]) => (
              <span key={reason} className="px-2.5 py-1 rounded-full text-xs font-mono bg-white border border-amber-200 text-amber-950 shadow-xs">
                {reason}: <strong>{count}</strong>
              </span>
            ))}
          </div>
        </Card>
      )}

      {/* Main Tab Controls: Recipients vs. Retry Queue */}
      <div className="flex items-center gap-2 border-b border-hairline pb-2">
        <button
          onClick={() => setActiveTab("recipients")}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeTab === "recipients"
              ? "bg-surface-card border border-hairline text-ink shadow-xs"
              : "text-muted hover:text-ink hover:bg-white/50"
          }`}
        >
          <span className="flex items-center gap-2">
            <PhoneCall className="w-3.5 h-3.5" />
            <span>Audience Recipients ({total})</span>
          </span>
        </button>

        <button
          onClick={() => setActiveTab("retries")}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeTab === "retries"
              ? "bg-surface-card border border-hairline text-ink shadow-xs"
              : "text-muted hover:text-ink hover:bg-white/50"
          }`}
        >
          <span className="flex items-center gap-2">
            <RotateCcw className="w-3.5 h-3.5 text-amber-600" />
            <span>Retry Queue & Recovery ({retries?.total_in_queue || 0})</span>
          </span>
        </button>
      </div>

      {/* 1. Recipients Table Tab */}
      {activeTab === "recipients" && (
        <Card className="p-0 overflow-hidden">
          <div className="p-4 border-b border-hairline flex flex-wrap items-center justify-between gap-4">
            <h3 className="t-heading-sm text-ink flex items-center gap-2">
              <PhoneCall className="w-4 h-4 text-muted" /> Campaign Recipients ({total})
            </h3>
            <div className="flex items-center gap-2">
              <span className="t-label text-xs text-muted">Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                className="input-base text-xs py-1 px-2.5 h-8"
              >
                <option value="">All Statuses</option>
                {["PENDING", "CALLING", "CONTACTED", "INTERESTED", "CALLBACK", "NOT_INTERESTED", "NO_ANSWER", "BLOCKED", "FAILED"].map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="w-full overflow-hidden">
            <table className="w-full text-left border-collapse table-fixed">
              <colgroup>
                <col style={{ width: "18%" }} />
                <col style={{ width: "14%" }} />
                <col style={{ width: "13%" }} />
                <col style={{ width: "15%" }} />
                <col style={{ width: "16%" }} />
                <col style={{ width: "7%" }} />
                <col style={{ width: "10%" }} />
                <col style={{ width: "7%" }} />
              </colgroup>
              <thead>
                <tr className="border-b border-hairline bg-surface-strong/50 text-muted text-[11px] font-semibold uppercase tracking-wider">
                  <th className="py-2 px-2.5">Recipient Name</th>
                  <th className="py-2 px-2.5">Snapshot Fit</th>
                  <th className="py-2 px-2.5">Policy Eligibility</th>
                  <th className="py-2 px-2.5">Outreach Status</th>
                  <th className="py-2 px-2.5">Tester Scenario</th>
                  <th className="py-2 px-2.5">Attempts</th>
                  <th className="py-2 px-2.5">Last Contact</th>
                  <th className="py-2 px-2.5 text-right">Call Record</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {recipients.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-muted text-xs">
                      No recipients found matching current status filter.
                    </td>
                  </tr>
                ) : (
                  recipients.map((r) => (
                    <tr key={r.id} className="hover:bg-surface-strong/30">
                      <td className="py-2 px-2.5 font-semibold text-ink text-xs truncate" title={r.name}>{r.name}</td>
                      <td className="py-2 px-2.5">
                        <Badge variant={r.band === "HIGH" ? "success" : r.band === "MEDIUM" ? "info" : "warning"} className="text-[10px] px-1.5 py-0.5">
                          {r.band} ({Math.round(r.match_score)}%)
                        </Badge>
                      </td>
                      <td className="py-2 px-2.5">
                        <Badge variant={r.eligibility === "ELIGIBLE" ? "success" : "danger"} className="text-[10px] px-1.5 py-0.5">{r.eligibility}</Badge>
                      </td>
                      <td className="py-2 px-2.5">
                        <Badge variant={r.status === "INTERESTED" ? "success" : r.status === "BLOCKED" ? "warning" : r.status === "CALLING" ? "info" : "default"} className="text-[10px] px-1.5 py-0.5">
                          {r.status}
                        </Badge>
                        {r.blocked_reason && <span className="block text-[10px] font-mono text-muted mt-0.5 truncate" title={r.blocked_reason}>{r.blocked_reason}</span>}
                      </td>
                      <td className="py-2 px-2.5 text-xs truncate">
                        {["DRAFT", "READY"].includes(campaign.status) ? (
                          <input
                            type="text"
                            defaultValue={r.tester_scenario || ""}
                            placeholder="e.g. interested+amount"
                            onBlur={async (e) => {
                              const val = e.target.value.trim();
                              if (val !== (r.tester_scenario || "")) {
                                try {
                                  await api.patch(`/campaigns/${id}/recipients/${r.entity_id}/scenario`, { tester_scenario: val || null });
                                } catch (err) {
                                  console.error("Failed to update scenario", err);
                                }
                              }
                            }}
                            className="input-base text-[11px] py-1 px-1.5 h-6 w-full max-w-[130px] font-mono"
                          />
                        ) : (
                          <span className="font-mono text-muted text-[10px] truncate block">{r.tester_scenario || "—"}</span>
                        )}
                      </td>
                      <td className="py-2 px-2.5 text-xs font-mono text-muted">{r.attempts}</td>
                      <td className="py-2 px-2.5 text-[11px] text-muted truncate">{r.last_contact_at ? formatDate(r.last_contact_at) : "—"}</td>
                      <td className="py-2 px-2.5 text-right">
                        {r.last_communication_id ? (
                          <button
                            type="button"
                            onClick={() => setInspectedCallId(r.last_communication_id)}
                            className="text-[11px] font-mono text-primary hover:underline inline-flex items-center gap-1 cursor-pointer"
                            title="Inspect Voice Session & Transcript"
                          >
                            <span>#{r.last_communication_id.slice(-6)}</span>
                            <ExternalLink className="w-3 h-3" />
                          </button>
                        ) : (
                          <span className="text-muted-soft text-xs">—</span>
                        )}
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
                Showing {recipients.length} of {pagination.total} recipients (Page {page} of {pagination.total_pages})
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= pagination.total_pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* 2. Retry Queue & Recovery Tab */}
      {activeTab === "retries" && (
        <Card className="p-0 overflow-hidden">
          <div className="p-4 border-b border-hairline flex flex-wrap items-center justify-between gap-4">
            <div>
              <h3 className="t-heading-sm text-ink flex items-center gap-2">
                <RotateCcw className="w-4 h-4 text-amber-600" />
                Automatic Retry Queue ({retries?.total_in_queue || 0})
              </h3>
              <p className="text-xs text-muted mt-0.5">
                Configured max attempts: <strong>{retries?.max_attempts_configured || 2}</strong>. Retries are checked periodically by background recovery.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleAction("retry")}
              disabled={actionLoading}
            >
              <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
              <span>Dispatch Due Retries Now</span>
            </Button>
          </div>

          {(!retries?.items || retries.items.length === 0) ? (
            <div className="py-12 text-center text-xs text-muted">
              No recipients currently pending in the retry queue for this campaign.
            </div>
          ) : (
            <div className="w-full overflow-hidden">
              <table className="w-full text-left border-collapse table-fixed">
                <colgroup>
                  <col style={{ width: "24%" }} />
                  <col style={{ width: "16%" }} />
                  <col style={{ width: "12%" }} />
                  <col style={{ width: "20%" }} />
                  <col style={{ width: "18%" }} />
                  <col style={{ width: "10%" }} />
                </colgroup>
                <thead>
                  <tr className="border-b border-hairline bg-surface-strong/50 text-muted text-[11px] font-semibold uppercase tracking-wider">
                    <th className="py-2.5 px-3">Recipient Name</th>
                    <th className="py-2.5 px-3">Masked Phone</th>
                    <th className="py-2.5 px-3">Attempts</th>
                    <th className="py-2.5 px-3">Next Retry Window</th>
                    <th className="py-2.5 px-3">Failure Reason</th>
                    <th className="py-2.5 px-3 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline text-xs">
                  {retries.items.map((item) => (
                    <tr key={item.recipient_id} className="hover:bg-surface-strong/30">
                      <td className="py-2.5 px-3 font-semibold text-ink truncate" title={item.name}>{item.name}</td>
                      <td className="py-2.5 px-3 font-mono text-muted">{item.phone_masked}</td>
                      <td className="py-2.5 px-3 font-mono">
                        {item.attempts} / {item.max_attempts}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-muted">
                        {item.next_retry_at ? formatDate(item.next_retry_at) : "Scheduled on run"}
                      </td>
                      <td className="py-2.5 px-3 text-muted truncate" title={item.failure_reason || ""}>
                        {item.failure_reason || "No Answer / Unreached"}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Badge variant={item.eligible_for_retry ? "warning" : "default"} className="text-[10px]">
                          {item.eligible_for_retry ? "QUEUED" : "EXHAUSTED"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* Embedded Call Detail & Transcript Drawer */}
      <CallDetailDrawer callId={inspectedCallId} onClose={() => setInspectedCallId(null)} />
    </div>
  );
}
