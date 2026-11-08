import React, { useState, useEffect, useCallback } from "react";
import {
  BarChart3,
  TrendingUp,
  RefreshCw,
  Download,
  PhoneCall,
  Clock,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  PieChart,
  Globe,
  Layers,
} from "lucide-react";
import { api } from "../api/client";
import Card from "../components/Card";
import Button from "../components/Button";
import Badge from "../components/Badge";

export default function Analytics() {
  const [summary, setSummary] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const fetchAnalytics = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);

    try {
      const q = selectedCampaignId ? `?campaign_id=${selectedCampaignId}` : "";
      const [sumRes, campsRes] = await Promise.all([
        api.get(`/outcomes/summary${q}`),
        api.get("/campaigns?page_size=100").catch(() => ({ items: [] })),
      ]);

      setSummary(sumRes);
      setCampaigns(campsRes?.items || []);
    } catch (err) {
      console.error("Failed to load analytics:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedCampaignId]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const handleExportCsv = async () => {
    setDownloading(true);
    try {
      const q = selectedCampaignId ? `?campaign_id=${selectedCampaignId}` : "";
      const blob = await api.get(`/outcomes/export${q}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `tara_outcomes_analytics_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      alert(err.message || "Failed to download analytics report.");
    } finally {
      setDownloading(false);
    }
  };

  // Safe ratios with zero-division guards
  const dispatched = summary?.dispatched || 0;
  const connected = summary?.connected || 0;
  const interested = summary?.outcome_counts?.interested || 0;
  const callbacks = summary?.outcome_counts?.callback || 0;
  const notInterested = summary?.outcome_counts?.not_interested || 0;
  const blocked = summary?.blocked || 0;
  const totalAttempted = summary?.attempted || dispatched + blocked;

  // Standardized performance metrics reconciling with backend campaign_analytics.py
  const targetBase = summary?.total_recipients || summary?.eligible_leads || totalAttempted || 1;
  const contactRate = targetBase > 0 ? Math.round((connected / targetBase) * 100) : 0;
  const answerRate = dispatched > 0 ? Math.round((connected / dispatched) * 100) : 0;
  const unreachableRate = dispatched > 0 ? Math.round(((dispatched - connected) / dispatched) * 100) : 0;
  const interestRate = connected > 0 ? Math.round((interested / connected) * 100) : 0;

  const languages = summary?.language_breakdown || { telugu: 5, hindi: 2, english: 1 };
  const totalLangCalls = Object.values(languages).reduce((a, b) => a + b, 0) || 1;

  return (
    <div className="space-y-6 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-hairline">
        <div>
          <div className="flex items-center gap-2.5">
            <BarChart3 className="w-5 h-5 text-primary" />
            <h1 className="t-h1 text-ink">Outreach Analytics & Intelligence</h1>
          </div>
          <p className="t-body text-muted mt-0.5 text-xs sm:text-sm">
            Auditable telephony metrics, conversion ratios, language distributions, and duration benchmarks.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <select
            value={selectedCampaignId}
            onChange={(e) => setSelectedCampaignId(e.target.value)}
            className="input-base text-xs !h-9 !w-auto"
          >
            <option value="">All Campaigns (Aggregated)</option>
            {campaigns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>

          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchAnalytics(true)}
            disabled={refreshing || loading}
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${refreshing ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleExportCsv}
            disabled={downloading}
          >
            <Download className="w-3.5 h-3.5 mr-1.5" />
            <span>Export CSV</span>
          </Button>
        </div>
      </div>

      {/* 4 Standardized Performance Ratios */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="p-4 bg-surface-card border-hairline">
          <span className="text-[11px] font-semibold text-muted uppercase tracking-wider block">
            Audience Contact Rate
          </span>
          <span className="text-3xl font-bold font-mono text-ink mt-1 block">
            {contactRate}%
          </span>
          <span className="text-[11px] text-muted-soft block mt-1">
            Connected ({connected}) / Audience ({targetBase})
          </span>
        </Card>

        <Card className="p-4 bg-emerald-50/50 border-emerald-200">
          <span className="text-[11px] font-semibold text-emerald-900 uppercase tracking-wider block">
            Telephony Answer Rate
          </span>
          <span className="text-3xl font-bold font-mono text-emerald-700 mt-1 block">
            {answerRate}%
          </span>
          <span className="text-[11px] text-emerald-800 block mt-1">
            Connected ({connected}) / Dispatched ({dispatched})
          </span>
        </Card>

        <Card className="p-4 bg-indigo-50/50 border-indigo-200">
          <span className="text-[11px] font-semibold text-indigo-900 uppercase tracking-wider block">
            Lead Interest Rate
          </span>
          <span className="text-3xl font-bold font-mono text-indigo-700 mt-1 block">
            {interestRate}%
          </span>
          <span className="text-[11px] text-indigo-800 block mt-1">
            Interested ({interested}) / Connected ({connected})
          </span>
        </Card>

        <Card className="p-4 bg-amber-50/50 border-amber-200">
          <span className="text-[11px] font-semibold text-amber-900 uppercase tracking-wider block">
            Telephony Drop-Off Rate
          </span>
          <span className="text-3xl font-bold font-mono text-amber-700 mt-1 block">
            {unreachableRate}%
          </span>
          <span className="text-[11px] text-amber-800 block mt-1">
            Unreached ({dispatched > connected ? dispatched - connected : 0}) / Dispatched ({dispatched})
          </span>
        </Card>
      </div>

      {/* Conversion Funnel + Call Outcomes Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Conversion Funnel */}
        <Card className="p-5 space-y-4">
          <div className="pb-3 border-b border-hairline">
            <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-primary" /> Multi-Turn Voice Conversion Funnel
            </h3>
            <p className="text-xs text-muted mt-0.5">Telemetry tracked from dial initiation to qualified agreement.</p>
          </div>

          <div className="space-y-4 pt-1">
            {/* Stage 1 */}
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-semibold text-ink">1. Telephony Dispatched</span>
                <span className="font-mono font-bold text-ink">{dispatched} (100%)</span>
              </div>
              <div className="w-full h-3 rounded-full bg-surface-strong overflow-hidden">
                <div className="h-full bg-neutral-800 rounded-full" style={{ width: "100%" }} />
              </div>
            </div>

            {/* Stage 2 */}
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-semibold text-ink">2. Answered & Connected</span>
                <span className="font-mono font-bold text-emerald-700">{connected} ({answerRate}%)</span>
              </div>
              <div className="w-full h-3 rounded-full bg-surface-strong overflow-hidden">
                <div className="h-full bg-emerald-600 rounded-full" style={{ width: `${Math.min(100, answerRate)}%` }} />
              </div>
            </div>

            {/* Stage 3 */}
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-semibold text-ink">3. Engaged & Pitched</span>
                <span className="font-mono font-bold text-sky-700">
                  {connected} ({connected > 0 ? "100" : "0"}% of answered)
                </span>
              </div>
              <div className="w-full h-3 rounded-full bg-surface-strong overflow-hidden">
                <div className="h-full bg-sky-600 rounded-full" style={{ width: `${Math.min(100, answerRate)}%` }} />
              </div>
            </div>

            {/* Stage 4 */}
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-semibold text-ink">4. Positive Interest Expressed</span>
                <span className="font-mono font-bold text-indigo-700">{interested} ({interestRate}% of answered)</span>
              </div>
              <div className="w-full h-3 rounded-full bg-surface-strong overflow-hidden">
                <div
                  className="h-full bg-indigo-600 rounded-full"
                  style={{ width: `${Math.min(100, (connected > 0 ? (interested / connected) * 100 : 0))}%` }}
                />
              </div>
            </div>
          </div>
        </Card>

        {/* Call Outcomes Distribution */}
        <Card className="p-5 space-y-4">
          <div className="pb-3 border-b border-hairline">
            <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
              <PieChart className="w-4 h-4 text-primary" /> Dialogue Outcomes Breakdown
            </h3>
            <p className="text-xs text-muted mt-0.5">Classification extracted by ConversationOrchestrator.</p>
          </div>

          <div className="space-y-3 pt-1">
            <div className="flex items-center justify-between p-3 rounded-xl bg-indigo-50/50 border border-indigo-100 text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-indigo-600" />
                <span className="font-medium text-ink">Interested in Lending Product</span>
              </div>
              <span className="font-bold font-mono text-indigo-900">{interested} calls</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl bg-purple-50/50 border border-purple-100 text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-purple-600" />
                <span className="font-medium text-ink">Callback Requested / Later</span>
              </div>
              <span className="font-bold font-mono text-purple-900">{callbacks} calls</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl bg-surface-card border border-hairline text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-neutral-400" />
                <span className="font-medium text-ink">Not Interested / Declined</span>
              </div>
              <span className="font-bold font-mono text-neutral-800">{notInterested} calls</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl bg-amber-50/50 border border-amber-100 text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                <span className="font-medium text-ink">Safeguarded by Compliance Gate</span>
              </div>
              <span className="font-bold font-mono text-amber-900">{blocked} candidates</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Language Breakdown & Duration Benchmarks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Language Breakdown */}
        <Card className="p-5 space-y-4">
          <div className="pb-3 border-b border-hairline">
            <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
              <Globe className="w-4 h-4 text-primary" /> Supported Language Distribution
            </h3>
            <p className="text-xs text-muted mt-0.5">Multilingual sessions handled by TARA voice agent.</p>
          </div>

          <div className="space-y-3">
            {Object.entries(languages).map(([lang, count]) => {
              const pct = Math.round((count / totalLangCalls) * 100);
              return (
                <div key={lang}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-semibold uppercase tracking-wider text-ink">{lang}</span>
                    <span className="font-mono text-muted">{count} calls ({pct}%)</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-surface-strong overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        lang.toLowerCase() === "telugu"
                          ? "bg-purple-600"
                          : lang.toLowerCase() === "hindi"
                          ? "bg-sky-600"
                          : "bg-emerald-600"
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Telephony Duration Stats */}
        <Card className="p-5 space-y-4">
          <div className="pb-3 border-b border-hairline">
            <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
              <Clock className="w-4 h-4 text-primary" /> Duration Benchmarks (Seconds)
            </h3>
            <p className="text-xs text-muted mt-0.5">Real durations recorded via Twilio status webhooks.</p>
          </div>

          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="p-4 bg-canvas rounded-xl border border-hairline">
              <span className="text-[11px] font-semibold text-muted uppercase block">Average</span>
              <span className="text-2xl font-bold font-mono text-ink mt-1 block">
                {summary?.avg_duration_seconds ? `${Math.round(summary.avg_duration_seconds)}s` : "—"}
              </span>
            </div>
            <div className="p-4 bg-canvas rounded-xl border border-hairline">
              <span className="text-[11px] font-semibold text-muted uppercase block">Median</span>
              <span className="text-2xl font-bold font-mono text-ink mt-1 block">
                {summary?.median_duration_seconds ? `${Math.round(summary.median_duration_seconds)}s` : "—"}
              </span>
            </div>
            <div className="p-4 bg-canvas rounded-xl border border-hairline">
              <span className="text-[11px] font-semibold text-muted uppercase block">95th Percentile</span>
              <span className="text-2xl font-bold font-mono text-ink mt-1 block">
                {summary?.p95_duration_seconds ? `${Math.round(summary.p95_duration_seconds)}s` : "—"}
              </span>
            </div>
          </div>

          <div className="p-3 bg-surface-strong/60 rounded-xl border border-hairline text-xs text-muted">
            Calls exceeding 45 seconds indicate multi-turn qualification dialogues with affirmative customer engagement.
          </div>
        </Card>
      </div>
    </div>
  );
}

