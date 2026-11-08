import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  PhoneCall,
  Clock,
  Tag,
  MessageSquare,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import Modal from "../Modal";
import Badge from "../Badge";
import Button from "../Button";
import { api } from "../../api/client";
import { formatDate } from "../../utils/format";

/**
 * CallDetailModal (aliased as CallDetailDrawer for backwards compatibility)
 * Renders call outcome, lifecycle timeline, and transcript in a centered dialog box.
 */
export default function CallDetailDrawer({ callId, onClose }) {
  const [call, setCall] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showTechnical, setShowTechnical] = useState(false);

  useEffect(() => {
    async function fetchDetail() {
      if (!callId) return;
      setLoading(true);
      try {
        const res = await api.get(`/outcomes/calls/${callId}`);
        setCall(res);
      } catch (err) {
        console.error("Failed to load call detail", err);
      } finally {
        setLoading(false);
      }
    }
    fetchDetail();
  }, [callId]);

  if (!callId) return null;

  const renderTranscript = () => {
    const raw = call?.transcript;
    if (!raw) {
      return (
        <div className="p-6 text-center text-muted t-body-xs bg-canvas rounded-xl border border-hairline">
          Transcript not received for this call.
        </div>
      );
    }

    if (Array.isArray(raw)) {
      return (
        <div className="space-y-3 max-h-72 overflow-y-auto p-4 rounded-xl bg-canvas border border-hairline">
          {raw.map((msg, i) => {
            const isBot =
              msg.role === "assistant" ||
              msg.speaker === "assistant" ||
              msg.role === "agent" ||
              msg.speaker === "agent";
            return (
              <div key={i} className={`flex flex-col ${isBot ? "items-start" : "items-end"}`}>
                <span className="text-[10px] font-mono text-muted mb-1 uppercase tracking-wider">
                  {isBot ? "TARA Voice Assistant" : "Customer"}
                </span>
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-xs leading-relaxed ${
                    isBot ? "bg-surface-card border border-hairline text-ink shadow-xs" : "bg-primary text-on-primary"
                  }`}
                >
                  {msg.content || msg.text || (typeof msg === "string" ? msg : JSON.stringify(msg))}
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    // String transcript
    const lines = String(raw).split("\n").filter((l) => l.trim().length > 0);
    return (
      <div className="space-y-2 max-h-72 overflow-y-auto p-4 rounded-xl bg-canvas border border-hairline text-xs font-mono text-ink">
        {lines.map((l, i) => (
          <div key={i} className="py-1 border-b border-hairline/40 last:border-none">
            {l}
          </div>
        ))}
      </div>
    );
  };

  const modalTitle = (
    <div className="flex items-center gap-2.5">
      <PhoneCall className="w-5 h-5 text-primary shrink-0" />
      <span>{call?.recipient_name || "Call Record"}</span>
      {call?.status && (
        <Badge
          variant={
            call.status === "COMPLETED"
              ? "success"
              : call.status === "BLOCKED"
              ? "warning"
              : call.status === "FAILED"
              ? "danger"
              : "default"
          }
          className="text-[11px]"
        >
          {call.status}
        </Badge>
      )}
    </div>
  );

  const modalSubtitle = (
    <div className="flex items-center gap-2 text-xs text-muted font-mono mt-0.5">
      <span>{call?.phone_masked}</span>
      {callId && (
        <>
          <span>•</span>
          <span>#{callId.slice(-6)}</span>
        </>
      )}
      {call?.test_run_label && (
        <>
          <span>•</span>
          <span className="bg-surface-strong px-2 py-0.5 rounded text-[11px] text-body">
            {call.test_run_label}
          </span>
        </>
      )}
    </div>
  );

  return (
    <Modal
      isOpen={!!callId}
      onClose={onClose}
      title={modalTitle}
      subtitle={modalSubtitle}
      maxWidth="max-w-2xl"
    >
      {loading ? (
        <div className="py-12 text-center text-muted t-body-sm font-sans">
          Loading call details...
        </div>
      ) : (
        <div className="space-y-5 font-sans">
          {/* Campaign Link & Timing */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-canvas p-4 rounded-xl border border-hairline">
              <span className="t-label text-muted block mb-1">Campaign</span>
              {call.campaign_id ? (
                <Link
                  to={`/app/campaigns/${call.campaign_id}`}
                  className="font-semibold text-primary hover:underline text-xs"
                >
                  {call.campaign_name || "View Campaign"}
                </Link>
              ) : (
                <span className="text-muted text-xs">Ad-hoc dispatch</span>
              )}
            </div>
            <div className="bg-canvas p-4 rounded-xl border border-hairline">
              <span className="t-label text-muted block mb-1">Duration</span>
              <span className="t-body-strong font-mono text-ink text-xs">
                {call.outcome?.duration_seconds !== null && call.outcome?.duration_seconds !== undefined ? (
                  <>
                    <span>{call.outcome.duration_seconds}s</span>
                    {(call.outcome.duration_source === "derived" || call.outcome.duration_type === "derived") && (
                      <span className="ml-1 text-[11px] font-sans font-normal text-muted">(derived)</span>
                    )}
                  </>
                ) : (
                  "—"
                )}
              </span>
            </div>
          </div>

          {/* Event Lifecycle Timeline */}
          <div className="space-y-2">
            <h4 className="t-label text-muted-soft flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" /> Event Lifecycle Timeline
            </h4>
            <div className="bg-canvas rounded-xl border border-hairline p-4 space-y-3">
              {(call.timeline || []).map((t, i) => (
                <div
                  key={i}
                  className="flex items-start justify-between gap-4 border-b border-hairline/60 pb-2.5 last:border-none last:pb-0"
                >
                  <div>
                    <span className="font-semibold text-ink text-xs uppercase tracking-wider block">
                      {t.event}
                    </span>
                    <span className="text-[11px] text-muted">source: {t.source}</span>
                  </div>
                  <span className="text-[11px] text-muted font-mono">{formatDate(t.timestamp)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Structured Extraction & Outcome */}
          <div className="space-y-2">
            <h4 className="t-label text-muted-soft flex items-center gap-1.5">
              <Tag className="w-3.5 h-3.5" /> Structured Extraction & Outcome
            </h4>
            <div className="bg-canvas rounded-xl border border-hairline divide-y divide-hairline">
              <div className="px-4 py-3 flex justify-between items-center text-xs">
                <span className="text-body">Interest Level</span>
                <strong className="text-ink">{call.outcome?.interest_level || "Not detected"}</strong>
              </div>
              {call.outcome?.qualification_status && (
                <div className="px-4 py-3 flex justify-between items-center text-xs">
                  <span className="text-body">Qualification Status</span>
                  <Badge variant={call.outcome.qualification_status === "qualified" ? "success" : "default"} className="text-[11px] uppercase">
                    {call.outcome.qualification_status}
                  </Badge>
                </div>
              )}
              <div className="px-4 py-3 flex justify-between items-center text-xs">
                <span className="text-body">Preferred Amount</span>
                <strong className="text-ink">{call.outcome?.preferred_amount || "—"}</strong>
              </div>
              <div className="px-4 py-3 flex justify-between items-center text-xs">
                <span className="text-body">Callback Time</span>
                <strong className="text-ink">{call.outcome?.preferred_callback_time || "—"}</strong>
              </div>
              <div className="px-4 py-3 flex justify-between items-center text-xs">
                <span className="text-body">Language Detected</span>
                <strong className="text-ink uppercase">{call.outcome?.language_used || "—"}</strong>
              </div>
              {call.outcome?.recommended_next_action && (
                <div className="px-4 py-3 flex justify-between items-center text-xs">
                  <span className="text-body">Recommended Action</span>
                  <strong className="text-primary font-mono text-[11px]">{call.outcome.recommended_next_action}</strong>
                </div>
              )}
              {call.outcome?.call_summary && (
                <div className="px-4 py-3 text-xs">
                  <span className="text-muted block mb-1">AI Conversation Summary:</span>
                  <p className="text-ink text-[12px] leading-relaxed italic">{call.outcome.call_summary}</p>
                </div>
              )}
            </div>
          </div>

          {/* Call Transcript */}
          <div className="space-y-2">
            <h4 className="t-label text-muted-soft flex items-center gap-1.5">
              <MessageSquare className="w-3.5 h-3.5" /> Call Transcript
            </h4>
            {renderTranscript()}
          </div>

          {/* Telephony Metadata / Reason */}
          {(call.hangup_reason || call.blocked_reason || call.error) && (
            <div className="p-3.5 rounded-xl bg-amber-50/60 border border-amber-200 text-xs text-amber-950 space-y-1">
              {call.hangup_reason && (
                <div><strong>Hangup Reason:</strong> {call.hangup_reason}</div>
              )}
              {call.blocked_reason && (
                <div><strong>Blocked Reason:</strong> {call.blocked_reason}</div>
              )}
              {call.error && (
                <div><strong>Error Detail:</strong> {call.error}</div>
              )}
            </div>
          )}

          {/* Collapsed Technical Details (SUPER_ADMIN only) */}
          {call.technical_details && (
            <div className="pt-2 border-t border-hairline">
              <button
                type="button"
                onClick={() => setShowTechnical(!showTechnical)}
                className="flex items-center justify-between w-full py-2 text-xs font-mono text-muted hover:text-ink cursor-pointer"
              >
                <span>Technical Details (SUPER_ADMIN)</span>
                {showTechnical ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {showTechnical && (
                <pre className="p-3 mt-2 rounded-xl bg-surface-dark text-on-dark text-[11px] font-mono overflow-x-auto max-h-60">
                  {JSON.stringify(call.technical_details, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
