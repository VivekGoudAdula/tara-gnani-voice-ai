import React, { useState, useEffect } from "react";
import { Filter, Users, ShieldAlert, CheckSquare, Square, AlertCircle, Info, Sparkles } from "lucide-react";
import { api } from "../../api/client";
import Card from "../Card";
import Button from "../Button";
import Badge from "../Badge";
import Input from "../Input";
import Modal from "../Modal";

export default function WizardStep2Audience({ campaignId, onAudienceSaved, savedRecipientCount }) {
  const [candidates, setCandidates] = useState([]);
  const [summary, setSummary] = useState({ total: 0, by_band: {}, by_eligibility: {}, selectable: 0, would_be_blocked: 0 });
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [selectedBands, setSelectedBands] = useState(["HIGH", "MEDIUM"]);
  const [eligibilityFilter, setEligibilityFilter] = useState("ELIGIBLE");
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({ total: 0, total_pages: 1 });
  const [includeIneligible, setIncludeIneligible] = useState(false);
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadPreview = async () => {
    if (!campaignId) return;
    setLoading(true);
    try {
      let q = `/campaigns/${campaignId}/audience/preview?page=${page}&page_size=50&eligibility=${eligibilityFilter}`;
      selectedBands.forEach((b) => (q += `&band=${b}`));
      if (minScore) q += `&min_score=${minScore}`;
      if (maxScore) q += `&max_score=${maxScore}`;
      if (search) q += `&search=${encodeURIComponent(search)}`;

      const res = await api.get(q);
      setCandidates(res.candidates || []);
      setSummary(res.summary || { total: 0, by_band: {}, by_eligibility: {}, selectable: 0, would_be_blocked: 0 });
      setPagination({ total: res.total || 0, total_pages: res.total_pages || 1 });

      const initialSelected = new Set(selectedIds);
      (res.candidates || []).forEach((c) => {
        if (c.already_selected) initialSelected.add(c.entity_id);
      });
      setSelectedIds(initialSelected);
    } catch (err) {
      console.error("Failed to load audience preview", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPreview();
  }, [campaignId, page, selectedBands, eligibilityFilter, minScore, maxScore, search]);

  const toggleBand = (band) => {
    setPage(1);
    setSelectedBands((prev) => (prev.includes(band) ? prev.filter((b) => b !== band) : [...prev, band]));
  };

  const handleSelectAllFilter = async () => {
    setSaving(true);
    try {
      const filterPayload = { bands: selectedBands, eligibility: eligibilityFilter };
      if (minScore) filterPayload.min_score = parseFloat(minScore);
      if (maxScore) filterPayload.max_score = parseFloat(maxScore);

      const res = await api.put(`/campaigns/${campaignId}/audience`, {
        mode: "filter", filter: filterPayload, include_not_eligible: includeIneligible, confirm_override: includeIneligible,
      });
      await loadPreview();
      if (onAudienceSaved) onAudienceSaved(res.recipient_count);
    } catch (err) {
      alert(err.message || "Failed to set audience");
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    setSaving(true);
    try {
      await api.put(`/campaigns/${campaignId}/audience`, { mode: "manual", entity_ids: [] });
      setSelectedIds(new Set());
      await loadPreview();
      if (onAudienceSaved) onAudienceSaved(0);
    } catch (err) {
      alert(err.message || "Failed to clear audience");
    } finally {
      setSaving(false);
    }
  };

  const toggleCandidate = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const saveManualSelection = async () => {
    setSaving(true);
    try {
      const res = await api.put(`/campaigns/${campaignId}/audience`, {
        mode: "manual", entity_ids: Array.from(selectedIds), include_not_eligible: includeIneligible, confirm_override: includeIneligible,
      });
      await loadPreview();
      if (onAudienceSaved) onAudienceSaved(res.recipient_count);
    } catch (err) {
      alert(err.message || "Failed to save selected candidates");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Policy Transparency Banner */}
      <div className="flex items-start gap-3 p-3.5 rounded-xl bg-surface-strong/60 border border-hairline t-body-xs text-body">
        <Sparkles className="w-4 h-4 text-primary shrink-0 mt-0.5" />
        <span>
          <strong>Scoring Governance:</strong> Fit score ranks likelihood of interest. Eligibility is decided by policy rules. A human approves every offer.
        </span>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        {[
          { label: "Total Filtered", val: summary.total },
          { label: "High Fit", val: summary.by_band?.HIGH || 0 },
          { label: "Medium Fit", val: summary.by_band?.MEDIUM || 0 },
          { label: "Low Fit", val: summary.by_band?.LOW || 0 },
          { label: "Policy Eligible", val: summary.by_eligibility?.ELIGIBLE || 0 },
          { label: "Not Eligible", val: summary.by_eligibility?.NOT_ELIGIBLE || 0 },
          { label: "Selectable", val: summary.selectable },
          { label: "Would Block", val: summary.would_be_blocked, danger: summary.would_be_blocked > 0 },
        ].map((card, idx) => (
          <div key={idx} className="p-3 bg-surface-card border border-hairline rounded-xl">
            <div className="t-label text-muted text-[11px] truncate">{card.label}</div>
            <div className={`text-xl font-bold font-mono mt-0.5 ${card.danger ? "text-amber-600" : "text-ink"}`}>
              {card.val}
            </div>
          </div>
        ))}
      </div>

      {/* Filter Bar */}
      <Card className="p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="t-label text-muted-soft text-xs mr-1">Fit Band:</span>
            {["HIGH", "MEDIUM", "LOW"].map((b) => (
              <button
                key={b}
                onClick={() => toggleBand(b)}
                className={`px-2.5 py-1 rounded-full t-label text-xs border ${
                  selectedBands.includes(b)
                    ? "bg-primary text-white border-primary"
                    : "bg-surface-strong text-muted hover:text-ink border-hairline"
                }`}
              >
                {b}
              </button>
            ))}

            <span className="t-label text-muted-soft text-xs ml-3 mr-1">Eligibility:</span>
            <select
              value={eligibilityFilter}
              onChange={(e) => {
                setEligibilityFilter(e.target.value);
                setPage(1);
              }}
              className="input-base text-xs py-1 px-2.5 h-8"
            >
              <option value="ELIGIBLE">Eligible Only (Default)</option>
              <option value="ALL">All (Including Ineligible)</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <Input
              type="text"
              placeholder="Search candidate name..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="text-xs h-8 w-48"
            />
          </div>
        </div>

        {/* Selection Action Bar */}
        <div className="flex flex-wrap items-center justify-between pt-3 border-t border-hairline text-sm">
          <div className="flex items-center gap-2">
            <Button variant="primary" size="sm" onClick={handleSelectAllFilter} disabled={saving || summary.total === 0}>
              Select All Matching Filter ({summary.total})
            </Button>
            <Button variant="outline" size="sm" onClick={saveManualSelection} disabled={saving || selectedIds.size === 0}>
              Save Selected ({selectedIds.size})
            </Button>
            <Button variant="text" size="sm" onClick={handleClear} disabled={saving}>
              Clear
            </Button>
          </div>

          {/* Ineligible Override Checkbox */}
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 cursor-pointer text-xs t-label text-muted hover:text-ink">
              <input
                type="checkbox"
                checked={includeIneligible}
                onChange={(e) => {
                  if (e.target.checked) setShowOverrideModal(true);
                  else setIncludeIneligible(false);
                }}
                className="w-4 h-4 rounded text-primary"
              />
              <span>Allow Ineligible Selection Override</span>
            </label>
          </div>
        </div>
      </Card>

      {/* Candidates Table */}
      <Card className="p-0 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-muted t-body-sm">Loading scored audience preview...</div>
        ) : candidates.length === 0 ? (
          <div className="p-8 text-center text-muted t-body-sm">No candidate matches found for current filter.</div>
        ) : (
          <div className="w-full overflow-hidden">
            <table className="w-full text-left border-collapse table-fixed">
              <colgroup>
                <col style={{ width: "6%" }} />
                <col style={{ width: "20%" }} />
                <col style={{ width: "11%" }} />
                <col style={{ width: "18%" }} />
                <col style={{ width: "15%" }} />
                <col style={{ width: "16%" }} />
                <col style={{ width: "14%" }} />
              </colgroup>
              <thead>
                <tr className="border-b border-hairline bg-surface-strong/50 text-muted text-[11px] font-semibold uppercase tracking-wider">
                  <th className="py-2 px-2.5 text-center">Select</th>
                  <th className="py-2 px-2.5">Candidate</th>
                  <th className="py-2 px-2.5">Language</th>
                  <th className="py-2 px-2.5">Fit Score & Band</th>
                  <th className="py-2 px-2.5">Policy Eligibility</th>
                  <th className="py-2 px-2.5">Compliance Status</th>
                  <th className="py-2 px-2.5">Dispatch Prediction</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {candidates.map((c) => {
                  const isChecked = selectedIds.has(c.entity_id);
                  return (
                    <tr key={c.entity_id} className={`hover:bg-surface-strong/30 ${isChecked ? "bg-primary/5" : ""}`}>
                      <td className="py-2 px-2.5 text-center">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleCandidate(c.entity_id)}
                          className="w-4 h-4 rounded text-primary"
                        />
                      </td>
                      <td className="py-2 px-2.5 truncate">
                        <div className="font-semibold text-ink text-xs truncate" title={c.name}>{c.name}</div>
                        <div className="text-[10px] text-muted font-mono">{c.phone_masked}</div>
                      </td>
                      <td className="py-2 px-2.5 uppercase font-mono text-xs text-muted truncate">{c.language}</td>
                      <td className="py-2 px-2.5 truncate">
                        <Badge variant={c.band === "HIGH" ? "success" : c.band === "MEDIUM" ? "info" : "warning"} className="text-[10px] px-1.5 py-0.5">
                          {c.band} ({Math.round(c.match_score)}%)
                        </Badge>
                      </td>
                      <td className="py-2 px-2.5 truncate">
                        <Badge variant={c.eligibility === "ELIGIBLE" ? "success" : "danger"} className="text-[10px] px-1.5 py-0.5">
                          {c.eligibility}
                        </Badge>
                      </td>
                      <td className="py-2 px-2.5 text-[11px] text-muted space-x-1.5 truncate">
                        <span>Cons: {c.consent ? "Yes" : "No"}</span>
                        <span>DND: {c.dnd ? "Yes" : "No"}</span>
                      </td>
                      <td className="py-2 px-2.5 truncate">
                        {c.will_be_blocked_reason ? (
                          <Badge variant="warning" dot={true} className="text-[10px] px-1.5 py-0.5 truncate max-w-[120px]" title={c.will_be_blocked_reason}>
                            {c.will_be_blocked_reason}
                          </Badge>
                        ) : (
                          <Badge variant="success" dot={true} className="text-[10px] px-1.5 py-0.5">
                            Dialable
                          </Badge>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {pagination.total_pages > 1 && (
          <div className="flex items-center justify-between p-3.5 border-t border-hairline t-body-sm text-muted bg-surface-strong/30">
            <span>
              Showing {(page - 1) * 50 + 1} to {Math.min(page * 50, pagination.total)} of {pagination.total} candidates
            </span>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <span className="text-ink font-medium px-2">
                Page {page} of {pagination.total_pages}
              </span>
              <Button variant="outline" size="sm" disabled={page >= pagination.total_pages} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Confirmation Modal for Overriding Eligibility */}
      <Modal
        isOpen={showOverrideModal}
        onClose={() => setShowOverrideModal(false)}
        title="Confirm Ineligible Candidate Override"
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-3.5 bg-amber-50 rounded-xl border border-amber-200 text-amber-900 t-body-sm">
            <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <strong>Regulatory Audit Notice:</strong> Including candidates marked NOT_ELIGIBLE overrides automated policy rules.
              This affirmative action will be permanently recorded in the institutional audit log.
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-3">
            <Button variant="outline" size="sm" onClick={() => setShowOverrideModal(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setIncludeIneligible(true);
                setShowOverrideModal(false);
              }}
            >
              Confirm Override
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
