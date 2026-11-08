import React from "react";
import { Info } from "lucide-react";
import Card from "../Card";

export default function OutcomesSummaryCards({ summary }) {
  const s = summary || {};
  const defs = s.definitions || {};

  const cards = [
    {
      label: "Attempted",
      value: s.attempted ?? 0,
      definition: defs.attempted || "Total outbound outreach calls initiated or scheduled.",
      color: "text-ink",
    },
    {
      label: "Blocked",
      value: s.blocked ?? 0,
      definition: defs.blocked || "Calls safeguarded by TRAI compliance gates (calling hours, consent, DND, allowlist).",
      color: "text-semantic-error",
    },
    {
      label: "Connected",
      value: s.connected ?? 0,
      definition: defs.connected || "Calls reaching terminal status COMPLETED with duration_seconds > 0, verifying live audio connection.",
      color: "text-emerald-700",
    },
    {
      label: "Completed",
      value: s.completed ?? 0,
      definition: defs.completed || "Calls that successfully concluded their conversation session.",
      color: "text-emerald-600",
    },
    {
      label: "Avg Duration",
      value: s.avg_duration_seconds !== null && s.avg_duration_seconds !== undefined ? `${s.avg_duration_seconds}s` : "—",
      definition: defs.avg_duration_seconds || "Arithmetic mean duration of connected calls in seconds.",
      color: "text-ink font-mono",
    },
    {
      label: "Median Latency",
      value: s.latency?.available ? `${s.latency.median_ms}ms` : "N/A",
      definition: defs.latency || "Round-trip processing latency extracted from provider payloads.",
      color: s.latency?.available ? "text-sky-700 font-mono" : "text-muted",
    },
    {
      label: "Interested",
      value: s.outcome_counts?.interested ?? 0,
      definition: "Conversations where the customer expressed positive interest in the product offer.",
      color: "text-emerald-600 font-bold",
    },
    {
      label: "Callback",
      value: s.outcome_counts?.callback ?? 0,
      definition: "Conversations where the customer requested a callback at a later time.",
      color: "text-amber-600 font-bold",
    },
    {
      label: "Not Interested",
      value: s.outcome_counts?.not_interested ?? 0,
      definition: "Conversations where the customer declined the product offer.",
      color: "text-muted font-bold",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 2xl:grid-cols-9 gap-2.5">
      {cards.map((c, i) => (
        <Card key={i} className="p-3 bg-surface-card relative group hover:border-hairline-strong transition-colors min-w-0">
          <div className="flex items-center justify-between gap-1">
            <span className="t-label text-[11px] text-muted truncate" title={c.label}>{c.label}</span>
            <div className="relative shrink-0">
              <Info className="w-3 h-3 text-muted-soft hover:text-muted cursor-help" />
              <div className="absolute right-0 bottom-full mb-1.5 hidden group-hover:block z-30 w-48 p-2 rounded-lg bg-surface-dark text-on-dark text-[11px] shadow-lg pointer-events-none">
                {c.definition}
              </div>
            </div>
          </div>
          <div className={`text-lg sm:text-xl font-bold font-mono mt-1 ${c.color} truncate`} title={String(c.value)}>{c.value}</div>
        </Card>
      ))}
    </div>
  );
}
