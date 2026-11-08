import React, { useState, useEffect, useCallback } from "react";
import { Package, RefreshCw, Plus, Edit2, AlertTriangle, CheckCircle2 } from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import DataTable from "../components/DataTable";
import Badge from "../components/Badge";
import Button from "../components/Button";
import Modal from "../components/Modal";
import { formatCurrency } from "../utils/format";

const DEFAULT_FORM = {
  name: "", category: "personal_loan", description: "", active: true,
  eligibility_rules: { min_income: 30000, min_age: 21, max_age: 60, max_emi_to_income: 0.5, min_financial_health: 60, allowed_repayment_behaviours: ["GOOD", "AVERAGE"], exclude_if_holds_product: true },
};

export default function Products() {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "SUPER_ADMIN";
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [isStale, setIsStale] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [formData, setFormData] = useState(DEFAULT_FORM);
  const [formSubmitting, setFormSubmitting] = useState(false);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [prodsData, runsData] = await Promise.all([api.get("/products"), api.get("/scoring/runs?page=1&page_size=1")]);
      setProducts(prodsData || []);
      const run = (runsData?.items || [])[0] || null;
      if (run?.finished_at) {
        const runFinished = new Date(run.finished_at).getTime();
        setIsStale((prodsData || []).some((p) => p.updated_at && new Date(p.updated_at).getTime() > runFinished));
      }
    } catch (err) { setError(err.message || "Failed to load product catalogue"); } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const openAddModal = () => { setEditingProduct(null); setFormData(DEFAULT_FORM); setError(""); setModalOpen(true); };
  const openEditModal = (prod) => {
    setEditingProduct(prod);
    const r = prod.eligibility_rules || {};
    setFormData({
      name: prod.name, category: prod.category || "other", description: prod.description || "", active: prod.active ?? true,
      eligibility_rules: { min_income: r.min_income ?? 30000, min_age: r.min_age ?? 21, max_age: r.max_age ?? 60, max_emi_to_income: r.max_emi_to_income ?? 0.5, min_financial_health: r.min_financial_health ?? 60, allowed_repayment_behaviours: r.allowed_repayment_behaviours || ["GOOD", "AVERAGE"], exclude_if_holds_product: r.exclude_if_holds_product ?? true },
    });
    setError(""); setModalOpen(true);
  };

  const handleRuleChange = (field, val) => setFormData((prev) => ({ ...prev, eligibility_rules: { ...prev.eligibility_rules, [field]: val } }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (Number(formData.eligibility_rules.min_age) > Number(formData.eligibility_rules.max_age)) {
      setError("Validation Error: Minimum Age cannot exceed Maximum Age.");
      return;
    }
    setFormSubmitting(true);
    setError("");
    try {
      const res = editingProduct ? await api.put(`/products/${editingProduct.id}`, formData) : await api.post("/products", formData);
      setNotice(res.notice || "Product saved. Rescore to apply rules.");
      setModalOpen(false);
      await fetchProducts();
    } catch (err) { setError(err.message || "Operation failed"); } finally { setFormSubmitting(false); }
  };

  const handleToggleActive = async (prod, e) => {
    e.stopPropagation();
    try {
      const res = await api.patch(`/products/${prod.id}/active`, { active: !prod.active });
      setNotice(res.notice || "Status updated.");
      await fetchProducts();
    } catch (err) { setError(err.message || "Failed toggling status"); }
  };

  const columns = [
    {
      header: "Product Name",
      width: isSuperAdmin ? "30%" : "35%",
      render: (row) => (
        <div className="flex items-center gap-2.5 truncate">
          <div className="w-7 h-7 rounded-full bg-surface-strong border border-hairline flex items-center justify-center shrink-0">
            <Package className="w-3.5 h-3.5 text-muted" />
          </div>
          <div className="truncate">
            <div className="font-semibold text-ink text-xs truncate" title={row.name}>{row.name}</div>
            <div className="text-[10px] text-muted truncate" title={row.description}>{row.description}</div>
          </div>
        </div>
      ),
    },
    {
      header: "Category",
      width: isSuperAdmin ? "18%" : "20%",
      render: (row) => <Badge variant="purple" className="text-[10px] px-1.5 py-0.5">{row.category?.replace("_", " ").toUpperCase()}</Badge>,
    },
    {
      header: "Eligibility Rules",
      width: isSuperAdmin ? "30%" : "32%",
      render: (row) => {
        const r = row.eligibility_rules || {};
        return (
          <div className="text-xs text-body space-y-0.5 truncate">
            <div className="truncate">Min Inc: <span className="font-semibold">{formatCurrency(r.min_income)}</span></div>
            <div className="text-[10px] text-muted truncate">Age: {r.min_age}–{r.max_age} yrs • Max EMI: {(r.max_emi_to_income * 100).toFixed(0)}%</div>
          </div>
        );
      },
    },
    {
      header: "Status",
      width: isSuperAdmin ? "11%" : "13%",
      render: (row) => (
        <button
          onClick={(e) => isSuperAdmin && handleToggleActive(row, e)}
          disabled={!isSuperAdmin}
          className={`${isSuperAdmin ? "cursor-pointer" : "cursor-default"}`}
        >
          <Badge variant={row.active ? "success" : "default"} className="text-[10px] px-1.5 py-0.5">{row.active ? "Active" : "Inactive"}</Badge>
        </button>
      ),
    },
    ...(isSuperAdmin
      ? [
          {
            header: "Action",
            width: "11%",
            className: "text-right",
            render: (row) => (
              <Button size="sm" variant="outline" onClick={() => openEditModal(row)} className="!py-1 !px-2 text-xs">
                <Edit2 className="w-3 h-3 mr-1 text-muted" /> Edit
              </Button>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto font-sans">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-hairline">
        <div>
          <h1 className="t-display-sm font-bold text-ink">Product Catalogue</h1>
          <p className="t-body text-muted mt-1">
            Active financial products and deterministic eligibility policy criteria.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isSuperAdmin && (
            <Button variant="primary" onClick={openAddModal}>
              <Plus className="w-4 h-4 mr-1.5" /> Add Product
            </Button>
          )}
          <Button variant="outline" onClick={fetchProducts} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {isStale && (
        <div className="p-3.5 bg-amber-500/10 border border-amber-500/20 rounded-xl flex items-center gap-3 text-amber-900 t-caption">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>Eligibility rules modified since last run. Go to <strong>Product Matches</strong> and run scoring to apply.</span>
        </div>
      )}

      {notice && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-800 rounded-xl t-caption flex items-center justify-between">
          <div className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-600" /> {notice}</div>
          <button onClick={() => setNotice("")} className="text-emerald-700 font-bold">×</button>
        </div>
      )}

      <DataTable columns={columns} data={products} loading={loading} emptyMessage="No products configured." />

      <Modal isOpen={modalOpen} onClose={() => setModalOpen(false)} title={editingProduct ? "Edit Product" : "Add Product"}>
        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs font-sans">
          <div>
            <label className="font-semibold block mb-1">Product Name</label>
            <input required type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className="w-full bg-canvas border border-hairline p-2 rounded-lg" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-semibold block mb-1">Category</label>
              <select value={formData.category} onChange={(e) => setFormData({ ...formData, category: e.target.value })} className="w-full bg-canvas border border-hairline p-2 rounded-lg">
                <option value="personal_loan">Personal Loan</option>
                <option value="credit_card">Credit Card</option>
                <option value="home_loan">Home Loan</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="font-semibold block mb-1">Active Status</label>
              <select value={formData.active ? "true" : "false"} onChange={(e) => setFormData({ ...formData, active: e.target.value === "true" })} className="w-full bg-canvas border border-hairline p-2 rounded-lg">
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </select>
            </div>
          </div>
          <div>
            <label className="font-semibold block mb-1">Description</label>
            <textarea value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} className="w-full bg-canvas border border-hairline p-2 rounded-lg" rows={2} />
          </div>

          <div className="pt-2 border-t border-hairline">
            <h4 className="font-bold text-ink mb-2">Deterministic Eligibility Rules</h4>
            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <label className="text-muted block mb-0.5">Min Income (₹)</label>
                <input type="number" value={formData.eligibility_rules.min_income || ""} onChange={(e) => handleRuleChange("min_income", Number(e.target.value))} className="w-full bg-canvas border border-hairline p-1.5 rounded-lg" />
              </div>
              <div>
                <label className="text-muted block mb-0.5">Max EMI / Income (0-1)</label>
                <input type="number" step="0.05" min="0" max="1" value={formData.eligibility_rules.max_emi_to_income || ""} onChange={(e) => handleRuleChange("max_emi_to_income", Number(e.target.value))} className="w-full bg-canvas border border-hairline p-1.5 rounded-lg" />
              </div>
              <div>
                <label className="text-muted block mb-0.5">Min Age (Years)</label>
                <input type="number" value={formData.eligibility_rules.min_age || ""} onChange={(e) => handleRuleChange("min_age", Number(e.target.value))} className="w-full bg-canvas border border-hairline p-1.5 rounded-lg" />
              </div>
              <div>
                <label className="text-muted block mb-0.5">Max Age (Years)</label>
                <input type="number" value={formData.eligibility_rules.max_age || ""} onChange={(e) => handleRuleChange("max_age", Number(e.target.value))} className="w-full bg-canvas border border-hairline p-1.5 rounded-lg" />
              </div>
            </div>
          </div>

          {error && <div className="p-2 bg-red-500/10 text-red-600 rounded">{error}</div>}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button variant="primary" type="submit" disabled={formSubmitting}>{formSubmitting ? "Saving..." : "Save Product"}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
