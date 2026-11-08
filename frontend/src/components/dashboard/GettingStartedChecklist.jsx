import React from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Circle, AlertCircle, ArrowRight } from "lucide-react";

export default function GettingStartedChecklist({ checklist }) {
  if (!checklist) return null;

  // Normalize array or object structure
  const rawSteps = Array.isArray(checklist) ? checklist : Object.values(checklist);

  const steps = rawSteps.map((s, idx) => ({
    id: s.id || `step-${idx + 1}`,
    stepNum: s.step || idx + 1,
    title: s.title || `Step ${idx + 1}`,
    desc: s.detail || s.desc || "",
    status: (s.state || s.status || "blocked").toUpperCase(),
    link: s.link || "/app/dashboard",
    actionText: s.action_label || s.actionText || "View",
  }));

  const completedCount = steps.filter((s) => s.status === "DONE").length;

  const renderStatusBadge = (status) => {
    if (status === "DONE") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-700">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Done
        </span>
      );
    }
    if (status === "NEXT") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-700">
          <Circle className="w-3.5 h-3.5 text-indigo-600 fill-indigo-200" /> Next
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-surface-strong text-muted">
        <AlertCircle className="w-3.5 h-3.5 text-muted" /> Blocked
      </span>
    );
  };

  return (
    <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft space-y-4 font-sans">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-hairline">
        <div>
          <h2 className="t-h2 text-ink">Getting Started Workflow</h2>
          <p className="t-caption text-muted mt-0.5">
            End-to-end guidance from data loading to verified audit evidence
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="t-caption text-muted font-medium block">
              {completedCount} of {steps.length} completed
            </span>
          </div>
          <div className="w-24 h-2 rounded-full bg-surface-strong overflow-hidden shrink-0">
            <div
              className="h-full bg-emerald-600 rounded-full transition-all duration-300"
              style={{ width: `${steps.length > 0 ? (completedCount / steps.length) * 100 : 0}%` }}
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
        {steps.map((step) => {
          const isNext = step.status === "NEXT";
          return (
            <div
              key={step.id}
              className={`p-3.5 rounded-xl border transition-all flex flex-col justify-between ${
                isNext
                  ? "bg-white border-indigo-200 shadow-sm ring-1 ring-indigo-500/20"
                  : step.status === "DONE"
                  ? "bg-canvas border-hairline"
                  : "bg-surface-card/40 border-hairline/60 opacity-75"
              }`}
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-1">
                  {renderStatusBadge(step.status)}
                  <span className="text-[11px] font-mono text-muted-soft font-semibold">
                    0{step.stepNum}
                  </span>
                </div>
                <div>
                  <h3 className="t-body-strong text-ink">{step.title}</h3>
                  <p className="t-caption text-muted mt-1 leading-snug">{step.desc}</p>
                </div>
              </div>

              <div className="pt-3 mt-3 border-t border-hairline">
                <Link
                  to={step.link}
                  className={`inline-flex items-center gap-1.5 text-xs font-medium transition-colors ${
                    isNext
                      ? "text-indigo-600 hover:text-indigo-800"
                      : "text-ink hover:text-indigo-600"
                  }`}
                >
                  <span>{step.actionText}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
