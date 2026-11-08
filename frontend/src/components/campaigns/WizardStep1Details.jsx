import React, { useEffect, useState } from "react";
import { Package, Users, Target } from "lucide-react";
import { api } from "../../api/client";
import Card from "../Card";
import Input from "../Input";

export default function WizardStep1Details({ data, onChange }) {
  const [products, setProducts] = useState([]);
  const [loadingProducts, setLoadingProducts] = useState(true);

  useEffect(() => {
    async function loadProducts() {
      try {
        const res = await api.get("/products?active_only=true");
        setProducts(res.items || res || []);
      } catch (err) {
        console.error("Failed to load products", err);
      } finally {
        setLoadingProducts(false);
      }
    }
    loadProducts();
  }, []);

  return (
    <div className="space-y-6 max-w-3xl">
      <Card className="p-6 space-y-5">
        <h3 className="t-heading-sm text-ink pb-3 border-b border-hairline flex items-center gap-2">
          <Target className="w-5 h-5 text-primary" />
          Campaign Details & Objective
        </h3>

        {/* Campaign Name */}
        <div>
          <label className="block t-label text-body-strong mb-1.5">
            Campaign Name <span className="text-semantic-error">*</span>
          </label>
          <Input
            type="text"
            placeholder="e.g., Q1 Festive Personal Loan Outreach"
            value={data.name || ""}
            onChange={(e) => onChange("name", e.target.value)}
            className="w-full text-base font-medium"
            required
          />
        </div>

        {/* Description */}
        <div>
          <label className="block t-label text-body-strong mb-1.5">Description (Optional)</label>
          <textarea
            rows={2}
            placeholder="Brief internal note regarding audience segment or campaign context..."
            value={data.description || ""}
            onChange={(e) => onChange("description", e.target.value)}
            className="input-base w-full py-2.5 px-3 text-sm resize-none"
          />
        </div>

        {/* Test Run Tag / Label */}
        <div>
          <label className="block t-label text-body-strong mb-1.5 flex items-center justify-between">
            <span>Test Run Tag / Label (Optional)</span>
            <span className="text-[11px] text-muted font-normal">Used for evidence report isolation</span>
          </label>
          <Input
            type="text"
            placeholder="e.g., phase5-evidence"
            value={data.test_run_label || ""}
            onChange={(e) => onChange("test_run_label", e.target.value)}
            className="w-full text-sm font-mono"
            maxLength={60}
          />
        </div>

        {/* Product Selection */}
        <div>
          <label className="block t-label text-body-strong mb-1.5 flex items-center gap-1.5">
            <Package className="w-4 h-4 text-muted" /> Target Product{" "}
            <span className="text-semantic-error">*</span>
          </label>
          {loadingProducts ? (
            <div className="t-body-sm text-muted p-2">Loading active catalogue products...</div>
          ) : (
            <select
              value={data.product_id || ""}
              onChange={(e) => {
                const selectedProd = products.find((p) => p.id === e.target.value);
                onChange("product_id", e.target.value);
                if (selectedProd) onChange("product_name", selectedProd.name);
              }}
              className="input-base w-full text-sm font-medium"
              required
            >
              <option value="">-- Select an active product --</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.code}) - {p.category}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Audience Entity Type */}
        <div>
          <label className="block t-label text-body-strong mb-1.5 flex items-center gap-1.5">
            <Users className="w-4 h-4 text-muted" /> Target Audience Entity
          </label>
          <div className="grid grid-cols-2 gap-4">
            <label
              className={`flex items-center gap-3 p-3.5 rounded-xl border cursor-pointer transition-colors ${
                data.entity_type === "lead"
                  ? "bg-surface-strong/60 border-primary shadow-sm"
                  : "bg-surface-card border-hairline hover:bg-surface-strong/20"
              }`}
            >
              <input
                type="radio"
                name="entity_type"
                value="lead"
                checked={data.entity_type === "lead"}
                onChange={() => onChange("entity_type", "lead")}
                className="w-4 h-4 text-primary"
              />
              <div>
                <div className="font-semibold text-ink text-sm">Leads</div>
                <div className="t-body-xs text-muted">Prospective applicants from acquisition channels</div>
              </div>
            </label>

            <label
              className={`flex items-center gap-3 p-3.5 rounded-xl border cursor-pointer transition-colors ${
                data.entity_type === "customer"
                  ? "bg-surface-strong/60 border-primary shadow-sm"
                  : "bg-surface-card border-hairline hover:bg-surface-strong/20"
              }`}
            >
              <input
                type="radio"
                name="entity_type"
                value="customer"
                checked={data.entity_type === "customer"}
                onChange={() => onChange("entity_type", "customer")}
                className="w-4 h-4 text-primary"
              />
              <div>
                <div className="font-semibold text-ink text-sm">Existing Customers</div>
                <div className="t-body-xs text-muted">Existing bank account holders for cross-sell outreach</div>
              </div>
            </label>
          </div>
        </div>

        {/* Objective */}
        <div>
          <label className="block t-label text-body-strong mb-1.5">
            Campaign Objective <span className="text-semantic-error">*</span>
          </label>
          <Input
            type="text"
            placeholder="e.g., Explain pre-approved festive loan terms and schedule callback"
            value={data.objective || ""}
            onChange={(e) => onChange("objective", e.target.value)}
            className="w-full text-sm"
            required
          />
        </div>
      </Card>
    </div>
  );
}
