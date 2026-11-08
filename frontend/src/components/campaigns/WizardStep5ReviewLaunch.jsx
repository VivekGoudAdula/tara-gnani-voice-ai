import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Rocket,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  PhoneCall,
  RefreshCw,
  Calendar,
} from "lucide-react";
import Card from "../Card";
import Button from "../Button";
import Input from "../Input";
import Modal from "../Modal";
import Badge from "../Badge";
import { api } from "../../api/client";
import { formatDate } from "../../utils/format";

export default function WizardStep5ReviewLaunch({ campaign, recipientCount }) {
  const navigate = useNavigate();
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [typedCount, setTypedCount] = useState("");
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState(null);
  const [validationReport, setValidationReport] = useState(null);
  const [validating, setValidating] = useState(false);

  const delaySeconds = 5;
  const estimatedSeconds = (recipientCount || 0) * delaySeconds;
  const estimatedMinutes = Math.ceil(estimatedSeconds / 60);

  // Run pre-flight validation automatically on mount
  const runValidation = async () => {
    if (!campaign?.id) return;
    setValidating(true);
    try {
      const rep = await api.post(`/campaigns/${campaign.id}/validate`);
      setValidationReport(rep);
    } catch (err) {
      console.error("Pre-flight validation check failed:", err);
    } finally {
      setValidating(false);
    }
  };

  useEffect(() => {
    runValidation();
  }, [campaign?.id]);

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

  const isScheduled = Boolean(campaign?.scheduled_start_time);

  return (
    <div className="space-y-6 max-w-3xl font-sans">
      {/* Test Mode Pre-Flight Warning */}
      <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <div className="font-bold flex items-center gap-2">
            <span>COMPLIANCE & DIALABILITY SAFEGUARD</span>
            <Badge variant="warning">TRAI Active</Badge>
          </div>
          <p className="mt-1 leading-relaxed">
            Every candidate is checked against the National DND Registry, calling hour windows (09:00 - 21:00 IST), and explicit consent requirements. In-flight duplicates are safeguarded against double-dialing.
          </p>
        </div>
      </div>

      {/* Campaign Summary Card */}
      <Card className="p-6 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-hairline">
          <h3 className="t-heading-sm text-ink flex items-center gap-2">
            <PhoneCall className="w-5 h-5 text-primary" /> Step 5: Review & Pre-Flight Validation
          </h3>
          <Button
            variant="outline"
            size="sm"
            onClick={runValidation}
            disabled={validating}
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1 ${validating ? "animate-spin" : ""}`} />
            <span>Re-verify</span>
          </Button>
        </div>

        <div className="grid grid-cols-2 gap-4 text-xs">
          <div>
            <span className="text-muted block">Campaign Name:</span>
            <div className="font-semibold text-ink text-sm mt-0.5">{campaign.name}</div>
          </div>
          <div>
            <span className="text-muted block">Target Product:</span>
            <div className="font-semibold text-ink text-sm mt-0.5">{campaign.product_name}</div>
          </div>
          <div>
            <span className="text-muted block">Audience Staged:</span>
            <div className="font-semibold text-ink font-mono text-sm mt-0.5">{recipientCount || 0} candidates</div>
          </div>
          <div>
            <span className="text-muted block">Dispatch Mode:</span>
            <div className="font-semibold text-ink flex items-center gap-1.5 text-sm mt-0.5">
              {isScheduled ? (
                <span className="text-purple-700 flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5" /> Scheduled for {formatDate(campaign.scheduled_start_time)}
                </span>
              ) : (
                <span className="text-emerald-700 flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" /> Immediate Launch (~{estimatedMinutes}m runtime)
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Pre-Flight Validation Report */}
        <div className="pt-4 border-t border-hairline space-y-3">
          <span className="text-xs font-semibold text-ink uppercase tracking-wider block">
            Pre-Flight System Check
          </span>

          {validating && !validationReport ? (
            <div className="p-4 rounded-xl bg-canvas border border-hairline text-center text-xs text-muted">
              Running automated pre-flight checks across dialability and provider connectivity...
            </div>
          ) : validationReport ? (
            <div
              className={`p-4 rounded-xl border ${
                validationReport.is_valid
                  ? "bg-emerald-50/60 border-emerald-200"
                  : "bg-rose-50/60 border-rose-200"
              }`}
            >
              <div className="flex items-center gap-2">
                {validationReport.is_valid ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0" />
                )}
                <div>
                  <h4 className="text-sm font-semibold text-ink">
                    {validationReport.is_valid ? "Campaign Validated & Ready" : "Validation Issues Detected"}
                  </h4>
                  <p className="text-xs text-muted mt-0.5">
                    {validationReport.eligible_recipients} eligible dialable recipients • {validationReport.blocked_estimate} blocked estimate
                  </p>
                </div>
              </div>

              {validationReport.errors?.length > 0 && (
                <div className="mt-3 text-xs text-rose-700 space-y-1">
                  {validationReport.errors.map((err, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <XCircle className="w-3.5 h-3.5 shrink-0" />
                      <span>{err}</span>
                    </div>
                  ))}
                </div>
              )}

              {validationReport.warnings?.length > 0 && (
                <div className="mt-2 text-xs text-amber-700 space-y-1">
                  {validationReport.warnings.map((w, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <span>⚠</span>
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Action Button */}
        <div className="pt-4 border-t border-hairline flex items-center justify-between">
          <span className="text-xs text-muted">
            Ready to proceed with {recipientCount || 0} customer recipients.
          </span>
          <Button
            variant="primary"
            size="md"
            onClick={() => setShowConfirmModal(true)}
            disabled={(recipientCount || 0) === 0}
          >
            <Rocket className="w-4 h-4 mr-2" />
            <span>{isScheduled ? "Confirm & Schedule" : "Confirm & Launch Campaign"}</span>
          </Button>
        </div>
      </Card>

      {/* Confirmation Modal */}
      <Modal
        isOpen={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        title={isScheduled ? "Confirm Campaign Schedule" : "Confirm Campaign Dispatch"}
        subtitle="This action will schedule or initiate actual telephone calls through Twilio Voice."
      >
        <div className="space-y-4 text-xs font-sans">
          <p className="text-body leading-relaxed">
            You are about to launch voice outreach for <strong>{recipientCount}</strong> recipients under campaign{" "}
            <strong>"{campaign.name}"</strong>.
          </p>

          <div className="p-3 bg-surface-strong/60 rounded-xl border border-hairline space-y-1">
            <div className="font-semibold text-ink">Confirmation Safeguard:</div>
            <p className="text-muted">
              Please enter the number of recipients (<strong>{recipientCount}</strong>) below to confirm:
            </p>
            <Input
              type="text"
              value={typedCount}
              onChange={(e) => setTypedCount(e.target.value)}
              placeholder={`Type "${recipientCount}" to confirm`}
              className="mt-2 text-sm font-mono"
            />
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-semantic-error">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-hairline">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowConfirmModal(false)}
              disabled={launching}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleLaunch}
              disabled={launching || parseInt(typedCount, 10) !== recipientCount}
            >
              {launching ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  <span>Initiating...</span>
                </>
              ) : (
                <span>Confirm & Proceed</span>
              )}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

