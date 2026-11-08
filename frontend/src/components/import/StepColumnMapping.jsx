import React, { useEffect } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, AlertTriangle, Info } from "lucide-react";
import Button from "../Button";
import Badge from "../Badge";

const SYNONYMS = {
  name: ["name", "full_name", "fullname", "lead_name", "customer_name"],
  phone: ["phone", "mobile", "msisdn", "phone_number", "contact", "cell"],
  language: ["language", "lang", "pref_lang", "preferred_language"],
  city: ["city", "location", "town"],
  age: ["age", "years"],
  income: ["income", "monthly_income", "salary", "annual_income"],
  segment: ["segment", "tier", "category"],
  source: ["source", "lead_source", "channel"],
  employment_type: ["employment_type", "employment", "job"],
  existing_emi_to_income: ["existing_emi_to_income", "emi_ratio", "dti", "foir"],
  consent: ["consent", "dpdp_consent", "opt_in"],
  dnd: ["dnd", "do_not_disturb"],
  financial_health: ["financial_health", "credit_health", "score"],
  repayment_behaviour: ["repayment_behaviour", "repayment_behavior", "repayment"],
  existing_products: ["existing_products", "products", "active_products"],
  tenure_months: ["tenure_months", "tenure"],
};

export default function StepColumnMapping({
  entityType,
  headers = [],
  sampleRows = [],
  mapping = {},
  setMapping,
  onBack,
  onNext,
  validating,
}) {
  const targetFields = [
    { key: "name", label: "Full Name", required: true },
    { key: "phone", label: "Phone (10-digit / E.164)", required: true },
    { key: "language", label: "Language (Hindi / Telugu / English)", required: false },
    { key: "city", label: "City", required: false },
    { key: "age", label: "Age (18 - 100)", required: false },
    { key: "income", label: "Monthly Income (INR)", required: false },
    { key: "segment", label: "Customer Segment", required: false },
    { key: "source", label: "Acquisition Source", required: false },
    { key: "employment_type", label: "Employment Type", required: false },
    { key: "existing_emi_to_income", label: "Existing EMI to Income (0.0 - 1.0)", required: false },
    { key: "consent", label: "DPDP Consent (true/yes/1)", required: false },
    { key: "dnd", label: "DND Registered Flag", required: false },
    ...(entityType === "customer"
      ? [
          { key: "financial_health", label: "Financial Health Score (0 - 100)", required: false },
          { key: "repayment_behaviour", label: "Repayment Behaviour (GOOD/AVERAGE/POOR)", required: false },
          { key: "existing_products", label: "Existing Products Held (comma separated)", required: false },
          { key: "tenure_months", label: "Tenure in Months", required: false },
        ]
      : []),
  ];

  // Auto-match on initial mount
  useEffect(() => {
    const newMapping = { ...mapping };
    targetFields.forEach((field) => {
      if (!newMapping[field.key]) {
        const syns = SYNONYMS[field.key] || [field.key];
        const match = headers.find((h) => {
          const norm = h.toLowerCase().replace(/[\s_-]+/g, "");
          return syns.some((s) => {
            const cleanS = s.toLowerCase().replace(/[\s_-]+/g, "");
            if (cleanS.length <= 3) return norm === cleanS;
            return norm === cleanS || norm.includes(cleanS);
          });
        });
        if (match) {
          newMapping[field.key] = match;
        }
      }
    });
    setMapping(newMapping);
  }, [headers, entityType]);

  const handleSelectChange = (targetKey, headerName) => {
    setMapping((prev) => {
      const updated = { ...prev };
      if (!headerName) {
        delete updated[targetKey];
      } else {
        updated[targetKey] = headerName;
      }
      return updated;
    });
  };

  const hasName = Boolean(mapping.name);
  const hasPhone = Boolean(mapping.phone);
  const canProceed = hasName && hasPhone;

  return (
    <div className="space-y-6 font-sans">
      <div className="p-3 bg-surface-card rounded-xl border border-hairline t-caption text-body flex items-center gap-2.5 shadow-soft">
        <Info className="w-4 h-4 text-muted shrink-0" />
        <span>
          <strong>Column Mapping Rules: </strong>
          Required fields are <span className="text-ink font-semibold">Name</span> and <span className="text-ink font-semibold">Phone</span>.
          Unmapped CSV columns will be ignored. Missing optional fields will be safely handled and imputed during scoring.
        </span>
      </div>

      {/* Target fields mapping grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 bg-canvas p-4 rounded-2xl border border-hairline">
        {targetFields.map((field) => {
          const selectedCol = mapping[field.key] || "";
          return (
            <div
              key={field.key}
              className={`p-3 rounded-xl border flex flex-col justify-between gap-2 ${
                selectedCol ? "bg-white border-hairline shadow-sm" : "bg-surface-card/60 border-hairline"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="t-body-strong text-ink flex items-center gap-1.5">
                  {field.label}
                  {field.required && <span className="text-rose-600 text-xs">*</span>}
                </span>
                {field.required && (
                  <Badge variant={selectedCol ? "success" : "danger"}>
                    {selectedCol ? "Mapped" : "Required"}
                  </Badge>
                )}
              </div>

              <select
                value={selectedCol}
                onChange={(e) => handleSelectChange(field.key, e.target.value)}
                className="w-full bg-canvas border border-hairline rounded-lg px-2.5 py-1.5 t-caption text-ink"
              >
                <option value="">-- Ignore / Not Mapped --</option>
                {headers.map((h) => (
                  <option key={h} value={h}>
                    CSV Header: "{h}"
                  </option>
                ))}
              </select>
            </div>
          );
        })}
      </div>

      {/* Sample 5 rows preview */}
      {sampleRows.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="t-label text-muted-soft">File Sample Preview (First 5 Rows)</h4>
            <span className="t-caption text-muted">{headers.length} headers detected</span>
          </div>
          <div className="border border-hairline rounded-xl overflow-x-auto bg-canvas">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-card border-b border-hairline text-muted">
                <tr>
                  {headers.map((h) => (
                    <th key={h} className="p-2 font-medium whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {sampleRows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-surface-card/40">
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="p-2 text-ink whitespace-nowrap font-mono text-[11px]">
                        {cell || "-"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!canProceed && (
        <div className="p-3 bg-amber-500/10 border border-amber-500/20 text-amber-900 rounded-xl t-caption flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
          <span>Please map both <strong>Full Name</strong> and <strong>Phone</strong> columns to proceed.</span>
        </div>
      )}

      <div className="flex items-center justify-between pt-2">
        <Button variant="outline" onClick={onBack} disabled={validating}>
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          <span>Back</span>
        </Button>
        <Button
          id="validate-preview-btn"
          variant="primary"
          onClick={onNext}
          disabled={!canProceed || validating}
        >
          <span>{validating ? "Validating Server-Side..." : "Validate & Preview"}</span>
          <ArrowRight className="w-4 h-4 ml-1.5" />
        </Button>
      </div>
    </div>
  );
}
