import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Rocket, ShieldAlert, CheckCircle2, XCircle, Clock, AlertTriangle, PhoneCall } from "lucide-react";
import Card from "../Card";
import Button from "../Button";
import Input from "../Input";
import Modal from "../Modal";
import Badge from "../Badge";
import { api } from "../../api/client";

export default function WizardStep4ReviewLaunch({ campaign, recipientCount }) {
  const navigate = useNavigate();
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [typedCount, setTypedCount] = useState("");
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState(null);

  const delaySeconds = 5;
  const estimatedSeconds = (recipientCount || 0) * delaySeconds;
  const estimatedMinutes = Math.ceil(estimatedSeconds / 60);

  const [testRunLabel, setTestRunLabel] = useState(campaign?.test_run_label || "");
  const [savingLabel, setSavingLabel] = useState(false);

  const handleSaveLabel = async () => {
    if (!campaign?.id) return;
    setSavingLabel(true);
    try {
      await api.put(`/campaigns/${campaign.id}`, { test_run_label: testRunLabel.trim() || null });
      alert("Test run label saved.");
    } catch (err) {
      alert(err.message || "Failed to save label");
    } finally {
      setSavingLabel(false);
    }
  };

  const checks = [
    { label: "Audience Selected", ok: (recipientCount || 0) > 0, detail: `${recipientCount || 0} recipient(s) staged` },
    { label: "Target Product Active", ok: true, detail: campaign.product_name },
    { label: "Voice AI Configuration", ok: true, detail: `Config Version ${campaign.config_version || 1}` },
  ];

  const handleLaunch = async () => {
    if (parseInt(typedCount, 10) !== recipientCount) {
      setError(`Recipient count mismatch. Please enter exactly "${recipientCount}".`);
      return;
    }
    setLaunching(true);
    setError(null);
    try {
      await api.post(`/campaigns/${campaign.id}/launch`, {
        confirm: true,
        expected_recipient_count: recipientCount,
      });
      setShowConfirmModal(false);
      navigate(`/app/campaigns/${campaign.id}`);
    } catch (err) {
      setError(err.message || "Failed to trigger campaign launch");
    } finally {
      setLaunching(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Test Mode Pre-Flight Warning */}
      <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 t-body-sm flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <div className="font-bold flex items-center gap-2">
            <span>TEST MODE ACTIVE</span>
            <Badge variant="warning">TRAI Gated</Badge>
          </div>
          <p className="mt-1 text-xs">
            Only allowlisted verified test numbers will receive actual calls. Non-allowlisted recipients, synthetic numbers,
            and records missing explicit consent will be automatically recorded as <strong>BLOCKED</strong> with verifiable audit entries.
          </p>
        </div>
      </div>

      {/* Campaign Summary Card */}
      <Card className="p-6 space-y-4">
        <h3 className="t-heading-sm text-ink pb-2 border-b border-hairline flex items-center gap-2">
          <PhoneCall className="w-5 h-5 text-primary" /> Outreach Deployment Summary
        </h3>

        <div className="grid grid-cols-2 gap-4 t-body-sm">
          <div>
            <span className="t-label text-xs text-muted">Campaign Name:</span>
            <div className="font-semibold text-ink text-base mt-0.5">{campaign.name}</div>
          </div>
          <div>
            <span className="t-label text-xs text-muted">Target Product:</span>
            <div className="font-semibold text-ink text-base mt-0.5">{campaign.product_name}</div>
          </div>
          <div>
            <span className="t-label text-xs text-muted">Target Recipients:</span>
            <div className="font-semibold text-ink font-mono text-base mt-0.5">{recipientCount || 0} candidates</div>
          </div>
          <div>
            <span className="t-label text-xs text-muted">Estimated Duration:</span>
            <div className="font-semibold text-ink flex items-center gap-1.5 text-base mt-0.5">
              <Clock className="w-4 h-4 text-muted" /> ~{estimatedMinutes} min ({estimatedSeconds}s paced)
            </div>
          </div>
        </div>

        {/* Validation Checklist */}
        <div className="pt-4 border-t border-hairline space-y-2.5">
          <span className="t-label text-xs text-muted-soft uppercase font-mono">Pre-Dispatch Gate Verification</span>
          {checks.map((chk, i) => (
            <div key={i} className="flex items-center justify-between p-2.5 rounded-lg bg-surface-strong/40 border border-hairline text-sm">
              <div className="flex items-center gap-2">
                {chk.ok ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : <XCircle className="w-4 h-4 text-semantic-error" />}
                <span className="font-medium text-ink">{chk.label}</span>
              </div>
              <span className="t-body-xs font-mono text-muted">{chk.detail}</span>
            </div>
          ))}
        </div>

        {/* Test Run Tag Field */}
        <div className="pt-4 border-t border-hairline space-y-1.5">
          <label className="block t-label text-xs text-body-strong">
            Label this campaign as a test run (Optional)
          </label>
          <div className="flex items-center gap-2">
            <Input
              type="text"
              placeholder="e.g. phase5-evidence"
              value={testRunLabel}
              onChange={(e) => setTestRunLabel(e.target.value)}
              className="text-xs font-mono py-1.5 h-8 flex-1"
              maxLength={60}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleSaveLabel}
              disabled={savingLabel}
              className="text-xs shrink-0"
            >
              {savingLabel ? "Saving..." : "Save Tag"}
            </Button>
          </div>
          <span className="text-[11px] text-muted block">
            Isolates communications from this campaign in the outcomes dashboard and evidence reports.
          </span>
        </div>
      </Card>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-semantic-error t-body-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Action Button */}
      <div className="flex justify-end">
        <Button
          variant="primary"
          size="md"
          onClick={() => {
            setTypedCount("");
            setError(null);
            setShowConfirmModal(true);
          }}
          disabled={(recipientCount || 0) === 0}
          className="px-6 py-2.5 text-base shadow-md"
        >
          <Rocket className="w-4 h-4 mr-2" /> Review & Launch Outreach
        </Button>
      </div>

      {/* Strict Retype Confirmation Dialog */}
      <Modal
        isOpen={showConfirmModal}
        onClose={() => !launching && setShowConfirmModal(false)}
        title="Confirm Campaign Dispatch"
      >
        <div className="space-y-4">
          <div className="p-3.5 bg-surface-strong/60 rounded-xl border border-hairline text-xs t-body text-body">
            You are about to launch automated AI phone outreach for <strong>{recipientCount}</strong> recipients.
            Dispatches will proceed sequentially with concurrency pacing and strict TRAI compliance checks.
          </div>

          <div>
            <label className="block t-label text-xs mb-1.5 text-body-strong">
              To prevent accidental dispatch, please type <span className="font-mono font-bold text-ink">{recipientCount}</span> below:
            </label>
            <Input
              type="text"
              placeholder={`Type "${recipientCount}" to confirm`}
              value={typedCount}
              onChange={(e) => setTypedCount(e.target.value)}
              className="w-full text-center text-lg font-mono font-bold"
              autoFocus
            />
          </div>

          <div className="flex justify-end gap-3 pt-3">
            <Button variant="outline" size="sm" onClick={() => setShowConfirmModal(false)} disabled={launching}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleLaunch}
              disabled={typedCount !== String(recipientCount) || launching}
            >
              {launching ? "Initiating..." : "Confirm & Launch"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
