import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, AlertCircle, Sparkles, CheckCircle2, XCircle } from "lucide-react";
import { api } from "../api/client";
import Badge from "./Badge";

export default function ProductMatchesSection({ entityType, entityId }) {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedMatchId, setExpandedMatchId] = useState(null);

  useEffect(() => {
    if (!entityId) return;
    let isMounted = true;
    setLoading(true);
    setError("");

    const endpoint = entityType === "lead" ? `/leads/${entityId}/matches` : `/customers/${entityId}/matches`;

    api
      .get(endpoint)
      .then((data) => {
        if (isMounted) setMatches(data || []);
      })
      .catch((err) => {
        if (isMounted) setError(err.message || "Failed to load product matches");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [entityType, entityId]);

  const toggleExpand = (matchId) => {
    setExpandedMatchId((prev) => (prev === matchId ? null : matchId));
  };

  const getBandVariant = (band) => {
    if (band === "HIGH") return "purple";
    if (band === "MEDIUM") return "info";
    return "default";
  };

  return (
    <div className="space-y-3 font-sans">
      <div className="flex items-center justify-between">
        <h4 className="t-label text-muted-soft flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-muted" />
          Product Fit & Policy Eligibility
        </h4>
        <span className="t-caption text-muted">{matches.length} Products Scored</span>
      </div>

      {/* Mandatory Regulatory / Ethical Disclaimer */}
      <div className="p-3 bg-surface-strong/60 rounded-xl border border-hairline t-caption text-body flex items-start gap-2">
        <AlertCircle className="w-4 h-4 text-muted shrink-0 mt-0.5" />
        <div>
          <span className="font-medium text-ink">Scoring Governance: </span>
          Fit score ranks likelihood of interest. Eligibility is decided by policy rules. A human approves every offer.
        </div>
      </div>

      {loading && (
        <div className="p-6 text-center text-muted t-caption bg-canvas rounded-xl border border-hairline">
          Evaluating product matches...
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/10 text-red-600 rounded-xl border border-red-500/20 t-caption">
          {error}
        </div>
      )}

      {!loading && !error && matches.length === 0 && (
        <div className="p-6 text-center text-muted t-caption bg-canvas rounded-xl border border-hairline">
          No matches evaluated yet. Run scoring from the Product Matches tab to generate fit scores.
        </div>
      )}

      {!loading && matches.length > 0 && (
        <div className="space-y-2.5">
          {matches.map((match) => {
            const isExpanded = expandedMatchId === match.id;
            return (
              <div
                key={match.id}
                className="bg-canvas rounded-xl border border-hairline overflow-hidden transition-colors"
              >
                {/* Header Row */}
                <div className="p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="t-body-strong text-ink truncate">{match.product_name}</span>
                      {match.fallback_model && (
                        <span className="t-label px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 text-[10px]">
                          Fallback Model
                        </span>
                      )}
                    </div>

                    {/* Progress Bar & Fit Score */}
                    <div className="mt-2 flex items-center gap-3">
                      <div className="w-36 h-2 rounded-full bg-surface-strong overflow-hidden shrink-0">
                        <div
                          className="h-full bg-ink/70 rounded-full"
                          style={{ width: `${Math.min(match.match_score, 100)}%` }}
                        />
                      </div>
                      <span className="t-body-strong text-ink">{match.match_score.toFixed(1)}%</span>
                      <span className="t-caption text-muted">Fit score</span>
                    </div>
                  </div>

                  {/* Status Badges & Action */}
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant={getBandVariant(match.band)}>{match.band}</Badge>
                    <Badge variant={match.eligibility === "ELIGIBLE" ? "success" : "danger"}>
                      {match.eligibility === "ELIGIBLE" ? "Eligible" : "Not Eligible"}
                    </Badge>
                    <button
                      onClick={() => toggleExpand(match.id)}
                      className="p-1.5 rounded-lg hover:bg-surface-strong text-muted hover:text-ink transition-colors flex items-center gap-1 t-caption"
                      title="Inspect rationale and policy checks"
                    >
                      <span>Why</span>
                      {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                {/* Expandable Why Details Panel */}
                {isExpanded && (
                  <div className="px-3.5 pb-4 pt-2 border-t border-hairline bg-surface-card/40 space-y-4">
                    {/* Imputed features notice */}
                    {match.imputed_features && match.imputed_features.length > 0 && (
                      <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 t-caption text-amber-800">
                        <span className="font-semibold">Imputed attributes: </span>
                        {match.imputed_features.join(", ")} (Missing data imputed using population median).
                      </div>
                    )}

                    {/* Deterministic Eligibility Policy Checks */}
                    <div>
                      <h5 className="t-label text-muted-soft mb-1.5">Deterministic Policy Rules</h5>
                      <div className="border border-hairline rounded-lg overflow-hidden divide-y divide-hairline bg-canvas">
                        {match.eligibility_checks.map((chk, idx) => (
                          <div key={idx} className="p-2.5 flex items-start justify-between text-xs gap-3">
                            <div className="flex items-start gap-2">
                              {chk.passed ? (
                                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                              ) : (
                                <XCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                              )}
                              <div>
                                <span className="font-medium text-ink block">{chk.rule}</span>
                                <span className="text-muted">{chk.message}</span>
                              </div>
                            </div>
                            <div className="text-right shrink-0">
                              <span className="font-medium text-ink block">
                                {typeof chk.value === "number" ? chk.value.toLocaleString() : String(chk.value)}
                              </span>
                              <span className="text-muted text-[10px]">
                                Threshold: {typeof chk.threshold === "number" ? chk.threshold.toLocaleString() : String(chk.threshold)}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Propensity ML Reason Codes */}
                    <div>
                      <h5 className="t-label text-muted-soft mb-1.5">Top Fit Reason Codes</h5>
                      <div className="space-y-1.5">
                        {match.reason_codes.map((rc, idx) => (
                          <div
                            key={idx}
                            className="p-2 rounded-lg bg-canvas border border-hairline flex items-center justify-between text-xs gap-2"
                          >
                            <div className="flex items-center gap-2 truncate">
                              <span
                                className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                                  rc.direction === "positive"
                                    ? "bg-emerald-500/10 text-emerald-700"
                                    : "bg-rose-500/10 text-rose-700"
                                }`}
                              >
                                {rc.direction === "positive" ? `+${rc.contribution_pp.toFixed(1)}pp` : `${rc.contribution_pp.toFixed(1)}pp`}
                              </span>
                              <span className="text-ink truncate">{rc.text}</span>
                            </div>
                            <span className="text-muted-soft text-[10px] shrink-0 font-mono">
                              {rc.code}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Model Lineage */}
                    <div className="pt-1 flex items-center justify-between t-caption text-muted-soft text-[11px]">
                      <span>Model Version: {match.model_version.slice(0, 12)}</span>
                      <span>Model ID: {match.model_id}</span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
