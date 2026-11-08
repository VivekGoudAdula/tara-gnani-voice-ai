import React from "react";
import { Link } from "react-router-dom";
import {
  Users,
  UserCheck,
  Package,
  Sparkles,
  Megaphone,
  PhoneCall,
  ShieldAlert,
  ArrowRight,
} from "lucide-react";
import Badge from "../Badge";

export default function DashboardMetrics({ summary }) {
  if (!summary) return null;

  const leads_count = summary.leads ?? summary.leads_count ?? 0;
  const customers_count = summary.customers ?? summary.customers_count ?? 0;
  const products_count = summary.products ?? summary.products_count ?? summary.active_products ?? 0;
  const raw_last_run = summary.last_scoring_run?.last_run_at || summary.last_scoring_run?.last_run;
  const isValidStr = typeof raw_last_run === "string" && raw_last_run.trim() !== "" && !raw_last_run.startsWith("None");
  const parsedDate = isValidStr ? new Date(raw_last_run) : null;
  const isDateValid = parsedDate && !isNaN(parsedDate.getTime());
  const last_scoring_run = isDateValid ? {
    last_run: parsedDate,
    stale: Boolean(summary.last_scoring_run?.is_stale || summary.last_scoring_run?.stale),
  } : null;
  const campaigns_total = summary.campaigns?.total ?? summary.campaigns_total ?? 0;
  const campaigns_by_status = summary.campaigns?.by_status ?? summary.campaigns_by_status ?? {};
  const outcomes = summary.calls ?? summary.outcomes ?? { attempted: 0, completed: 0, interested: 0 };
  const blocked_by_compliance = summary.compliance_blocked ?? summary.blocked_by_compliance ?? 0;

  return (
    <div id="dashboard-metrics-grid" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Leads Card */}
      <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft flex flex-col justify-between">
        <div className="flex items-start justify-between">
          <div>
            <span className="t-label text-muted-soft block">Audience Leads</span>
            <div className="mt-2 text-2xl font-semibold text-ink font-mono">
              {leads_count.toLocaleString()}
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-canvas border border-hairline text-muted">
            <Users className="w-5 h-5" />
          </div>
        </div>
        <div className="mt-4 pt-3 border-t border-hairline flex items-center justify-between text-xs">
          <Link to="/app/leads" className="text-muted hover:text-ink inline-flex items-center gap-1 font-medium">
            <span>View Leads</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
          <Link to="/app/data-import" className="text-indigo-600 hover:text-indigo-800 font-medium">
            + Import
          </Link>
        </div>
      </div>

      {/* 2. Customers Card */}
      <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft flex flex-col justify-between">
        <div className="flex items-start justify-between">
          <div>
            <span className="t-label text-muted-soft block">Portfolio Customers</span>
            <div className="mt-2 text-2xl font-semibold text-ink font-mono">
              {customers_count.toLocaleString()}
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-canvas border border-hairline text-muted">
            <UserCheck className="w-5 h-5" />
          </div>
        </div>
        <div className="mt-4 pt-3 border-t border-hairline flex items-center justify-between text-xs">
          <Link to="/app/customers" className="text-muted hover:text-ink inline-flex items-center gap-1 font-medium">
            <span>View Customers</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
          <Link to="/app/data-import" className="text-indigo-600 hover:text-indigo-800 font-medium">
            + Import
          </Link>
        </div>
      </div>

      {/* 3. Products Card */}
      <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft flex flex-col justify-between">
        <div className="flex items-start justify-between">
          <div>
            <span className="t-label text-muted-soft block">Active Products</span>
            <div className="mt-2 text-2xl font-semibold text-ink font-mono">
              {products_count.toLocaleString()}
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-canvas border border-hairline text-muted">
            <Package className="w-5 h-5" />
          </div>
        </div>
        <div className="mt-4 pt-3 border-t border-hairline flex items-center justify-between text-xs">
          <Link to="/app/products" className="text-muted hover:text-ink inline-flex items-center gap-1 font-medium">
            <span>Product Catalog</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
          <span className="text-muted-soft">Policy rules active</span>
        </div>
      </div>

      {/* 4. Last Scoring Run Card */}
      <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft flex flex-col justify-between">
        <div className="flex items-start justify-between">
          <div>
            <span className="t-label text-muted-soft block">Scoring Engine</span>
            <div className="mt-2 text-sm font-semibold text-ink">
              {last_scoring_run?.last_run ? (
                <>
                  <div className="text-ink">
                    {last_scoring_run.last_run.toLocaleDateString()}
                  </div>
                  <div className="text-xs text-muted font-normal">
                    {last_scoring_run.last_run.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </>
              ) : (
                <span className="text-muted font-normal">Not run yet</span>
              )}
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-canvas border border-hairline text-muted">
            <Sparkles className="w-5 h-5" />
          </div>
        </div>
        <div className="mt-4 pt-3 border-t border-hairline flex items-center justify-between text-xs">
          <Link to="/app/matches" className="text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1">
            <span>{last_scoring_run?.last_run ? "View Matches" : "Run Scoring"}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
          {last_scoring_run?.stale && (
            <Badge variant="warning">Stale Rules</Badge>
          )}
        </div>
      </div>

      {/* 5. Campaigns Summary Card */}
      <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft flex flex-col justify-between">
        <div className="flex items-start justify-between">
          <div>
            <span className="t-label text-muted-soft block">Campaigns</span>
            <div className="mt-2 text-2xl font-semibold text-ink font-mono">
              {campaigns_total}
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-canvas border border-hairline text-muted">
            <Megaphone className="w-5 h-5" />
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
          {Object.entries(campaigns_by_status).map(([status, cnt]) => (
            <span
              key={status}
              className="px-2 py-0.5 rounded bg-surface-strong text-muted text-[11px] font-medium"
            >
              {status}: <strong className="text-ink">{cnt}</strong>
            </span>
          ))}
          {campaigns_total === 0 && (
            <span className="text-xs text-muted">No campaigns created</span>
          )}
        </div>
        <div className="mt-4 pt-3 border-t border-hairline flex items-center justify-between text-xs">
          <Link to="/app/campaigns" className="text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1">
            <span>Manage Campaigns</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* 6. Outreach Calls Summary Card */}
      <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft flex flex-col justify-between sm:col-span-2">
        <div className="flex items-start justify-between">
          <div>
            <span className="t-label text-muted-soft block">Outreach Calls (All Time)</span>
            <div className="mt-2 grid grid-cols-3 gap-4">
              <div>
                <span className="text-xs text-muted block">Attempted</span>
                <span className="text-xl font-semibold text-ink font-mono">
                  {outcomes.attempted.toLocaleString()}
                </span>
              </div>
              <div>
                <span className="text-xs text-muted block">Completed</span>
                <span className="text-xl font-semibold text-emerald-700 font-mono">
                  {outcomes.completed.toLocaleString()}
                </span>
              </div>
              <div>
                <span className="text-xs text-muted block">Interested</span>
                <span className="text-xl font-semibold text-indigo-700 font-mono">
                  {outcomes.interested.toLocaleString()}
                </span>
              </div>
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-canvas border border-hairline text-muted">
            <PhoneCall className="w-5 h-5" />
          </div>
        </div>
        <div className="mt-4 pt-3 border-t border-hairline flex items-center justify-between text-xs">
          <Link to="/app/outcomes" className="text-muted hover:text-ink inline-flex items-center gap-1 font-medium">
            <span>Interaction History & Audio Evidence</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
          <Link to="/app/live-monitor" className="text-indigo-600 hover:text-indigo-800 font-medium">
            Live Monitor &rarr;
          </Link>
        </div>
      </div>

      {/* 7. Blocked by Compliance */}
      <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft flex flex-col justify-between">
        <div className="flex items-start justify-between">
          <div>
            <span className="t-label text-muted-soft block">Compliance Guardrail</span>
            <div className="mt-2 text-2xl font-semibold text-rose-700 font-mono">
              {blocked_by_compliance.toLocaleString()}
            </div>
            <span className="text-[11px] text-muted block mt-1">Blocked at dispatch</span>
          </div>
          <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-700">
            <ShieldAlert className="w-5 h-5" />
          </div>
        </div>
        <div className="mt-4 pt-3 border-t border-hairline flex items-center justify-between text-xs">
          <span className="text-muted">DND, Consent & Cap</span>
          <Link to="/app/outcomes?status=blocked" className="text-muted hover:text-ink font-medium">
            Audit logs &rarr;
          </Link>
        </div>
      </div>
    </div>
  );
}
