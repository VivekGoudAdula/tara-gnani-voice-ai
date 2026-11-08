import React, { useState } from "react";
import { CheckCircle2, ChevronRight } from "lucide-react";
import Badge from "../Badge";

export default function ModulesSection() {
  const [activeTab, setActiveTab] = useState("matches");

  const modules = [
    { id: "dashboard", label: "Dashboard" },
    { id: "matches", label: "Product Matches" },
    { id: "campaigns", label: "Campaigns" },
    { id: "history", label: "Interaction History" },
  ];

  const highlights = [
    "Live contact monitoring",
    "Interaction history and audit trail",
    "Explainable AI views",
    "Campaign orchestration",
  ];

  return (
    <section id="modules" className="py-16 lg:py-24 border-t border-hairline bg-canvas">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-12 items-start">
          
          {/* Left Column: Heading, Highlights, and Module Selector */}
          <div>
            <span className="t-label text-muted-soft block mb-2">Platform</span>
            <h2 className="t-display-lg font-bold text-ink mb-4">
              One platform, every module
            </h2>
            <p className="t-body-md text-body font-sans mb-8 leading-relaxed">
              Unified workflows connect customer records, explainable scoring rules, voice campaign dispatch, and auditable call logs.
            </p>

            {/* Highlights List */}
            <ul className="space-y-3 mb-8">
              {highlights.map((item, idx) => (
                <li key={idx} className="flex items-center gap-2.5 text-sm font-medium text-ink font-sans">
                  <CheckCircle2 className="w-4 h-4 text-semantic-success shrink-0" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>

            {/* Static Tab Selector (No animation) */}
            <div className="space-y-2">
              <span className="t-caption text-muted block mb-1">Select a module view:</span>
              <div className="flex flex-wrap gap-2">
                {modules.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setActiveTab(m.id)}
                    className={`px-3.5 py-1.5 rounded-lg text-xs font-medium font-sans border transition-colors cursor-pointer ${
                      activeTab === m.id
                        ? "bg-ink text-white border-ink shadow-xs"
                        : "bg-surface-card text-body hover:text-ink border-hairline hover:border-hairline-strong"
                    }`}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column: Clean Static Mock Component (Sample data only, NO result numbers) */}
          <div className="bg-surface-card rounded-2xl border border-hairline shadow-soft overflow-hidden">
            <div className="px-4 py-2.5 bg-canvas-soft border-b border-hairline flex items-center justify-between">
              <span className="text-[11px] font-mono text-muted">
                {modules.find((m) => m.id === activeTab)?.label} • Preview
              </span>
              <span className="text-[10px] uppercase font-semibold text-muted bg-surface-strong px-2 py-0.5 rounded border border-hairline">
                Sample data
              </span>
            </div>

            <div className="p-5 font-sans">
              {/* Tab 1: Dashboard Mock */}
              {activeTab === "dashboard" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-xl bg-canvas border border-hairline">
                      <span className="text-[11px] text-muted block mb-1">Audience Registry</span>
                      <span className="text-xs font-semibold text-ink">Customers & Leads loaded</span>
                    </div>
                    <div className="p-3 rounded-xl bg-canvas border border-hairline">
                      <span className="text-[11px] text-muted block mb-1">Product Catalog</span>
                      <span className="text-xs font-semibold text-ink">Policy criteria active</span>
                    </div>
                    <div className="p-3 rounded-xl bg-canvas border border-hairline">
                      <span className="text-[11px] text-muted block mb-1">Scoring Status</span>
                      <span className="text-xs font-semibold text-ink">Propensity ranked</span>
                    </div>
                    <div className="p-3 rounded-xl bg-canvas border border-hairline">
                      <span className="text-[11px] text-muted block mb-1">Compliance Barrier</span>
                      <span className="text-xs font-semibold text-emerald-700">Enforcing calling rules</span>
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-canvas border border-hairline">
                    <span className="text-[11px] text-muted block mb-1">System Operational State</span>
                    <p className="text-xs text-body leading-relaxed">
                      Borrower records unified with explicit consent flags. Outreach campaigns ready for audience segmentation.
                    </p>
                  </div>
                </div>
              )}

              {/* Tab 2: Product Matches Mock */}
              {activeTab === "matches" && (
                <div className="overflow-hidden border border-hairline rounded-xl">
                  <table className="w-full text-left text-xs table-fixed border-collapse">
                    <thead className="bg-canvas border-b border-hairline text-muted text-[11px] font-semibold uppercase">
                      <tr>
                        <th className="p-2.5">Prospect</th>
                        <th className="p-2.5">Product</th>
                        <th className="p-2.5">Fit Band</th>
                        <th className="p-2.5">Eligibility</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-hairline">
                      <tr>
                        <td className="p-2.5 truncate font-medium text-ink">Aarav Patel (Sample)</td>
                        <td className="p-2.5 truncate text-body">Home Loan Extension</td>
                        <td className="p-2.5"><Badge variant="purple" className="text-[10px] px-1.5 py-0.5">High Fit</Badge></td>
                        <td className="p-2.5"><Badge variant="success" className="text-[10px] px-1.5 py-0.5">Eligible</Badge></td>
                      </tr>
                      <tr>
                        <td className="p-2.5 truncate font-medium text-ink">Priya Rao (Sample)</td>
                        <td className="p-2.5 truncate text-body">Credit Card Upgrade</td>
                        <td className="p-2.5"><Badge variant="purple" className="text-[10px] px-1.5 py-0.5">High Fit</Badge></td>
                        <td className="p-2.5"><Badge variant="success" className="text-[10px] px-1.5 py-0.5">Eligible</Badge></td>
                      </tr>
                      <tr>
                        <td className="p-2.5 truncate font-medium text-ink">Vikram Sen (Sample)</td>
                        <td className="p-2.5 truncate text-body">Personal Loan</td>
                        <td className="p-2.5"><Badge variant="info" className="text-[10px] px-1.5 py-0.5">Medium Fit</Badge></td>
                        <td className="p-2.5"><Badge variant="success" className="text-[10px] px-1.5 py-0.5">Eligible</Badge></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}

              {/* Tab 3: Campaigns Mock */}
              {activeTab === "campaigns" && (
                <div className="space-y-3">
                  <div className="p-3.5 rounded-xl bg-canvas border border-hairline space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-ink">Personal Loan Cross-sell (Sample)</span>
                      <Badge variant="purple" className="text-[10px] px-1.5 py-0.5">Ready</Badge>
                    </div>
                    <div className="text-[11px] text-muted space-y-1">
                      <div>Audience: High-fit propensity band with captured consent</div>
                      <div>Voice Prompt: Pre-approved limit disclosure in Hindi & Telugu</div>
                      <div>Calling Window: 09:00 to 21:00 IST barrier enforced</div>
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-canvas border border-hairline flex items-center justify-between text-xs text-body">
                    <span>Retry Strategy: Configured for polite verification</span>
                    <span className="text-ink font-medium">Standard Policy</span>
                  </div>
                </div>
              )}

              {/* Tab 4: Interaction History Mock */}
              {activeTab === "history" && (
                <div className="overflow-hidden border border-hairline rounded-xl">
                  <table className="w-full text-left text-xs table-fixed border-collapse">
                    <thead className="bg-canvas border-b border-hairline text-muted text-[11px] font-semibold uppercase">
                      <tr>
                        <th className="p-2.5">Recipient</th>
                        <th className="p-2.5">Outcome</th>
                        <th className="p-2.5">Compliance</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-hairline">
                      <tr>
                        <td className="p-2.5 truncate font-medium text-ink">Rohan Verma (Sample)</td>
                        <td className="p-2.5 truncate text-body">Interested; callback requested</td>
                        <td className="p-2.5 text-emerald-700 font-medium">Consent verified</td>
                      </tr>
                      <tr>
                        <td className="p-2.5 truncate font-medium text-ink">Ananya Iyer (Sample)</td>
                        <td className="p-2.5 truncate text-body">Information shared in Telugu</td>
                        <td className="p-2.5 text-emerald-700 font-medium">Calling window valid</td>
                      </tr>
                      <tr>
                        <td className="p-2.5 truncate font-medium text-ink">Meera K. (Sample)</td>
                        <td className="p-2.5 truncate text-body">Declined offer politely</td>
                        <td className="p-2.5 text-muted">Frequency cap respected</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}
