import React, { useState, useEffect } from "react";
import { Cpu, ShieldCheck, AlertCircle, BarChart3, Sliders, CheckCircle2 } from "lucide-react";
import { api } from "../api/client";
import Badge from "../components/Badge";
import Card from "../components/Card";

export default function Models() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedEntityType, setSelectedEntityType] = useState("lead");

  useEffect(() => {
    setLoading(true);
    api
      .get("/models")
      .then((data) => setModels(data || []))
      .catch((err) => setError(err.message || "Failed to load model artifacts"))
      .finally(() => setLoading(false));
  }, []);

  const filteredModels = models.filter((m) => m.entity_type === selectedEntityType);

  const formatCategoryName = (cat) => {
    if (cat === "personal_loan") return "Personal Loan Model";
    if (cat === "credit_card") return "Credit Card Model";
    if (cat === "home_loan") return "Home Loan Model";
    return "Generic Baseline Model ('Other')";
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Header */}
      <div className="pb-2 border-b border-hairline">
        <h1 className="t-h1 text-ink flex items-center gap-2">
          <Cpu className="w-5 h-5 text-muted" />
          Model Governance & Algorithmic Cards
        </h1>
        <p className="t-body text-muted mt-1">
          Auditable model artifacts, standardized feature weights, Platt calibration tables, and fairness exclusions.
        </p>
      </div>

      {/* Prominent Synthetic Data Pipeline Banner */}
      <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-2xl flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-indigo-600 shrink-0 mt-0.5" />
        <div className="text-xs text-indigo-950">
          <span className="font-semibold block text-sm mb-0.5">
            Trained on synthetic data. Demo pipeline; production requires retraining on the bank's own conversion history.
          </span>
          All propensity weights shown below are trained offline from synthetic demographic functions. Models rank customer conversion likelihood and never decide credit underwriting or policy eligibility.
        </div>
      </div>

      {/* Entity Selector Tabs */}
      <div className="flex items-center justify-between">
        <div className="inline-flex p-1 bg-surface-card rounded-full border border-hairline shadow-soft">
          <button
            onClick={() => setSelectedEntityType("lead")}
            className={`px-5 py-1.5 rounded-full t-body-strong transition-all ${
              selectedEntityType === "lead"
                ? "bg-ink text-canvas shadow-sm"
                : "text-muted hover:text-ink"
            }`}
          >
            Lead Models (4)
          </button>
          <button
            onClick={() => setSelectedEntityType("customer")}
            className={`px-5 py-1.5 rounded-full t-body-strong transition-all ${
              selectedEntityType === "customer"
                ? "bg-ink text-canvas shadow-sm"
                : "text-muted hover:text-ink"
            }`}
          >
            Customer Models (4)
          </button>
        </div>

        <span className="t-caption text-muted">
          Runtime Engine: Pure Python / Zero External ML Dependencies
        </span>
      </div>

      {loading && (
        <div className="p-12 text-center text-muted t-body bg-surface-card rounded-2xl border border-hairline">
          Loading model artifacts and calibration curves...
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-600 rounded-xl t-caption">
          {error}
        </div>
      )}

      {/* Models Grid */}
      {!loading && !error && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {filteredModels.map((model) => (
            <Card key={model.model_id} className="p-6 bg-surface-card border-hairline space-y-6">
              {/* Card Header */}
              <div className="flex items-start justify-between border-b border-hairline pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="t-h2 text-ink">{formatCategoryName(model.category)}</h2>
                    <Badge variant="purple">{model.entity_type.toUpperCase()}</Badge>
                  </div>
                  <div className="t-caption text-muted mt-1 font-mono">
                    ID: {model.model_id} • v{model.version.slice(0, 8)}
                  </div>
                </div>
                <div className="text-right t-caption text-muted">
                  <span>Trained: {model.trained_at ? new Date(model.trained_at).toLocaleDateString() : "Offline"}</span>
                </div>
              </div>

              {/* Holdout Metrics Grid */}
              <div>
                <h3 className="t-label text-muted-soft mb-2">Holdout Test Performance (20% Split)</h3>
                <div className="grid grid-cols-3 gap-3 bg-canvas p-3.5 rounded-xl border border-hairline">
                  <div>
                    <span className="t-label text-muted block mb-1">AUC-ROC</span>
                    <span className="t-body-strong text-indigo-600 block">
                      {model.metrics.auc ? model.metrics.auc.toFixed(3) : "N/A"}
                    </span>
                  </div>
                  <div>
                    <span className="t-label text-muted block mb-1">Brier Score</span>
                    <span className="t-body-strong text-ink block">
                      {model.metrics.brier_score ? model.metrics.brier_score.toFixed(3) : "N/A"}
                    </span>
                  </div>
                  <div>
                    <span className="t-label text-muted block mb-1">Base Rate</span>
                    <span className="t-body-strong text-muted block">
                      {model.metrics.base_rate ? `${(model.metrics.base_rate * 100).toFixed(1)}%` : "N/A"}
                    </span>
                  </div>
                </div>
                <p className="t-caption text-muted-soft mt-1.5 italic">
                  "{model.metrics.notice || "Synthetic data. Metrics demonstrate pipeline, not real-world performance."}"
                </p>
              </div>

              {/* Global Feature Importance (Normalized to 100%) */}
              <div>
                <h3 className="t-label text-muted-soft mb-2">
                  Feature Importance & Direction (Normalized Abs Standardized Coefs)
                </h3>
                <div className="space-y-2 bg-canvas p-3.5 rounded-xl border border-hairline">
                  {(model.global_feature_importance || []).map((feat, idx) => (
                    <div key={idx} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-medium text-ink font-mono">{feat.feature}</span>
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-1.5 py-0.2 rounded text-[10px] font-semibold ${
                              feat.direction === "positive"
                                ? "bg-emerald-500/10 text-emerald-700"
                                : "bg-rose-500/10 text-rose-700"
                            }`}
                          >
                            {feat.direction === "positive" ? "+ Effect" : "- Effect"}
                          </span>
                          <span className="text-muted t-caption font-mono">
                            {feat.importance_percent.toFixed(1)}% (coef: {feat.coefficient.toFixed(3)})
                          </span>
                        </div>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-surface-strong overflow-hidden">
                        <div
                          className="h-full bg-ink/70 rounded-full"
                          style={{ width: `${Math.min(feat.importance_percent, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Excluded Protected Features (Fairness by Design) */}
              <div>
                <h3 className="t-label text-muted-soft mb-2">Exclusions & Fairness Safeguards</h3>
                <div className="border border-hairline rounded-xl overflow-hidden divide-y divide-hairline bg-canvas">
                  {(model.excluded_features || []).map((exc, idx) => (
                    <div key={idx} className="p-2.5 flex items-start justify-between text-xs gap-3">
                      <span className="font-mono font-medium text-rose-800 bg-rose-500/10 px-1.5 py-0.5 rounded shrink-0">
                        {exc.feature}
                      </span>
                      <span className="text-muted text-right">{exc.reason}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Platt Calibration Table (10 Bins) */}
              {model.calibration?.bins && (
                <div>
                  <h3 className="t-label text-muted-soft mb-2">Calibration Reliability (10 Deciles)</h3>
                  <div className="border border-hairline rounded-xl overflow-hidden bg-canvas">
                    <table className="w-full text-left text-xs table-fixed border-collapse">
                      <colgroup>
                        <col style={{ width: "25%" }} />
                        <col style={{ width: "25%" }} />
                        <col style={{ width: "25%" }} />
                        <col style={{ width: "25%" }} />
                      </colgroup>
                      <thead className="bg-surface-card border-b border-hairline t-caption text-muted">
                        <tr>
                          <th className="p-2">Decile Bin</th>
                          <th className="p-2">Pred Mean</th>
                          <th className="p-2">Empirical Rate</th>
                          <th className="p-2 text-right">Count</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-hairline font-mono">
                        {model.calibration.bins.slice(0, 5).map((b, idx) => (
                          <tr key={idx} className="hover:bg-surface-card/30">
                            <td className="p-2 text-ink">{b.bin}</td>
                            <td className="p-2 text-muted">{(b.predicted_mean * 100).toFixed(1)}%</td>
                            <td className="p-2 text-muted">{(b.actual_rate * 100).toFixed(1)}%</td>
                            <td className="p-2 text-right text-muted">{b.count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
