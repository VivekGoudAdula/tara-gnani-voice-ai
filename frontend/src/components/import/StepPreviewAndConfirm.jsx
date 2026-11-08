import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  Sparkles,
  Users,
  ArrowLeft,
  ArrowRight,
  AlertTriangle,
} from "lucide-react";
import Button from "../Button";
import Badge from "../Badge";

export default function StepPreviewAndConfirm({
  entityType,
  validationResult,
  onConfirm,
  confirming,
  confirmedResult,
  onBack,
}) {
  const navigate = useNavigate();
  const [attestConsent, setAttestConsent] = useState(false);

  if (!validationResult) return null;

  const { counts = {}, flags = {}, problems = [] } = validationResult;

  if (confirmedResult) {
    return (
      <div className="space-y-6 font-sans">
        <div className="p-6 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-emerald-600 text-white flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h2 className="t-h2 text-emerald-950">Import Completed Successfully</h2>
          <p className="t-body text-emerald-900 max-w-lg mx-auto">
            {confirmedResult.imported_count} records were committed to the workspace database with source="csv_import".
            {confirmedResult.duplicates_skipped > 0 && ` (${confirmedResult.duplicates_skipped} duplicates safely skipped).`}
          </p>

          <div className="grid grid-cols-3 gap-3 max-w-md mx-auto pt-3">
            <div className="p-3 bg-white rounded-xl border border-hairline text-center">
              <span className="t-label text-muted block mb-1">Imported</span>
              <span className="t-body-strong text-emerald-700 text-lg">{confirmedResult.imported_count}</span>
            </div>
            <div className="p-3 bg-white rounded-xl border border-hairline text-center">
              <span className="t-label text-muted block mb-1">Skipped (Dupes)</span>
              <span className="t-body-strong text-muted text-lg">{confirmedResult.duplicates_skipped || 0}</span>
            </div>
            <div className="p-3 bg-white rounded-xl border border-hairline text-center">
              <span className="t-label text-muted block mb-1">Rejected</span>
              <span className="t-body-strong text-rose-700 text-lg">{confirmedResult.rejected_count || 0}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <Button
            id="run-scoring-now-btn"
            variant="primary"
            onClick={() => navigate("/app/matches")}
          >
            <Sparkles className="w-4 h-4 mr-1.5" />
            <span>Run Scoring Now</span>
          </Button>
          <Button
            id="view-records-btn"
            variant="outline"
            onClick={() => navigate(entityType === "lead" ? "/app/leads" : "/app/customers")}
          >
            <Users className="w-4 h-4 mr-1.5 text-muted" />
            <span>View {entityType === "lead" ? "Leads" : "Customers"} Records</span>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 font-sans">
      {/* 1. Validation Counts Grid */}
      <div>
        <h3 className="t-body-strong text-ink mb-3">Validation & Pre-flight Summary</h3>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="p-3.5 bg-canvas rounded-xl border border-hairline text-center">
            <span className="t-label text-muted block mb-1">Total Parsed</span>
            <span className="t-body-strong text-ink text-xl font-mono">{counts.total || 0}</span>
          </div>
          <div className="p-3.5 bg-emerald-500/10 rounded-xl border border-emerald-500/20 text-center">
            <span className="t-label text-emerald-800 block mb-1">Will Be Created</span>
            <span className="t-body-strong text-emerald-700 text-xl font-mono">{counts.will_be_created || 0}</span>
          </div>
          <div className="p-3.5 bg-amber-500/10 rounded-xl border border-amber-500/20 text-center">
            <span className="t-label text-amber-800 block mb-1">Duplicates Skipped</span>
            <span className="t-body-strong text-amber-700 text-xl font-mono">{counts.duplicates || 0}</span>
          </div>
          <div className="p-3.5 bg-rose-500/10 rounded-xl border border-rose-500/20 text-center">
            <span className="t-label text-rose-800 block mb-1">Rejected Rows</span>
            <span className="t-body-strong text-rose-700 text-xl font-mono">{counts.rejected || 0}</span>
          </div>
          <div className="p-3.5 bg-canvas rounded-xl border border-hairline text-center">
            <span className="t-label text-muted block mb-1">Consent Missing</span>
            <span className="t-body-strong text-muted-soft text-xl font-mono">{flags.consent_missing || 0}</span>
          </div>
        </div>
        <p className="t-caption text-muted mt-2 italic">
          * Nothing has been written to the database yet. Review summary and problems below before confirming.
        </p>
      </div>

      {/* 2. Problems Table (First 50 problems) */}
      {problems.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="t-label text-muted-soft flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
              Detected Row Validation Problems ({problems.length})
            </h4>
            <span className="t-caption text-muted">Phones masked for privacy</span>
          </div>
          <div className="border border-hairline rounded-xl overflow-hidden bg-canvas max-h-56 overflow-y-auto">
            <table className="w-full text-left text-xs table-fixed border-collapse">
              <colgroup>
                <col style={{ width: "15%" }} />
                <col style={{ width: "25%" }} />
                <col style={{ width: "60%" }} />
              </colgroup>
              <thead className="bg-surface-card border-b border-hairline text-muted sticky top-0 text-[11px] font-semibold uppercase tracking-wider">
                <tr>
                  <th className="py-2 px-2.5">Row #</th>
                  <th className="py-2 px-2.5">Masked Phone</th>
                  <th className="py-2 px-2.5">Validation Reason(s)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {problems.map((p, idx) => (
                  <tr key={idx} className="hover:bg-surface-card/40">
                    <td className="py-2 px-2.5 font-mono text-ink font-semibold">Row {p.row_number}</td>
                    <td className="py-2 px-2.5 font-mono text-muted">{p.phone || p.phone_masked || "N/A"}</td>
                    <td className="py-2 px-2.5 text-rose-700 text-xs truncate" title={Array.isArray(p.reasons || p.errors) ? (p.reasons || p.errors).join("; ") : String(p.reasons || p.errors)}>
                      {Array.isArray(p.reasons || p.errors)
                        ? (p.reasons || p.errors).join("; ")
                        : String(p.reasons || p.errors)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 3. DPDP Act Attestation Checkbox */}
      <div className="p-4 bg-surface-card rounded-xl border border-hairline space-y-3">
        <div className="flex items-start gap-3">
          <input
            id="dpdp-attestation-check"
            type="checkbox"
            checked={attestConsent}
            onChange={(e) => setAttestConsent(e.target.checked)}
            className="mt-1 h-4 w-4 rounded border-hairline text-indigo-600 focus:ring-indigo-500"
          />
          <label htmlFor="dpdp-attestation-check" className="text-xs text-ink cursor-pointer select-none">
            <strong className="block font-semibold mb-0.5 text-indigo-950">
              DPDP Act Compliance Attestation
            </strong>
            I confirm these records were collected with consent for outreach and I am authorised to upload them (Digital Personal Data Protection Act).
          </label>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between pt-2">
        <Button variant="outline" onClick={onBack} disabled={confirming}>
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          <span>Back to Mapping</span>
        </Button>
        <Button
          id="confirm-import-btn"
          variant="primary"
          onClick={() => onConfirm(attestConsent)}
          disabled={!attestConsent || confirming || counts.will_be_created === 0}
        >
          <ShieldCheck className="w-4 h-4 mr-1.5" />
          <span>{confirming ? "Importing Records..." : `Confirm & Import ${counts.will_be_created || 0} Records`}</span>
        </Button>
      </div>
    </div>
  );
}
