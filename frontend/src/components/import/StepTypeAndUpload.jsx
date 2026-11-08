import React, { useRef, useState } from "react";
import { Download, UploadCloud, FileText, AlertCircle, ArrowRight } from "lucide-react";
import { api } from "../../api/client";
import Button from "../Button";
import Badge from "../Badge";

export default function StepTypeAndUpload({
  entityType,
  setEntityType,
  file,
  setFile,
  parsedHeaders,
  setParsedHeaders,
  sampleRows,
  setSampleRows,
  onNext,
}) {
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState("");
  const [downloadingTemplate, setDownloadingTemplate] = useState(false);
  const fileInputRef = useRef(null);

  const downloadTemplate = async () => {
    setDownloadingTemplate(true);
    try {
      const blob = await api.get(`/imports/template?entity_type=${entityType}`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `template_${entityType}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || "Failed to download template CSV.");
    } finally {
      setDownloadingTemplate(false);
    }
  };

  const processFile = (selectedFile) => {
    setError("");
    if (!selectedFile) return;

    if (!selectedFile.name.toLowerCase().endsWith(".csv")) {
      setError("Only .csv files are supported. Please select a comma-separated CSV file.");
      return;
    }

    if (selectedFile.size > 5 * 1024 * 1024) {
      setError("File size exceeds 5 MB limit. Please select a smaller file.");
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target.result;
        const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
        if (lines.length < 2) {
          setError("CSV file must contain a header row and at least one data row.");
          return;
        }
        if (lines.length > 5001) {
          setError(`File contains ${lines.length - 1} rows, exceeding the 5,000 row maximum limit.`);
          return;
        }

        const headers = lines[0].split(",").map((h) => h.trim().replace(/^["']|["']$/g, ""));
        const sample = lines.slice(1, 6).map((line) => {
          return line.split(",").map((c) => c.trim().replace(/^["']|["']$/g, ""));
        });

        setFile(selectedFile);
        setParsedHeaders(headers);
        setSampleRows(sample);
      } catch (err) {
        setError("Failed to parse CSV file. Ensure it is UTF-8 encoded.");
      }
    };
    reader.onerror = () => setError("Error reading file. Ensure it is UTF-8 encoded.");
    reader.readAsText(selectedFile, "UTF-8");
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="space-y-6 font-sans">
      {/* 1. Entity Type Selection */}
      <div className="space-y-3">
        <label className="t-body-strong text-ink block">1. Select Target Entity Type</label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div
            onClick={() => { setEntityType("lead"); setFile(null); }}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              entityType === "lead"
                ? "bg-white border-indigo-600 ring-2 ring-indigo-500/20 shadow-sm"
                : "bg-canvas border-hairline hover:bg-surface-card"
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="t-body-strong text-ink">Leads Portfolio</span>
              {entityType === "lead" && <Badge variant="purple">Selected</Badge>}
            </div>
            <p className="t-caption text-muted">
              Prospective customers with consent. Evaluated for eligibility and initial acquisition propensity.
            </p>
          </div>

          <div
            onClick={() => { setEntityType("customer"); setFile(null); }}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              entityType === "customer"
                ? "bg-white border-indigo-600 ring-2 ring-indigo-500/20 shadow-sm"
                : "bg-canvas border-hairline hover:bg-surface-card"
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="t-body-strong text-ink">Existing Customers</span>
              {entityType === "customer" && <Badge variant="purple">Selected</Badge>}
            </div>
            <p className="t-caption text-muted">
              Current account/loan holders. Includes tenure, financial health, and repayment behavior for cross-sell.
            </p>
          </div>
        </div>

        {/* Template Download & Field requirements */}
        <div className="p-3 bg-canvas rounded-xl border border-hairline flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div>
            <span className="font-semibold text-ink">Required: </span>
            <span className="text-muted">name, phone. </span>
            <span className="font-semibold text-ink ml-2">Optional: </span>
            <span className="text-muted">
              language, city, age, income, segment, consent, dnd
              {entityType === "customer" ? ", financial_health, repayment_behaviour, tenure_months" : ""}.
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={downloadTemplate}
            disabled={downloadingTemplate}
            className="shrink-0"
          >
            <Download className="w-3.5 h-3.5 mr-1 text-muted" />
            <span>{downloadingTemplate ? "Downloading..." : "Download Template CSV"}</span>
          </Button>
        </div>
      </div>

      {/* 2. Drag and drop file upload */}
      <div className="space-y-3">
        <label className="t-body-strong text-ink block">2. Upload CSV File</label>
        <div
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`p-8 border-2 border-dashed rounded-2xl text-center cursor-pointer transition-colors ${
            dragActive
              ? "border-indigo-600 bg-indigo-50/50"
              : file
              ? "border-emerald-500/50 bg-emerald-50/20"
              : "border-hairline hover:border-indigo-300 bg-canvas"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={(e) => processFile(e.target.files[0])}
            className="hidden"
          />
          <div className="flex flex-col items-center justify-center space-y-2">
            <div className="p-3 rounded-xl bg-surface-card border border-hairline text-muted">
              {file ? <FileText className="w-6 h-6 text-emerald-600" /> : <UploadCloud className="w-6 h-6 text-indigo-600" />}
            </div>
            {file ? (
              <div>
                <p className="t-body-strong text-ink">{file.name}</p>
                <p className="t-caption text-muted mt-0.5">
                  {(file.size / 1024).toFixed(1)} KB • {sampleRows.length > 0 ? "Ready for mapping" : ""}
                </p>
              </div>
            ) : (
              <div>
                <p className="t-body-strong text-ink">Click or drag & drop CSV file</p>
                <p className="t-caption text-muted mt-0.5">
                  Strictly UTF-8 encoded, max 5 MB and up to 5,000 rows
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-700 flex items-center gap-2 t-caption">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="flex justify-end pt-2">
        <Button
          id="continue-to-mapping-btn"
          variant="primary"
          onClick={onNext}
          disabled={!file || parsedHeaders.length === 0}
        >
          <span>Continue to Column Mapping</span>
          <ArrowRight className="w-4 h-4 ml-1.5" />
        </Button>
      </div>
    </div>
  );
}
