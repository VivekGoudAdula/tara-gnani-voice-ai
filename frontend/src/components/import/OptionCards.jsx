import React, { useState } from "react";
import { UploadCloud, Database, Sparkles, AlertCircle, CheckCircle2 } from "lucide-react";
import { api } from "../../api/client";
import Button from "../Button";
import Badge from "../Badge";

export default function OptionCards({ isSuperAdmin, onStartCsvUpload, onSampleLoaded }) {
  const [loadingSample, setLoadingSample] = useState(false);
  const [sampleMessage, setSampleMessage] = useState(null);

  const handleLoadSample = async () => {
    if (!isSuperAdmin) return;
    setLoadingSample(true);
    setSampleMessage(null);

    try {
      const res = await api.post("/workspace/sample-data", {});
      setSampleMessage({
        type: "success",
        text: `Sample data loaded successfully (${res.leads_count || 12} leads, ${res.customers_count || 12} customers).`,
      });
      if (onSampleLoaded) onSampleLoaded();
    } catch (err) {
      const msg = err.message || "";
      if (msg.includes("already loaded") || msg.includes("already exist") || msg.includes("409")) {
        setSampleMessage({
          type: "info",
          text: "Sample dataset has already been loaded for this workspace.",
        });
      } else {
        setSampleMessage({
          type: "error",
          text: msg || "Failed to load sample dataset.",
        });
      }
    } finally {
      setLoadingSample(false);
    }
  };

  return (
    <div className="space-y-3 font-sans">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card A: Upload CSV */}
        <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft flex flex-col justify-between hover:border-indigo-200 transition-colors">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-700">
                <UploadCloud className="w-5 h-5" />
              </div>
              <Badge variant="purple">Primary Method</Badge>
            </div>
            <h3 className="t-h2 text-ink">Upload CSV File</h3>
            <p className="t-caption text-muted mt-1 leading-snug">
              Import leads or customer portfolios from CSV. Automatic synonym header mapping, E.164 normalization, and DPDP compliance validation.
            </p>
          </div>
          <div className="pt-4 mt-4 border-t border-hairline">
            <Button
              id="start-csv-btn"
              variant="primary"
              className="w-full justify-center"
              onClick={onStartCsvUpload}
            >
              Start CSV Import Wizard
            </Button>
          </div>
        </div>

        {/* Card B: Load Sample Data */}
        <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-700">
                <Sparkles className="w-5 h-5" />
              </div>
              <Badge variant={isSuperAdmin ? "success" : "default"}>
                {isSuperAdmin ? "Admin Only" : "Super Admin Required"}
              </Badge>
            </div>
            <h3 className="t-h2 text-ink">Load Sample Dataset</h3>
            <p className="t-caption text-muted mt-1 leading-snug">
              Populate workspace with a realistic synthetic portfolio of 12 Indian retail leads and 12 bank customers with risk attributes and policy rules.
            </p>
          </div>
          <div className="pt-4 mt-4 border-t border-hairline">
            <Button
              id="load-sample-btn"
              variant="outline"
              className="w-full justify-center"
              onClick={handleLoadSample}
              disabled={!isSuperAdmin || loadingSample}
              title={!isSuperAdmin ? "Only SUPER_ADMIN can load sample data" : ""}
            >
              {loadingSample ? "Loading Data..." : "Load Sample Data"}
            </Button>
          </div>
        </div>

        {/* Card C: Connect Database (Disabled) */}
        <div className="bg-surface-card/60 rounded-2xl border border-hairline/80 p-5 shadow-soft flex flex-col justify-between opacity-80">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 rounded-xl bg-surface-strong text-muted">
                <Database className="w-5 h-5" />
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-surface-strong text-muted-soft">
                Upcoming
              </span>
            </div>
            <h3 className="t-h2 text-muted">Connect a Database</h3>
            <p className="t-caption text-muted-soft mt-1 leading-snug">
              Coming soon: PostgreSQL, MySQL, MongoDB, bank Core Banking & Loan Origination APIs.
            </p>
          </div>
          <div className="pt-4 mt-4 border-t border-hairline/80">
            <button
              disabled
              className="w-full py-2 px-3 rounded-lg bg-surface-strong text-muted text-xs font-medium cursor-not-allowed text-center"
            >
              Direct Integration (Disabled)
            </button>
          </div>
        </div>
      </div>

      {sampleMessage && (
        <div
          className={`p-3.5 rounded-xl border flex items-center gap-2.5 text-xs ${
            sampleMessage.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-800"
              : sampleMessage.type === "info"
              ? "bg-indigo-500/10 border-indigo-500/20 text-indigo-800"
              : "bg-red-500/10 border-red-500/20 text-red-700"
          }`}
        >
          {sampleMessage.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0" />
          )}
          <span>{sampleMessage.text}</span>
        </div>
      )}
    </div>
  );
}
