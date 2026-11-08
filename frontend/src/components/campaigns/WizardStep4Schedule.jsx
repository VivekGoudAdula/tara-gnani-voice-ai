import React, { useState, useEffect } from "react";
import { Clock, Calendar, Sliders, ShieldCheck, CheckCircle2, RotateCcw } from "lucide-react";
import Card from "../Card";
import Button from "../Button";
import Input from "../Input";
import { api } from "../../api/client";

export default function WizardStep4Schedule({ campaign, onScheduleUpdated }) {
  const [dispatchType, setDispatchType] = useState(campaign?.scheduled_start_time ? "scheduled" : "immediate");
  const [scheduledTime, setScheduledTime] = useState(
    campaign?.scheduled_start_time ? new Date(campaign.scheduled_start_time).toISOString().slice(0, 16) : ""
  );
  const [testRunLabel, setTestRunLabel] = useState(campaign?.test_run_label || "");
  const [callDelay, setCallDelay] = useState(5);
  const [maxRetries, setMaxRetries] = useState(2);
  const [retryInterval, setRetryInterval] = useState(60);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSaveParameters = async () => {
    if (!campaign?.id) return;
    setSaving(true);
    setSavedSuccess(false);

    try {
      // 1. Update Campaign metadata (scheduled time & test run label)
      const scheduledPayload = dispatchType === "scheduled" && scheduledTime ? new Date(scheduledTime).toISOString() : null;
      await api.put(`/campaigns/${campaign.id}`, {
        test_run_label: testRunLabel.trim() || null,
        scheduled_start_time: scheduledPayload,
      });

      // 2. If scheduled, invoke scheduling endpoint
      if (dispatchType === "scheduled" && scheduledPayload) {
        await api.post(`/campaigns/${campaign.id}/schedule`, {
          scheduled_start_time: scheduledPayload,
        });
      }

      setSavedSuccess(true);
      if (onScheduleUpdated) onScheduleUpdated();
    } catch (err) {
      alert(err.message || "Failed to save dispatch schedule parameters");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl font-sans">
      <Card className="p-6 space-y-5">
        <div className="pb-3 border-b border-hairline">
          <h3 className="t-heading-sm text-ink flex items-center gap-2">
            <Clock className="w-5 h-5 text-primary" /> Step 4: Schedule & Dispatch Parameters
          </h3>
          <p className="text-xs text-muted mt-1">
            Configure telephony dispatch timing, call pacing, retry rules, and regulatory calling hours.
          </p>
        </div>

        {/* 1. Launch Mode */}
        <div className="space-y-3">
          <label className="text-xs font-semibold text-ink uppercase tracking-wider block">
            Dispatch Timing Mode
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div
              onClick={() => setDispatchType("immediate")}
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                dispatchType === "immediate"
                  ? "bg-primary/5 border-ink text-ink font-semibold shadow-xs"
                  : "bg-surface-card border-hairline text-muted hover:border-hairline-strong"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-sm">Immediate On Launch</span>
              </div>
              <p className="text-xs font-normal text-muted">
                Campaign begins calling eligible candidates as soon as you confirm launch.
              </p>
            </div>

            <div
              onClick={() => setDispatchType("scheduled")}
              className={`p-4 rounded-xl border cursor-pointer transition-all ${
                dispatchType === "scheduled"
                  ? "bg-primary/5 border-ink text-ink font-semibold shadow-xs"
                  : "bg-surface-card border-hairline text-muted hover:border-hairline-strong"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <Calendar className="w-4 h-4 text-purple-600" />
                <span className="text-sm">Scheduled Future Time</span>
              </div>
              <p className="text-xs font-normal text-muted">
                Queues campaign in SCHEDULED state. Background runner starts it automatically.
              </p>
            </div>
          </div>

          {dispatchType === "scheduled" && (
            <div className="pt-2">
              <label className="text-xs font-medium text-body block mb-1">
                Target Start Time (IST / Local):
              </label>
              <input
                type="datetime-local"
                value={scheduledTime}
                onChange={(e) => setScheduledTime(e.target.value)}
                className="input-base text-sm"
              />
            </div>
          )}
        </div>

        {/* 2. Pacing & Concurrency Controls */}
        <div className="pt-4 border-t border-hairline space-y-4">
          <h4 className="text-xs font-semibold text-ink uppercase tracking-wider flex items-center gap-1.5">
            <Sliders className="w-4 h-4 text-muted" /> Pacing & Concurrency
          </h4>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-muted block mb-1">Pacing Delay Between Dials</label>
              <select
                value={callDelay}
                onChange={(e) => setCallDelay(Number(e.target.value))}
                className="input-base text-xs"
              >
                <option value={3}>3 seconds (Accelerated)</option>
                <option value={5}>5 seconds (Standard)</option>
                <option value={10}>10 seconds (Even pacing)</option>
                <option value={15}>15 seconds (Gentle dispatch)</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">Auto-Retry Max Attempts</label>
              <select
                value={maxRetries}
                onChange={(e) => setMaxRetries(Number(e.target.value))}
                className="input-base text-xs"
              >
                <option value={1}>1 Retry (2 Total Attempts)</option>
                <option value={2}>2 Retries (3 Total Attempts - Recommended)</option>
                <option value={3}>3 Retries (4 Total Attempts)</option>
              </select>
            </div>
          </div>
        </div>

        {/* 3. Calling Hours & Policy Banner */}
        <div className="p-4 rounded-xl bg-canvas border border-hairline space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-ink">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>TRAI & RBI Compliance Policy Enforcement</span>
          </div>
          <p className="text-xs text-muted leading-relaxed">
            Outbound calls are restricted to compliant window hours <strong>09:00 to 21:00 IST</strong>. Calls scheduled outside this window are automatically delayed by the compliance gate until the next permissible morning window.
          </p>
        </div>

        {/* 4. Test Run Label Tag */}
        <div className="pt-4 border-t border-hairline">
          <label className="text-xs font-medium text-body block mb-1">
            Test Run Tag / Campaign Label (Optional)
          </label>
          <div className="flex items-center gap-2">
            <Input
              type="text"
              value={testRunLabel}
              onChange={(e) => setTestRunLabel(e.target.value)}
              placeholder="e.g. dev-smoke-test, telugu-voice-eval"
              className="flex-1 text-xs font-mono"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleSaveParameters}
              disabled={saving}
            >
              {saving ? "Saving..." : "Save Parameters"}
            </Button>
          </div>
          {savedSuccess && (
            <span className="text-xs text-emerald-600 font-medium inline-flex items-center gap-1 mt-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" /> Dispatch parameters saved successfully.
            </span>
          )}
        </div>
      </Card>
    </div>
  );
}

