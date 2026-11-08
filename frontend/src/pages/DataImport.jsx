import React, { useState, useEffect, useCallback } from "react";
import { UploadCloud, RefreshCw } from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Button from "../components/Button";
import OptionCards from "../components/import/OptionCards";
import CsvImportWizard from "../components/import/CsvImportWizard";
import ImportHistoryTable from "../components/import/ImportHistoryTable";

export default function DataImport() {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "SUPER_ADMIN";

  const [wizardOpen, setWizardOpen] = useState(false);
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [error, setError] = useState("");

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    setError("");
    try {
      const res = await api.get("/imports?page=1&page_size=20");
      setHistory(res?.items || []);
    } catch (err) {
      console.error("Failed to load import history:", err);
      setError(err.message || "Failed to load import history.");
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  return (
    <div className="space-y-6 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-hairline">
        <div>
          <h1 className="t-h1 text-ink flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-muted" />
            Data Import & Portfolio Intake
          </h1>
          <p className="t-body text-muted mt-1">
            Ingest customer profiles and leads via compliant CSV upload or synthetic demo datasets.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={loadHistory}
            disabled={loadingHistory}
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loadingHistory ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-600 rounded-xl t-caption">
          {error}
        </div>
      )}

      {/* Top 3 Option Cards */}
      <OptionCards
        isSuperAdmin={isSuperAdmin}
        onStartCsvUpload={() => setWizardOpen(true)}
        onSampleLoaded={loadHistory}
      />

      {/* Interactive CSV Import Wizard Modal / Drawer / Accordion */}
      {wizardOpen && (
        <div className="pt-2">
          <CsvImportWizard
            onClose={() => setWizardOpen(false)}
            onImportSuccess={() => {
              loadHistory();
            }}
          />
        </div>
      )}

      {/* Import History Table */}
      <ImportHistoryTable
        history={history}
        loading={loadingHistory}
        onRefresh={loadHistory}
      />
    </div>
  );
}
