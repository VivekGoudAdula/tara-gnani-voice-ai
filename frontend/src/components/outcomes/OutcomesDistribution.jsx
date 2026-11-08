import React from "react";
import { ShieldCheck, CheckCircle2, Webhook, BarChart2 } from "lucide-react";
import Card from "../Card";

export default function OutcomesDistribution({ summary }) {
  const s = summary || {};
  const completed = s.completed || 0;
  const oc = s.outcome_counts || {};
  const totalOutcomes = (oc.interested || 0) + (oc.callback || 0) + (oc.not_interested || 0) + (oc.other || 0) + (oc.unknown || 0);

  const outcomeBars = [
    { label: "Interested", count: oc.interested || 0, color: "bg-emerald-500", text: "text-emerald-700" },
    { label: "Callback", count: oc.callback || 0, color: "bg-amber-500", text: "text-amber-700" },
    { label: "Not Interested", count: oc.not_interested || 0, color: "bg-stone-400", text: "text-stone-700" },
    { label: "Other / Ambiguous", count: oc.other || 0, color: "bg-sky-400", text: "text-sky-700" },
    { label: "Unknown (No extraction)", count: oc.unknown || 0, color: "bg-stone-200", text: "text-stone-500" },
  ];

  const fr = s.extraction_fill_rate || {};
  const fillRates = [
    { label: "Interest Level", pct: fr.interest_level ?? 0 },
    { label: "Preferred Loan Amount", pct: fr.preferred_amount ?? 0 },
    { label: "Callback Preference", pct: fr.preferred_callback_time ?? 0 },
    { label: "Language Detected", pct: fr.language_used ?? 0 },
  ];

  const blockedReasons = Object.entries(s.blocked_by_reason || {});
  const wh = s.webhook_delivery || {};

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* 1. Static Outcome Distribution */}
      <Card className="p-4 space-y-3 bg-surface-card">
        <h4 className="t-heading-xs text-ink flex items-center gap-1.5 pb-2 border-b border-hairline">
          <BarChart2 className="w-4 h-4 text-muted" /> Outcome Distribution
        </h4>
        <div className="space-y-2.5">
          {outcomeBars.map((b) => {
            const pct = totalOutcomes > 0 ? Math.round((b.count / totalOutcomes) * 100) : 0;
            return (
              <div key={b.label} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-body">{b.label}</span>
                  <span className={`font-mono font-semibold ${b.text}`}>
                    {b.count} <span className="text-muted font-normal">({pct}%)</span>
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-surface-strong overflow-hidden">
                  <div className={`h-full ${b.color}`} style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* 2. Extraction Fill Rates */}
      <Card className="p-4 space-y-3 bg-surface-card">
        <h4 className="t-heading-xs text-ink flex items-center gap-1.5 pb-2 border-b border-hairline">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Structured Extraction Fill Rates
        </h4>
        <div className="space-y-3">
          {fillRates.map((f) => (
            <div key={f.label} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-body">{f.label}</span>
                <span className="font-mono font-semibold text-ink">{f.pct}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-surface-strong overflow-hidden">
                <div className="h-full bg-emerald-600" style={{ width: `${Math.min(100, Math.max(0, f.pct))}%` }} />
              </div>
            </div>
          ))}
          <p className="t-body-xs text-muted pt-1">
            Measured across {completed} completed session(s). Fields are extracted by AI during live conversation.
          </p>
        </div>
      </Card>

      {/* 3. Compliance Blocks & Webhook Delivery Line */}
      <Card className="p-4 space-y-3 bg-surface-card flex flex-col justify-between">
        <div>
          <h4 className="t-heading-xs text-ink flex items-center gap-1.5 pb-2 border-b border-hairline">
            <ShieldCheck className="w-4 h-4 text-amber-600" /> Compliance Gate Safeguards
          </h4>
          {blockedReasons.length === 0 ? (
            <div className="py-4 text-center text-muted t-body-xs">No calls blocked in filtered selection.</div>
          ) : (
            <div className="flex flex-wrap gap-1.5 pt-2">
              {blockedReasons.map(([reason, count]) => (
                <span key={reason} className="px-2.5 py-1 rounded-md text-xs font-mono bg-amber-50 border border-amber-200 text-amber-900">
                  {reason}: <strong>{count}</strong>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Webhook Delivery Line */}
        <div className="p-2.5 rounded-lg bg-surface-strong/50 border border-hairline flex items-center gap-2 t-body-xs text-muted">
          <Webhook className="w-4 h-4 text-sky-600 shrink-0" />
          <span>
            <strong className="text-ink font-mono">{wh.communications_with_terminal_status || 0}</strong> of{" "}
            <strong className="text-ink font-mono">{s.dispatched || 0}</strong> dispatched calls reached a terminal status via webhook.
            {(wh.missing_terminal || 0) > 0 && (
              <span className="ml-1.5 text-amber-600 font-medium">
                ({wh.missing_terminal} missing)
              </span>
            )}
          </span>
        </div>
      </Card>
    </div>
  );
}
