import React, { useState } from "react";
import { FileText, Download, FileSpreadsheet, ShieldAlert } from "lucide-react";
import Card from "../Card";
import Button from "../Button";
import Input from "../Input";
import { useAuth } from "../../auth/AuthContext";

export default function EvidencePanel({ currentTestRunLabel, onSelectLabel }) {
  const { user } = useAuth();
  const [testRunLabel, setTestRunLabel] = useState(currentTestRunLabel || "");
  const [downloading, setDownloading] = useState(false);

  // Evidence panel is restricted to SUPER_ADMIN
  if (user?.role !== "SUPER_ADMIN") {
    return null;
  }

  const triggerDownload = async (endpoint, filename, mediaType) => {
    setDownloading(true);
    try {
      const token = sessionStorage.getItem("tara_token") || localStorage.getItem("tara_token");
      const res = await fetch(`/api${endpoint}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Export failed with status ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.message || "Failed to download export file");
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadReport = () => {
    const label = (testRunLabel || currentTestRunLabel || "").trim();
    if (!label) {
      alert("Please enter or select a test run tag (e.g. phase5-evidence) to generate an evidence report.");
      return;
    }
    triggerDownload(
      `/outcomes/evidence-report?test_run_label=${encodeURIComponent(label)}`,
      `evidence_report_${label.replace(/\s+/g, "_")}.md`,
      "text/markdown"
    );
  };

  const handleExportCsv = () => {
    const label = (testRunLabel || currentTestRunLabel || "").trim();
    const q = label ? `?format=csv&test_run_label=${encodeURIComponent(label)}` : "?format=csv";
    triggerDownload(`/outcomes/export${q}`, "outcomes_export.csv", "text/csv");
  };

  const handleExportJson = () => {
    const label = (testRunLabel || currentTestRunLabel || "").trim();
    const q = label ? `?format=json&test_run_label=${encodeURIComponent(label)}` : "?format=json";
    triggerDownload(`/outcomes/export${q}`, "outcomes_export.json", "application/json");
  };

  return (
    <Card className="p-4 bg-surface-card border-hairline space-y-3">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-hairline">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-primary" />
          <h3 className="t-heading-xs text-ink">Evidence Report & Raw Audit Export</h3>
          <span className="t-body-xs font-mono text-muted bg-surface-strong px-2 py-0.5 rounded">
            SUPER_ADMIN
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Input
            type="text"
            placeholder="Target test run tag (e.g. phase5-evidence)..."
            value={testRunLabel}
            onChange={(e) => {
              setTestRunLabel(e.target.value);
              if (onSelectLabel) onSelectLabel(e.target.value);
            }}
            className="text-xs py-1 px-2.5 h-8 w-56 font-mono"
          />
        </div>
      </div>

      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Actions Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={handleDownloadReport}
            disabled={downloading}
            className="text-xs"
          >
            <Download className="w-3.5 h-3.5 mr-1.5" /> Download Report (.md)
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportCsv}
            disabled={downloading}
            className="text-xs"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 mr-1.5" /> Export CSV
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportJson}
            disabled={downloading}
            className="text-xs font-mono"
          >
            Export JSON
          </Button>
        </div>

        {/* Limitations Notice */}
        <div className="flex items-start gap-2 max-w-xl p-2.5 rounded-lg bg-surface-strong/40 border border-hairline t-body-xs text-muted">
          <ShieldAlert className="w-4 h-4 text-muted-soft shrink-0 mt-0.5" />
          <p className="text-[11px] leading-relaxed">
            <strong className="text-ink">Limitations:</strong> These are test calls to verified testers following scripts.
            They measure pipeline reliability, latency and extraction behaviour. They do not measure real-world conversion.
            Scoring models are trained on synthetic data.
          </p>
        </div>
      </div>
    </Card>
  );
}
