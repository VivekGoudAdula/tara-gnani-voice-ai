import React from "react";
import { Link } from "react-router-dom";
import { History, ArrowRight, ShieldCheck, User } from "lucide-react";
import Badge from "../Badge";

export default function RecentActivity({ activities = [] }) {
  const getActionBadge = (action = "") => {
    const act = action.toLowerCase();
    if (act.includes("import") || act.includes("sample")) return <Badge variant="info">{action}</Badge>;
    if (act.includes("score")) return <Badge variant="purple">{action}</Badge>;
    if (act.includes("send") || act.includes("launch")) return <Badge variant="success">{action}</Badge>;
    if (act.includes("block") || act.includes("fail")) return <Badge variant="danger">{action}</Badge>;
    return <Badge variant="default">{action}</Badge>;
  };

  const formatActivitySummary = (item) => {
    if (item.details?.file_name) {
      return `Imported "${item.details.file_name}" (${item.details.imported_count || 0} valid records)`;
    }
    if (item.details?.name) {
      return `Updated product "${item.details.name}"`;
    }
    if (item.details?.total_scored !== undefined) {
      return `Scored ${item.details.total_scored} profiles against active catalog`;
    }
    if (item.details?.campaign_name) {
      return `Campaign "${item.details.campaign_name}" (${item.details.recipient_count || 0} recipients)`;
    }
    if (item.details?.reason) {
      return `Action reason: ${item.details.reason}`;
    }
    return item.action || "Workspace event";
  };

  return (
    <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-hairline">
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-muted" />
          <h2 className="t-h2 text-ink">Recent Activity & Audit Trail</h2>
        </div>
        <Link
          to="/app/governance"
          className="text-xs font-medium text-indigo-600 hover:text-indigo-800 inline-flex items-center gap-1"
        >
          <span>Full Audit Log</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {activities.length === 0 ? (
        <div className="p-8 text-center bg-canvas rounded-xl border border-hairline space-y-3">
          <p className="t-caption text-muted">No activity has been recorded yet in this workspace.</p>
          <Link
            to="/app/data-import"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-ink text-canvas text-xs font-medium hover:bg-ink/90 transition-colors"
          >
            <span>Import your first dataset</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      ) : (
        <div className="divide-y divide-hairline bg-canvas rounded-xl border border-hairline overflow-hidden">
          {activities.slice(0, 10).map((act, idx) => {
            const timeStr = act.created_at
              ? new Date(act.created_at).toLocaleString([], {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "Just now";

            return (
              <div
                key={act.id || idx}
                className="p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-surface-card/40 transition-colors"
              >
                <div className="flex items-start sm:items-center gap-3">
                  <div className="p-2 rounded-lg bg-surface-strong text-muted shrink-0 mt-0.5 sm:mt-0">
                    <User className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="t-body-strong text-ink">{act.actor_name || "System"}</span>
                      {getActionBadge(act.action)}
                      {act.entity_type && (
                        <span className="text-[11px] font-mono text-muted-soft uppercase">
                          {act.entity_type}
                        </span>
                      )}
                    </div>
                    <p className="t-caption text-muted mt-0.5">
                      {formatActivitySummary(act)}
                    </p>
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <span className="t-caption text-muted font-mono">{timeStr}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
