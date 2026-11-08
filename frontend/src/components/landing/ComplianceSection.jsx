import React from "react";
import { CheckCircle2 } from "lucide-react";

export default function ComplianceSection() {
  const checks = [
    "Tenant-isolated workspaces",
    "Audit log of every attempt",
    "Transparent reason codes",
    "Policy gates on eligibility",
  ];

  return (
    <section id="compliance" className="py-16 lg:py-24 border-t border-hairline bg-canvas">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-surface-card border border-hairline rounded-2xl p-8 lg:p-12 shadow-soft">
          <div className="max-w-[760px]">
            <span className="t-label text-muted-soft block mb-3">Governance</span>
            <h2 className="t-display-lg font-bold text-ink mb-4">Built for regulated banking</h2>
            <p className="t-body-md text-body mb-8 font-sans leading-relaxed">
              Each bank's data is kept in its own isolated workspace, every communication attempt is written to an audit log, and every match shows the reasons behind its score. The model ranks fit; policy rules decide eligibility, and a human approves every offer.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
              {checks.map((item, idx) => (
                <div key={idx} className="flex items-center gap-2.5 t-body-sm font-medium text-ink font-sans">
                  <CheckCircle2 className="w-4 h-4 text-semantic-success shrink-0" />
                  <span>{item}</span>
                </div>
              ))}
            </div>

            <p className="text-xs text-muted-soft font-sans border-t border-hairline pt-4">
              The scoring models in this demo are trained on synthetic data. A pilot retrains on the lender's own conversion history.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
