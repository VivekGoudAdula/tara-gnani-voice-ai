import React, { useState } from "react";
import { X, Check } from "lucide-react";
import { api } from "../../api/client";
import StepTypeAndUpload from "./StepTypeAndUpload";
import StepColumnMapping from "./StepColumnMapping";
import StepPreviewAndConfirm from "./StepPreviewAndConfirm";

export default function CsvImportWizard({ onClose, onImportSuccess }) {
  const [step, setStep] = useState(1); // 1: Upload, 2: Mapping, 3: Preview & Confirm
  const [entityType, setEntityType] = useState("lead");
  const [file, setFile] = useState(null);
  const [parsedHeaders, setParsedHeaders] = useState([]);
  const [sampleRows, setSampleRows] = useState([]);
  const [mapping, setMapping] = useState({});

  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmedResult, setConfirmedResult] = useState(null);
  const [error, setError] = useState("");

  const handleValidate = async () => {
    if (!file) return;
    setValidating(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("entity_type", entityType);
      formData.append("column_mapping", JSON.stringify(mapping));

      const res = await api.post("/imports/validate", formData);
      setValidationResult(res);
      setStep(3);
    } catch (err) {
      setError(err.message || "Validation failed.");
    } finally {
      setValidating(false);
    }
  };

  const handleConfirm = async (attestConsent) => {
    if (!validationResult?.batch_id) return;
    setConfirming(true);
    setError("");

    try {
      const res = await api.post(`/imports/${validationResult.batch_id}/confirm`, {
        attest_consent: attestConsent,
      });
      setConfirmedResult(res);
      if (onImportSuccess) onImportSuccess();
    } catch (err) {
      setError(err.message || "Failed to confirm import.");
    } finally {
      setConfirming(false);
    }
  };

  const stepsList = [
    { num: 1, label: "Type & Upload" },
    { num: 2, label: "Column Mapping" },
    { num: 3, label: "Validate & Confirm" },
  ];

  return (
    <div className="bg-surface-card rounded-2xl border border-hairline p-6 shadow-soft space-y-6 font-sans">
      {/* Wizard Header & Stepper */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-hairline">
        <div>
          <h2 className="t-h2 text-ink">CSV Data Import Wizard</h2>
          <p className="t-caption text-muted mt-0.5">
            5-step workflow with schema validation, deduplication, and consent attestation
          </p>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-surface-strong text-muted hover:text-ink self-start sm:self-center transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Stepper Pill Indicators */}
      <div className="flex items-center justify-center gap-2 sm:gap-6 py-2">
        {stepsList.map((s, idx) => {
          const isDone = step > s.num || (step === 3 && confirmedResult);
          const isCurrent = step === s.num && !confirmedResult;
          return (
            <div key={s.num} className="flex items-center gap-2">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-all ${
                  isDone
                    ? "bg-emerald-600 text-white"
                    : isCurrent
                    ? "bg-ink text-canvas ring-4 ring-ink/10"
                    : "bg-surface-strong text-muted"
                }`}
              >
                {isDone ? <Check className="w-4 h-4" /> : s.num}
              </div>
              <span
                className={`text-xs font-medium hidden sm:inline ${
                  isCurrent ? "text-ink" : "text-muted"
                }`}
              >
                {s.label}
              </span>
              {idx < stepsList.length - 1 && (
                <div className="w-8 sm:w-12 h-[1px] bg-hairline mx-1" />
              )}
            </div>
          );
        })}
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-700 text-xs">
          {error}
        </div>
      )}

      {/* Step Views */}
      {step === 1 && (
        <StepTypeAndUpload
          entityType={entityType}
          setEntityType={setEntityType}
          file={file}
          setFile={setFile}
          parsedHeaders={parsedHeaders}
          setParsedHeaders={setParsedHeaders}
          sampleRows={sampleRows}
          setSampleRows={setSampleRows}
          onNext={() => setStep(2)}
        />
      )}

      {step === 2 && (
        <StepColumnMapping
          entityType={entityType}
          headers={parsedHeaders}
          sampleRows={sampleRows}
          mapping={mapping}
          setMapping={setMapping}
          onBack={() => setStep(1)}
          onNext={handleValidate}
          validating={validating}
        />
      )}

      {step === 3 && (
        <StepPreviewAndConfirm
          entityType={entityType}
          validationResult={validationResult}
          onConfirm={handleConfirm}
          confirming={confirming}
          confirmedResult={confirmedResult}
          onBack={() => setStep(2)}
        />
      )}
    </div>
  );
}
