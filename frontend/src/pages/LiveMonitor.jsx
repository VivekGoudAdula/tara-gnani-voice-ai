import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Radio, RefreshCw, Eye, Megaphone, ArrowRight, Activity, Clock } from "lucide-react";
import { api } from "../api/client";
import Badge from "../components/Badge";
import Button from "../components/Button";

export default function LiveMonitor() {
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [isPaused, setIsPaused] = useState(false);
  const [error, setError] = useState("");

  const fetchLiveCampaigns = useCallback(async () => {
    try {
      // Fetch both active and launching campaigns
      const res = await api.get("/campaigns?page=1&page_size=50");
      const items = res?.items || [];
      const liveItems = items.filter(
        (c) => c.status === "ACTIVE" || c.status === "LAUNCHING"
      );
      setCampaigns(liveItems);
      setLastUpdated(new Date());
      setError("");
    } catch (err) {
      console.error("Live monitor fetch error:", err);
      setError(err.message || "Failed to update live monitor.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    fetchLiveCampaigns();

    // 10s Polling, paused when tab is hidden
    const intervalId = setInterval(() => {
      if (!document.hidden) {
        fetchLiveCampaigns();
      }
    }, 10000);

    const handleVisibilityChange = () => {
      if (document.hidden) {
        setIsPaused(true);
      } else {
        setIsPaused(false);
        fetchLiveCampaigns();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [fetchLiveCampaigns]);

  const getStatusBadge = (status) => {
    if (status === "ACTIVE") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-700 animate-pulse">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          ACTIVE LIVE
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-700">
        <span className="w-2 h-2 rounded-full bg-amber-500" />
        LAUNCHING
      </span>
    );
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-hairline">
        <div>
          <div className="flex items-center gap-2.5">
            <Radio className="w-5 h-5 text-rose-600 animate-pulse" />
            <h1 className="t-h1 text-ink">Live Outreach Monitor</h1>
          </div>
          <p className="t-body text-muted mt-1">
            Real-time feed of active and launching campaigns. Auto-refreshes every 10 seconds.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block">
            <span className="t-caption text-muted block">
              {isPaused ? "Paused (Tab Hidden)" : "Live Polling (10s)"}
            </span>
            {lastUpdated && (
              <span className="text-[11px] font-mono text-muted-soft">
                Updated: {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchLiveCampaigns}
            disabled={loading}
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh Now</span>
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-600 rounded-xl t-caption">
          {error}
        </div>
      )}

      {loading && campaigns.length === 0 ? (
        <div className="p-12 text-center text-muted t-body bg-surface-card rounded-2xl border border-hairline">
          Checking for active and launching campaigns...
        </div>
      ) : campaigns.length === 0 ? (
        <div className="bg-surface-card rounded-2xl border border-hairline p-10 text-center space-y-4 shadow-soft">
          <div className="p-4 rounded-full bg-canvas border border-hairline w-16 h-16 flex items-center justify-center mx-auto text-muted">
            <Megaphone className="w-8 h-8" />
          </div>
          <div className="max-w-md mx-auto">
            <h3 className="t-h2 text-ink">No Campaigns Currently In-Flight</h3>
            <p className="t-caption text-muted mt-1">
              There are currently no campaigns with status ACTIVE or LAUNCHING. Launch a draft campaign or create a new campaign to monitor real-time recipient status counts.
            </p>
          </div>
          <div className="pt-2">
            <Button
              id="goto-campaigns-btn"
              variant="primary"
              onClick={() => navigate("/app/campaigns")}
            >
              <span>View Campaigns Catalogue</span>
              <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {campaigns.map((camp) => {
            const counts = camp.recipient_counts || {};
            const total = camp.total_recipients || 0;
            const queued = counts.QUEUED || 0;
            const contacted = camp.contacted_count || 0;
            const interested = counts.INTERESTED || 0;
            const blocked = counts.BLOCKED || 0;
            const failed = counts.FAILED || 0;

            const progressPct = total > 0 ? Math.round((contacted / total) * 100) : 0;

            return (
              <div
                key={camp.id}
                onClick={() => navigate(`/app/campaigns/${camp.id}`)}
                className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft hover:border-indigo-300 cursor-pointer transition-all space-y-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="t-h2 text-ink hover:text-indigo-600 transition-colors">
                        {camp.name}
                      </h3>
                      {camp.test_run_label && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-700">
                          {camp.test_run_label}
                        </span>
                      )}
                    </div>
                    <p className="t-caption text-muted mt-0.5">
                      Target Product: <strong className="text-ink">{camp.product_name}</strong> • Type: {camp.entity_type}
                    </p>
                  </div>
                  {getStatusBadge(camp.status)}
                </div>

                {/* Progress bar */}
                <div>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="text-muted">Outreach Progress</span>
                    <span className="t-body-strong text-ink">{progressPct}% ({contacted} / {total})</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-surface-strong overflow-hidden">
                    <div
                      className="h-full bg-indigo-600 rounded-full transition-all duration-300"
                      style={{ width: `${progressPct}%` }}
                    />
                  </div>
                </div>

                {/* Live recipient counts grid */}
                <div className="grid grid-cols-4 gap-2 pt-2 border-t border-hairline text-center text-xs">
                  <div className="p-2 bg-canvas rounded-lg border border-hairline">
                    <span className="text-muted text-[11px] block">Queued</span>
                    <span className="font-semibold text-ink font-mono">{queued}</span>
                  </div>
                  <div className="p-2 bg-canvas rounded-lg border border-hairline">
                    <span className="text-emerald-700 text-[11px] block">Contacted</span>
                    <span className="font-semibold text-emerald-700 font-mono">{contacted}</span>
                  </div>
                  <div className="p-2 bg-canvas rounded-lg border border-hairline">
                    <span className="text-indigo-700 text-[11px] block">Interested</span>
                    <span className="font-semibold text-indigo-700 font-mono">{interested}</span>
                  </div>
                  <div className="p-2 bg-canvas rounded-lg border border-hairline">
                    <span className="text-rose-700 text-[11px] block">Blocked</span>
                    <span className="font-semibold text-rose-700 font-mono">{blocked}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs pt-1 text-muted">
                  <span className="font-mono text-[11px]">ID: {camp.id.slice(0, 8)}...</span>
                  <span className="text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1">
                    <span>Inspect Detail & Telephony</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
