import React, { useState } from "react";
import { MessageSquare, Mail, PhoneCall, Clock, CheckCircle2 } from "lucide-react";
import Card from "../Card";
import Button from "../Button";
import Input from "../Input";
import Badge from "../Badge";
import { api } from "../../api/client";

export default function WizardNonVoiceConfigs({ campaignId, channel }) {
  const [waConfig, setWaConfig] = useState({ template_name: "festive_loan_offer", body: "Hello {{customer_name}}, check your pre-approved loan of {{preferred_amount}}.", cta_label: "View Offer", cta_url: "https://bank.com/offers" });
  const [smsConfig, setSmsConfig] = useState({ body: "Hi {{customer_name}}, your loan offer is ready at {{bank_name}}. Apply now!" });
  const [emailConfig, setEmailConfig] = useState({ sender_name: "Outreach Team", subject: "Special Offer: {{product_name}}", body: "Dear {{customer_name}},\n\nWe are pleased to introduce our {{product_name}} tailored for your requirements.\n\nWarm regards,\n{{bank_name}}", cta_label: "Check Eligibility", cta_url: "https://bank.com" });
  const [saving, setSaving] = useState(false);
  const [savedVersion, setSavedVersion] = useState(null);

  const handleSave = async (data) => {
    setSaving(true);
    try {
      const res = await api.put(`/campaigns/${campaignId}/config/${channel}`, data);
      setSavedVersion(res.version);
    } catch (err) {
      alert(err.message || "Failed to save configuration");
    } finally {
      setSaving(false);
    }
  };

  const getSmsSegments = (text) => {
    const isUnicode = /[^\u0000-\u007F]/.test(text);
    const limit = isUnicode ? 70 : 160;
    const len = text.length;
    const segments = Math.ceil(len / limit) || 1;
    return { len, limit, segments, isUnicode };
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Execution Coming Soon Notice */}
      <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 t-body-sm flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Clock className="w-5 h-5 text-amber-600 shrink-0" />
          <span>
            <strong>Channel Preview Mode:</strong> {channel.toUpperCase()} configuration can be versioned and stored. Outreach execution is scheduled for Phase 5.
          </span>
        </div>
        <Badge variant="warning">Execution coming soon</Badge>
      </div>

      {channel === "whatsapp" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="p-5 space-y-4">
            <h4 className="t-heading-sm text-ink pb-2 border-b border-hairline">WhatsApp Template Configuration</h4>
            <div>
              <label className="block t-label text-xs mb-1">Template Identifier</label>
              <Input
                type="text"
                value={waConfig.template_name}
                onChange={(e) => setWaConfig({ ...waConfig, template_name: e.target.value })}
                className="w-full text-xs font-mono"
              />
            </div>
            <div>
              <label className="block t-label text-xs mb-1">Message Body</label>
              <textarea
                rows={4}
                value={waConfig.body}
                onChange={(e) => setWaConfig({ ...waConfig, body: e.target.value })}
                className="input-base w-full py-2 px-3 text-xs resize-none font-mono"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block t-label text-xs mb-1">CTA Button Label</label>
                <Input
                  type="text"
                  value={waConfig.cta_label}
                  onChange={(e) => setWaConfig({ ...waConfig, cta_label: e.target.value })}
                  className="w-full text-xs"
                />
              </div>
              <div>
                <label className="block t-label text-xs mb-1">CTA URL</label>
                <Input
                  type="text"
                  value={waConfig.cta_url}
                  onChange={(e) => setWaConfig({ ...waConfig, cta_url: e.target.value })}
                  className="w-full text-xs"
                />
              </div>
            </div>
            <Button variant="primary" size="sm" onClick={() => handleSave(waConfig)} disabled={saving}>
              {saving ? "Saving..." : "Save WhatsApp Config"}
            </Button>
          </Card>

          <Card className="p-5 bg-[#ECE5DD] rounded-xl flex flex-col justify-center items-center">
            <div className="bg-white rounded-lg p-3 shadow-md max-w-sm w-full space-y-2 text-ink text-sm">
              <p className="whitespace-pre-wrap">{waConfig.body}</p>
              {waConfig.cta_label && (
                <div className="pt-2 border-t border-hairline text-center">
                  <span className="text-emerald-700 font-medium text-xs flex items-center justify-center gap-1">
                    {waConfig.cta_label}
                  </span>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {channel === "sms" && (
        <Card className="p-5 space-y-4 max-w-2xl">
          <h4 className="t-heading-sm text-ink pb-2 border-b border-hairline">SMS Template Configuration</h4>
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="t-label text-xs">SMS Body</label>
              {(() => {
                const s = getSmsSegments(smsConfig.body);
                return (
                  <span className="t-body-xs font-mono text-muted">
                    {s.len} chars ({s.segments} segment{s.segments > 1 ? "s" : ""} - {s.isUnicode ? "Unicode" : "GSM"})
                  </span>
                );
              })()}
            </div>
            <textarea
              rows={4}
              value={smsConfig.body}
              onChange={(e) => setSmsConfig({ body: e.target.value })}
              className="input-base w-full py-2 px-3 text-xs resize-none font-mono"
            />
          </div>
          <Button variant="primary" size="sm" onClick={() => handleSave(smsConfig)} disabled={saving}>
            {saving ? "Saving..." : "Save SMS Config"}
          </Button>
        </Card>
      )}

      {channel === "email" && (
        <Card className="p-5 space-y-4 max-w-2xl">
          <h4 className="t-heading-sm text-ink pb-2 border-b border-hairline">Email Template Configuration</h4>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block t-label text-xs mb-1">Sender Name</label>
              <Input
                type="text"
                value={emailConfig.sender_name}
                onChange={(e) => setEmailConfig({ ...emailConfig, sender_name: e.target.value })}
                className="w-full text-xs"
              />
            </div>
            <div>
              <label className="block t-label text-xs mb-1">Subject</label>
              <Input
                type="text"
                value={emailConfig.subject}
                onChange={(e) => setEmailConfig({ ...emailConfig, subject: e.target.value })}
                className="w-full text-xs"
              />
            </div>
          </div>
          <div>
            <label className="block t-label text-xs mb-1">Body Text</label>
            <textarea
              rows={5}
              value={emailConfig.body}
              onChange={(e) => setEmailConfig({ ...emailConfig, body: e.target.value })}
              className="input-base w-full py-2 px-3 text-xs resize-none"
            />
          </div>
          <Button variant="primary" size="sm" onClick={() => handleSave(emailConfig)} disabled={saving}>
            {saving ? "Saving..." : "Save Email Config"}
          </Button>
        </Card>
      )}

      {savedVersion && (
        <div className="p-3 bg-emerald-50 text-emerald-800 rounded-lg text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          Configuration version {savedVersion} saved successfully.
        </div>
      )}
    </div>
  );
}
