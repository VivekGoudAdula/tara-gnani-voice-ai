import React, { useState, useEffect, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  RefreshCw,
  Megaphone,
  PhoneCall,
  UserCheck,
  Users,
  ShieldCheck,
  TrendingUp,
  Plus,
  ArrowRight,
  Radio,
  CheckCircle2,
  AlertCircle,
  Clock,
  Activity,
  Layers,
  Sparkles,
  HeartPulse,
} from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Card from "../components/Card";
import Button from "../components/Button";
import Badge from "../components/Badge";
import { formatDate } from "../utils/format";

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [workspaceData, setWorkspaceData] = useState(null);
  const [outcomesData, setOutcomesData] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [providersHealth, setProvidersHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadAllMetrics = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);
    setError("");

    try {
      const [ws, out, camps, health] = await Promise.all([
        api.get("/workspace/dashboard"),
        api.get("/outcomes/summary").catch(() => null),
        api.get("/campaigns?page=1&page_size=5").catch(() => ({ items: [] })),
        api.get("/workspace/providers-health").catch(() => null),
      ]);

      setWorkspaceData(ws);
      setOutcomesData(out);
      setCampaigns(camps?.items || []);
      setProvidersHealth(health);
    } catch (err) {
      console.error("Dashboard metrics fetch error:", err);
      setError(err.message || "Failed to load executive dashboard.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadAllMetrics();
  }, [loadAllMetrics]);

  // Derived metrics with zero-division guards
  const summary = workspaceData?.summary || workspaceData?.summary_cards || {};
  const leadsCount = summary.leads ?? summary.leads_count ?? 0;
  const customersCount = summary.customers ?? summary.customers_count ?? 0;
  const totalAudience = leadsCount + customersCount;

  const dispatched = outcomesData?.dispatched ?? summary.calls?.attempted ?? 0;
  const connected = outcomesData?.connected ?? summary.calls?.completed ?? 0;
  const interested = outcomesData?.outcome_counts?.interested ?? summary.calls?.interested ?? 0;
  const blockedCompliance = outcomesData?.blocked ?? summary.compliance_blocked ?? 0;

  const answerRate = dispatched > 0 ? Math.round((connected / dispatched) * 100) : 0;
  const interestRate = connected > 0 ? Math.round((interested / connected) * 100) : 0;

  const activeCampaigns = campaigns.filter(
    (c) => c.status === "ACTIVE" || c.status === "RUNNING" || c.status === "LAUNCHING"
  );

  return (
    <div className="space-y-6 font-sans">
      {/* Executive Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-hairline">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="t-h1 text-ink flex items-center gap-2">
              <LayoutDashboard className="w-5 h-5 text-ink" />
              Executive Command Center
            </h1>
            <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Voice AI Online
            </span>
          </div>
          <p className="t-body text-muted mt-0.5 text-xs sm:text-sm">
            Targeted customer acquisition, live voice outreach velocity, and pipeline intelligence for {user?.tenant_name || "Workspace"}.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadAllMetrics(true)}
            disabled={refreshing || loading}
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${refreshing ? "animate-spin" : ""}`} />
            <span>Sync Live</span>
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate("/app/campaigns/new")}
          >
            <Plus className="w-3.5 h-3.5 mr-1" />
            <span>New Campaign</span>
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-600 rounded-xl text-xs">
          {error}
        </div>
      )}

      {/* Voice AI Infrastructure Telemetry Pill */}
      <div className="bg-surface-card border border-hairline rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-4 shadow-soft">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary shrink-0" />
          <span className="text-xs font-semibold text-ink">Telephony & AI Pipeline:</span>
          <span className="text-xs text-muted">Twilio Outbound Voice + Gnani Prisma STT + Gnani Timbre TTS</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className={`inline-flex items-center gap-1 font-medium ${providersHealth?.twilio?.configured ? "text-emerald-700" : "text-amber-700"}`}>
            {providersHealth?.twilio?.configured ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
            Twilio {providersHealth?.twilio?.configured ? "Configured" : (providersHealth?.twilio ? "Not Configured" : "Checking")}
          </span>
          <span className="text-hairline">•</span>
          <span className={`inline-flex items-center gap-1 font-medium ${providersHealth?.gnani_prisma?.configured ? "text-emerald-700" : "text-amber-700"}`}>
            {providersHealth?.gnani_prisma?.configured ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
            Prisma STT {providersHealth?.gnani_prisma?.configured ? "Configured" : (providersHealth?.gnani_prisma ? "Not Configured" : "Checking")}
          </span>
          <span className="text-hairline">•</span>
          <span className={`inline-flex items-center gap-1 font-medium ${providersHealth?.gnani_timbre?.configured ? "text-emerald-700" : "text-amber-700"}`}>
            {providersHealth?.gnani_timbre?.configured ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
            Timbre TTS {providersHealth?.gnani_timbre?.configured ? "Configured" : (providersHealth?.gnani_timbre ? "Not Configured" : "Checking")}
          </span>
        </div>
      </div>

      {/* 6 Top-Level KPI Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* 1. Total Audience */}
        <Card className="p-3.5 bg-surface-card flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <span className="text-[11px] font-semibold text-muted uppercase tracking-wider block">Audience</span>
            <Users className="w-4 h-4 text-muted" />
          </div>
          <div className="mt-2">
            <span className="text-2xl font-bold font-mono text-ink block">{totalAudience.toLocaleString()}</span>
            <span className="text-[10px] text-muted-soft block mt-0.5">{leadsCount} leads • {customersCount} portfolio</span>
          </div>
        </Card>

        {/* 2. Active Campaigns */}
        <Card className="p-3.5 bg-surface-card flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <span className="text-[11px] font-semibold text-muted uppercase tracking-wider block">In-Flight</span>
            <Radio className="w-4 h-4 text-sky-600 animate-pulse" />
          </div>
          <div className="mt-2">
            <span className="text-2xl font-bold font-mono text-sky-600 block">{activeCampaigns.length}</span>
            <span className="text-[10px] text-muted-soft block mt-0.5">Active voice campaigns</span>
          </div>
        </Card>

        {/* 3. Calls Dispatched */}
        <Card className="p-3.5 bg-surface-card flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <span className="text-[11px] font-semibold text-muted uppercase tracking-wider block">Dispatched</span>
            <PhoneCall className="w-4 h-4 text-muted" />
          </div>
          <div className="mt-2">
            <span className="text-2xl font-bold font-mono text-ink block">{dispatched.toLocaleString()}</span>
            <span className="text-[10px] text-muted-soft block mt-0.5">Real telephony dials</span>
          </div>
        </Card>

        {/* 4. Answer / Connect Rate */}
        <Card className="p-3.5 bg-surface-card flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <span className="text-[11px] font-semibold text-muted uppercase tracking-wider block">Answer Rate</span>
            <TrendingUp className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-2">
            <span className="text-2xl font-bold font-mono text-emerald-700 block">{answerRate}%</span>
            <span className="text-[10px] text-muted-soft block mt-0.5">{connected} connected sessions</span>
          </div>
        </Card>

        {/* 5. Lead Interest Rate */}
        <Card className="p-3.5 bg-surface-card flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <span className="text-[11px] font-semibold text-muted uppercase tracking-wider block">Interest Rate</span>
            <Sparkles className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="mt-2">
            <span className="text-2xl font-bold font-mono text-indigo-600 block">{interestRate}%</span>
            <span className="text-[10px] text-muted-soft block mt-0.5">{interested} positive responses</span>
          </div>
        </Card>

        {/* 6. Compliance Blocked */}
        <Card className="p-3.5 bg-surface-card flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <span className="text-[11px] font-semibold text-muted uppercase tracking-wider block">Safeguarded</span>
            <ShieldCheck className="w-4 h-4 text-amber-600" />
          </div>
          <div className="mt-2">
            <span className="text-2xl font-bold font-mono text-amber-700 block">{blockedCompliance}</span>
            <span className="text-[10px] text-muted-soft block mt-0.5">DND & duplicate blocks</span>
          </div>
        </Card>
      </div>

      {/* Main Grid: Conversion Funnel + Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Conversion Funnel & Engagement */}
        <Card className="lg:col-span-2 p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-hairline">
            <div>
              <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-muted" /> Real Voice Outreach Conversion Funnel
              </h3>
              <p className="text-xs text-muted mt-0.5">Direct telemetry from Twilio status callbacks and AI session outcomes.</p>
            </div>
            <Link to="/app/analytics" className="text-xs text-primary font-medium hover:underline inline-flex items-center gap-1">
              <span>View Full Analytics</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {/* Funnel Visual Steps */}
          <div className="space-y-3 pt-1">
            {/* Step 1: Dispatched */}
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-medium text-ink">1. Outbound Calls Dispatched</span>
                <span className="font-mono font-bold text-ink">{dispatched} (100%)</span>
              </div>
              <div className="w-full h-2 rounded-full bg-surface-strong overflow-hidden">
                <div className="h-full bg-neutral-700 rounded-full" style={{ width: "100%" }} />
              </div>
            </div>

            {/* Step 2: Connected */}
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-medium text-ink">2. Connected & Greeted by TARA</span>
                <span className="font-mono font-bold text-emerald-700">{connected} ({answerRate}%)</span>
              </div>
              <div className="w-full h-2 rounded-full bg-surface-strong overflow-hidden">
                <div className="h-full bg-emerald-600 rounded-full" style={{ width: `${Math.min(100, answerRate)}%` }} />
              </div>
            </div>

            {/* Step 3: Interested */}
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-medium text-ink">3. Positive Intent & Pitch Acknowledged</span>
                <span className="font-mono font-bold text-indigo-700">{interested} ({connected > 0 ? Math.round((interested / connected) * 100) : 0}% of connected)</span>
              </div>
              <div className="w-full h-2 rounded-full bg-surface-strong overflow-hidden">
                <div className="h-full bg-indigo-600 rounded-full" style={{ width: `${Math.min(100, (connected > 0 ? (interested / connected) * 100 : 0))}%` }} />
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-hairline grid grid-cols-3 gap-2 text-center text-xs">
            <div className="p-2.5 bg-canvas rounded-lg border border-hairline">
              <span className="text-[11px] text-muted block">Avg Call Duration</span>
              <span className="font-mono font-bold text-ink text-sm mt-0.5 block">
                {outcomesData?.avg_duration_seconds ? `${Math.round(outcomesData.avg_duration_seconds)}s` : "—"}
              </span>
            </div>
            <div className="p-2.5 bg-canvas rounded-lg border border-hairline">
              <span className="text-[11px] text-muted block">Primary Language</span>
              <span className="font-mono font-bold text-ink text-sm mt-0.5 block uppercase">
                {Object.keys(outcomesData?.language_breakdown || {})[0] || "Telugu"}
              </span>
            </div>
            <div className="p-2.5 bg-canvas rounded-lg border border-hairline">
              <span className="text-[11px] text-muted block">Failed / Unreachable</span>
              <span className="font-mono font-bold text-rose-700 text-sm mt-0.5 block">
                {outcomesData?.no_answer || outcomesData?.failed || 0}
              </span>
            </div>
          </div>
        </Card>

        {/* Right Col: Quick Actions & Launchpad */}
        <Card className="p-5 space-y-4 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-semibold text-ink flex items-center gap-2 pb-3 border-b border-hairline">
              <Layers className="w-4 h-4 text-muted" /> Quick Operations
            </h3>
            <p className="text-xs text-muted mt-2 mb-4">
              Rapid workflow shortcuts to ingest audience data, calibrate models, and dispatch campaigns.
            </p>

            <div className="space-y-2.5">
              <Link
                to="/app/campaigns/new"
                className="w-full flex items-center justify-between p-3 rounded-xl bg-canvas border border-hairline hover:border-ink hover:bg-white transition-all text-xs text-ink font-medium shadow-xs"
              >
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-primary text-white flex items-center justify-center shrink-0">
                    <Plus className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-semibold block">Create Voice Campaign</span>
                    <span className="text-[11px] text-muted">5-step guided wizard</span>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-muted" />
              </Link>

              <Link
                to="/app/data-import"
                className="w-full flex items-center justify-between p-3 rounded-xl bg-canvas border border-hairline hover:border-ink hover:bg-white transition-all text-xs text-ink font-medium shadow-xs"
              >
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-surface-strong text-ink flex items-center justify-center shrink-0">
                    <Users className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-semibold block">Import Audience CSV</span>
                    <span className="text-[11px] text-muted">Map columns & validate</span>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-muted" />
              </Link>

              <Link
                to="/app/matches"
                className="w-full flex items-center justify-between p-3 rounded-xl bg-canvas border border-hairline hover:border-ink hover:bg-white transition-all text-xs text-ink font-medium shadow-xs"
              >
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-surface-strong text-ink flex items-center justify-center shrink-0">
                    <Sparkles className="w-4 h-4 text-indigo-600" />
                  </div>
                  <div>
                    <span className="font-semibold block">Lead Propensity Scoring</span>
                    <span className="text-[11px] text-muted">Examine high-fit bands</span>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-muted" />
              </Link>

              <Link
                to="/app/live-calls"
                className="w-full flex items-center justify-between p-3 rounded-xl bg-canvas border border-hairline hover:border-ink hover:bg-white transition-all text-xs text-ink font-medium shadow-xs"
              >
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center shrink-0 border border-rose-100">
                    <Radio className="w-4 h-4 animate-pulse" />
                  </div>
                  <div>
                    <span className="font-semibold block">Live Call Monitor</span>
                    <span className="text-[11px] text-muted">Watch in-flight calls</span>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-muted" />
              </Link>
            </div>
          </div>

          <div className="pt-3 border-t border-hairline flex items-center justify-between text-[11px] text-muted">
            <span>Workspace: <strong>{user?.tenant_name || "TARA"}</strong></span>
            <Link to="/app/settings" className="hover:underline">Settings & Policies</Link>
          </div>
        </Card>
      </div>

      {/* Campaigns Snapshot & Recent Audit Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active & Recent Campaigns */}
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-hairline">
            <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
              <Megaphone className="w-4 h-4 text-muted" /> Outreach Campaigns
            </h3>
            <Link to="/app/campaigns" className="text-xs text-primary font-medium hover:underline inline-flex items-center gap-1">
              <span>All Campaigns ({workspaceData?.summary?.campaigns?.total || campaigns.length})</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {campaigns.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted">
              No campaigns created yet. Click "Create Voice Campaign" to get started.
            </div>
          ) : (
            <div className="divide-y divide-hairline">
              {campaigns.map((camp) => {
                const total = camp.total_recipients || 0;
                const contacted = camp.contacted_count || 0;
                const pct = total > 0 ? Math.round((contacted / total) * 100) : 0;

                return (
                  <div key={camp.id} className="py-3 flex items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <Link to={`/app/campaigns/${camp.id}`} className="text-xs font-semibold text-ink hover:underline truncate block">
                        {camp.name}
                      </Link>
                      <span className="text-[11px] text-muted block truncate mt-0.5">
                        {camp.product_name} • {contacted}/{total} dialed ({pct}%)
                      </span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <Badge
                        variant={
                          camp.status === "ACTIVE" || camp.status === "RUNNING"
                            ? "info"
                            : camp.status === "COMPLETED"
                            ? "success"
                            : camp.status === "PAUSED"
                            ? "warning"
                            : "default"
                        }
                        className="text-[10px]"
                      >
                        {camp.status}
                      </Badge>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(`/app/campaigns/${camp.id}`)}
                        className="!py-0.5 !px-2 text-xs"
                      >
                        Inspect
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Recent Platform Activity from Audit Log */}
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-hairline">
            <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
              <Clock className="w-4 h-4 text-muted" /> Real Activity & Audit Trail
            </h3>
            {user?.role === "SUPER_ADMIN" && (
              <Link to="/app/governance" className="text-xs text-primary font-medium hover:underline inline-flex items-center gap-1">
                <span>Security Logs</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            )}
          </div>

          {(!workspaceData?.recent_activity || workspaceData.recent_activity.length === 0) ? (
            <div className="py-8 text-center text-xs text-muted">
              No recent audit activity logged yet.
            </div>
          ) : (
            <div className="space-y-3">
              {workspaceData.recent_activity.slice(0, 5).map((act, idx) => (
                <div key={idx} className="flex items-start justify-between gap-3 text-xs border-b border-hairline/60 pb-2.5 last:border-none last:pb-0">
                  <div className="min-w-0">
                    <span className="font-semibold text-ink block truncate">{act.action}</span>
                    <span className="text-[11px] text-muted block truncate mt-0.5">
                      by {act.actor || "System"} • {act.entity_type || "Resource"}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-muted shrink-0">
                    {formatDate(act.timestamp)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
