import React, { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  Radio,
  RefreshCw,
  PhoneCall,
  Activity,
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertCircle,
  Megaphone,
  Volume2,
} from "lucide-react";
import { api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Card from "../components/Card";
import CallDetailDrawer from "../components/outcomes/CallDetailDrawer";
import { formatDate } from "../utils/format";

export default function LiveCalls() {
  const navigate = useNavigate();
  const [liveCampaigns, setLiveCampaigns] = useState([]);
  const [activeCalls, setActiveCalls] = useState([]);
  const [recentCalls, setRecentCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [inspectedCallId, setInspectedCallId] = useState(null);
  const [elapsedTimer, setElapsedTimer] = useState(0);

  // Tick elapsed timer every second for realistic active call duration display
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedTimer((t) => t + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const fetchLiveTelemetry = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    try {
      const [campsRes, commsRes] = await Promise.all([
        api.get("/campaigns?page=1&page_size=50").catch(() => ({ items: [] })),
        api.get("/communications?page=1&page_size=30").catch(() => ({ items: [] })),
      ]);

      const items = campsRes?.items || [];
      const inFlightCamps = items.filter(
        (c) => c.status === "ACTIVE" || c.status === "LAUNCHING" || c.status === "RUNNING"
      );
      setLiveCampaigns(inFlightCamps);

      const allComms = commsRes?.items || [];
      // Distinguish in-flight (calling, dialing, in-progress) vs recently completed
      const inFlightCalls = allComms.filter((c) =>
        ["calling", "in-progress", "ringing", "dialing", "initiated"].includes((c.status || "").toLowerCase())
      );
      const pastCalls = allComms.filter(
        (c) => !["calling", "in-progress", "ringing", "dialing", "initiated"].includes((c.status || "").toLowerCase())
      );

      setActiveCalls(inFlightCalls);
      setRecentCalls(pastCalls.slice(0, 10));
      setLastUpdated(new Date());
    } catch (err) {
      console.error("Live call monitor fetch error:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchLiveTelemetry();

    // 6-second polling loop with document visibility guards
    const interval = setInterval(() => {
      if (document.visibilityState === "visible") {
        fetchLiveTelemetry();
      }
    }, 6000);

    return () => clearInterval(interval);
  }, [fetchLiveTelemetry]);

  return (
    <div className="space-y-6 font-sans">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-hairline">
        <div>
          <div className="flex items-center gap-2.5">
            <Radio className="w-5 h-5 text-rose-600 animate-pulse" />
            <h1 className="t-h1 text-ink">Live Outreach & Voice Telemetry</h1>
          </div>
          <p className="t-body text-muted mt-0.5 text-xs sm:text-sm">
            Real-time feed of in-flight telephony channels, SIP connections, and active voice AI dialogs.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block text-xs text-muted">
            <span>Polling every 6s</span>
            {lastUpdated && (
              <span className="block font-mono text-[11px] text-muted-soft">
                Sync: {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchLiveTelemetry(true)}
            disabled={refreshing || loading}
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${refreshing ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-4 bg-surface-card flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold text-muted uppercase tracking-wider block">
              In-Flight Voice Calls
            </span>
            <span className="text-2xl font-bold font-mono text-rose-600 mt-1 block">
              {activeCalls.length}
            </span>
          </div>
          <div className="p-3 rounded-full bg-rose-50 text-rose-600 border border-rose-100">
            <Volume2 className="w-5 h-5 animate-pulse" />
          </div>
        </Card>

        <Card className="p-4 bg-surface-card flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold text-muted uppercase tracking-wider block">
              Active Campaigns
            </span>
            <span className="text-2xl font-bold font-mono text-sky-600 mt-1 block">
              {liveCampaigns.length}
            </span>
          </div>
          <div className="p-3 rounded-full bg-sky-50 text-sky-600 border border-sky-100">
            <Megaphone className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 bg-surface-card flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold text-muted uppercase tracking-wider block">
              Recent Dispatches
            </span>
            <span className="text-2xl font-bold font-mono text-emerald-700 mt-1 block">
              {recentCalls.length}
            </span>
          </div>
          <div className="p-3 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </Card>
      </div>

      {/* In-Flight Voice Calls Table */}
      <Card className="p-0 overflow-hidden">
        <div className="p-4 border-b border-hairline flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-rose-600 animate-pulse" />
            <h3 className="text-sm font-semibold text-ink">In-Flight Telephone Calls ({activeCalls.length})</h3>
          </div>
          <span className="text-[11px] font-mono text-muted">Webhooks: Active</span>
        </div>

        {activeCalls.length === 0 ? (
          <div className="py-12 text-center text-xs text-muted space-y-2">
            <Activity className="w-8 h-8 mx-auto text-muted-soft" />
            <div className="font-medium text-ink">No calls currently active in real-time</div>
            <p className="max-w-md mx-auto text-[11px]">
              When an outbound campaign dispatches telephony or a recipient answers, their live channel state will stream here.
            </p>
          </div>
        ) : (
          <div className="w-full overflow-hidden">
            <table className="w-full text-left border-collapse table-fixed text-xs">
              <colgroup>
                <col style={{ width: "25%" }} />
                <col style={{ width: "20%" }} />
                <col style={{ width: "20%" }} />
                <col style={{ width: "15%" }} />
                <col style={{ width: "20%" }} />
              </colgroup>
              <thead>
                <tr className="border-b border-hairline bg-surface-strong/50 text-muted text-[11px] font-semibold uppercase tracking-wider">
                  <th className="py-2.5 px-3">Recipient Name & ID</th>
                  <th className="py-2.5 px-3">Phone</th>
                  <th className="py-2.5 px-3">Call Status</th>
                  <th className="py-2.5 px-3">Provider</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {activeCalls.map((call) => (
                  <tr key={call.id} className="hover:bg-surface-strong/30 bg-rose-50/20">
                    <td className="py-2.5 px-3 font-semibold text-ink truncate">
                      {call.recipient_name || "Lead / Customer"}
                      <span className="block text-[10px] text-muted font-mono mt-0.5">#{call.id.slice(-6)}</span>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-muted">{call.phone || "—"}</td>
                    <td className="py-2.5 px-3">
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-100 text-rose-800">
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-ping" />
                        {call.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-muted uppercase font-mono text-[11px]">{call.provider || "Twilio"}</td>
                    <td className="py-2.5 px-3 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setInspectedCallId(call.id)}
                        className="!py-0.5 !px-2 text-xs"
                      >
                        Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Active Campaigns Progress Feeds */}
      {liveCampaigns.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
            <Megaphone className="w-4 h-4 text-primary" /> Active Outreach Campaigns ({liveCampaigns.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {liveCampaigns.map((camp) => {
              const total = camp.total_recipients || 0;
              const contacted = camp.contacted_count || 0;
              const pct = total > 0 ? Math.round((contacted / total) * 100) : 0;

              return (
                <Card
                  key={camp.id}
                  className="p-4 hover:border-ink transition-all cursor-pointer space-y-3"
                  onClick={() => navigate(`/app/campaigns/${camp.id}`)}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-ink hover:underline">{camp.name}</h4>
                      <p className="text-xs text-muted mt-0.5">{camp.product_name} • {camp.entity_type}s</p>
                    </div>
                    <Badge variant="info">{camp.status}</Badge>
                  </div>

                  <div>
                    <div className="flex items-center justify-between text-xs text-muted mb-1">
                      <span>Dispatch Progress</span>
                      <span className="font-mono font-semibold text-ink">{contacted}/{total} ({pct}%)</span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-surface-strong overflow-hidden">
                      <div className="h-full bg-primary rounded-full transition-all duration-300" style={{ width: `${pct}%` }} />
                    </div>
                  </div>

                  <div className="pt-2 border-t border-hairline flex items-center justify-between text-xs text-muted">
                    <span>Config v{camp.config_version || 1}</span>
                    <span className="text-primary font-medium inline-flex items-center gap-1">
                      View Campaign <ArrowRight className="w-3 h-3" />
                    </span>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Recent Telephony Dispatches */}
      <Card className="p-0 overflow-hidden">
        <div className="p-4 border-b border-hairline flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-muted" />
            <h3 className="text-sm font-semibold text-ink">Recent Outbound Call Dispatches</h3>
          </div>
          <Link to="/app/conversations" className="text-xs text-primary font-medium hover:underline inline-flex items-center gap-1">
            <span>All Conversations</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {recentCalls.length === 0 ? (
          <div className="py-8 text-center text-xs text-muted">No completed dispatches yet.</div>
        ) : (
          <div className="w-full overflow-hidden">
            <table className="w-full text-left border-collapse table-fixed text-xs">
              <colgroup>
                <col style={{ width: "25%" }} />
                <col style={{ width: "20%" }} />
                <col style={{ width: "15%" }} />
                <col style={{ width: "20%" }} />
                <col style={{ width: "20%" }} />
              </colgroup>
              <thead>
                <tr className="border-b border-hairline bg-surface-strong/50 text-muted text-[11px] font-semibold uppercase tracking-wider">
                  <th className="py-2.5 px-3">Recipient</th>
                  <th className="py-2.5 px-3">Time</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Channel / Provider</th>
                  <th className="py-2.5 px-3 text-right">Recording & Transcript</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {recentCalls.map((c) => (
                  <tr key={c.id} className="hover:bg-surface-strong/30">
                    <td className="py-2.5 px-3 font-semibold text-ink truncate">
                      {c.recipient_name || "Recipient"}
                      <span className="block text-[10px] text-muted font-mono mt-0.5">#{c.id.slice(-6)}</span>
                    </td>
                    <td className="py-2.5 px-3 text-muted font-mono text-[11px]">{formatDate(c.created_at)}</td>
                    <td className="py-2.5 px-3">
                      <Badge
                        variant={c.status === "completed" ? "success" : c.status === "blocked" ? "warning" : "default"}
                        className="text-[10px]"
                      >
                        {c.status}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3 text-muted uppercase font-mono text-[11px]">{c.provider || "Twilio"}</td>
                    <td className="py-2.5 px-3 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setInspectedCallId(c.id)}
                        className="!py-0.5 !px-2 text-xs"
                      >
                        Transcript
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Embedded Call Detail & Transcript Drawer */}
      <CallDetailDrawer callId={inspectedCallId} onClose={() => setInspectedCallId(null)} />
    </div>
  );
}

