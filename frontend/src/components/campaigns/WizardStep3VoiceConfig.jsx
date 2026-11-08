import React, { useState, useEffect } from "react";
import { Mic, Phone, MessageSquare, Mail, Plus, Trash2, CheckCircle2, AlertCircle, Eye, Sparkles, RefreshCw } from "lucide-react";
import Card from "../Card";
import Button from "../Button";
import Input from "../Input";
import Badge from "../Badge";
import WizardNonVoiceConfigs from "./WizardNonVoiceConfigs";
import { api } from "../../api/client";

export default function WizardStep3VoiceConfig({ campaignId, initialConfig, onConfigSaved }) {
  const [activeTab, setActiveTab] = useState("voice");
  const [config, setConfig] = useState(initialConfig || {});
  const [preview, setPreview] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);

  useEffect(() => {
    if (initialConfig && Object.keys(initialConfig).length > 0) {
      setConfig(initialConfig);
    }
  }, [initialConfig]);

  const loadLivePreview = async () => {
    if (!campaignId) return;
    setLoadingPreview(true);
    try {
      const res = await api.post(`/campaigns/${campaignId}/preview`, {});
      setPreview(res);
    } catch (err) {
      console.error("Preview failed", err);
    } finally {
      setLoadingPreview(false);
    }
  };

  useEffect(() => {
    if (activeTab === "voice") loadLivePreview();
  }, [activeTab, campaignId]);

  const handleSaveVoiceConfig = async () => {
    setSaving(true);
    try {
      const res = await api.put(`/campaigns/${campaignId}/config/voice`, config);
      await loadLivePreview();
      if (onConfigSaved) onConfigSaved(res.version);
    } catch (err) {
      alert(err.message || "Voice configuration failed validation");
    } finally {
      setSaving(false);
    }
  };

  const addQuestion = () => {
    const curr = config.questions_to_collect || [];
    if (curr.length >= 6) return;
    setConfig({
      ...config,
      questions_to_collect: [...curr, { field: `question_${curr.length + 1}`, question: "", required: true }],
    });
  };

  const removeQuestion = (idx) => {
    const curr = [...(config.questions_to_collect || [])];
    curr.splice(idx, 1);
    setConfig({ ...config, questions_to_collect: curr });
  };

  const updateQuestion = (idx, key, val) => {
    const curr = [...(config.questions_to_collect || [])];
    curr[idx] = { ...curr[idx], [key]: val };
    setConfig({ ...config, questions_to_collect: curr });
  };

  return (
    <div className="space-y-6">
      {/* Horizontal Channel Tabs */}
      <div className="flex border-b border-hairline gap-2">
        {[
          { id: "voice", label: "Voice AI Agent", icon: Mic },
          { id: "whatsapp", label: "WhatsApp", icon: MessageSquare },
          { id: "sms", label: "SMS", icon: Phone },
          { id: "email", label: "Email", icon: Mail },
        ].map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 font-medium text-sm border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-primary text-ink font-semibold"
                  : "border-transparent text-muted hover:text-ink"
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
              {tab.id !== "voice" && (
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-surface-strong text-muted">Soon</span>
              )}
            </button>
          );
        })}
      </div>

      {activeTab !== "voice" ? (
        <WizardNonVoiceConfigs campaignId={campaignId} channel={activeTab} />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Form: Voice Settings */}
          <div className="lg:col-span-7 space-y-5">
            <Card className="p-5 space-y-4">
              <h4 className="t-heading-sm text-ink pb-2 border-b border-hairline">Voice Engine & Tone</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block t-label text-xs mb-1">Language Mode</label>
                  <select
                    value={config.language_mode || "recipient"}
                    onChange={(e) => setConfig({ ...config, language_mode: e.target.value })}
                    className="input-base w-full text-xs"
                  >
                    <option value="recipient">Recipient's Stored Language (Default)</option>
                    <option value="fixed">Fixed Language</option>
                  </select>
                </div>
                {config.language_mode === "fixed" && (
                  <div>
                    <label className="block t-label text-xs mb-1">Language</label>
                    <select
                      value={config.language || "telugu"}
                      onChange={(e) => setConfig({ ...config, language: e.target.value })}
                      className="input-base w-full text-xs"
                    >
                      <option value="telugu">Telugu</option>
                      <option value="hindi">Hindi</option>
                      <option value="english">English</option>
                    </select>
                  </div>
                )}
                <div>
                  <label className="block t-label text-xs mb-1">Agent Tone</label>
                  <select
                    value={config.tone || "Professional"}
                    onChange={(e) => setConfig({ ...config, tone: e.target.value })}
                    className="input-base w-full text-xs"
                  >
                    <option value="Professional">Professional</option>
                    <option value="Friendly">Friendly</option>
                    <option value="Formal">Formal</option>
                  </select>
                </div>
              </div>
            </Card>

            <Card className="p-5 space-y-4">
              <h4 className="t-heading-sm text-ink pb-2 border-b border-hairline">Conversation Flow</h4>
              <div>
                <label className="block t-label text-xs mb-1">Opening Greeting Message</label>
                <textarea
                  rows={2}
                  value={config.opening_message || ""}
                  onChange={(e) => setConfig({ ...config, opening_message: e.target.value })}
                  className="input-base w-full py-2 px-3 text-xs resize-none font-mono"
                  placeholder="Hello {{customer_name}}, calling from {{bank_name}} regarding {{product_name}}..."
                />
              </div>
              <div>
                <label className="block t-label text-xs mb-1">Additional Instructions (Addendum)</label>
                <textarea
                  rows={2}
                  value={config.system_prompt_addendum || ""}
                  onChange={(e) => setConfig({ ...config, system_prompt_addendum: e.target.value })}
                  className="input-base w-full py-2 px-3 text-xs resize-none"
                  placeholder="Extra dialogue instructions (do not promise approvals)..."
                />
              </div>
            </Card>

            <Card className="p-5 space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-hairline">
                <h4 className="t-heading-sm text-ink">Structured Fields to Collect</h4>
                <Button variant="outline" size="sm" onClick={addQuestion} disabled={(config.questions_to_collect || []).length >= 6}>
                  <Plus className="w-3.5 h-3.5 mr-1" /> Add Field
                </Button>
              </div>
              <div className="space-y-3">
                {(config.questions_to_collect || []).map((q, idx) => (
                  <div key={idx} className="flex items-center gap-2 bg-surface-strong/40 p-2.5 rounded-lg border border-hairline">
                    <Input
                      type="text"
                      placeholder="field_name"
                      value={q.field}
                      onChange={(e) => updateQuestion(idx, "field", e.target.value)}
                      className="w-36 text-xs font-mono"
                    />
                    <Input
                      type="text"
                      placeholder="Question dialogue prompt..."
                      value={q.question}
                      onChange={(e) => updateQuestion(idx, "question", e.target.value)}
                      className="flex-1 text-xs"
                    />
                    <label className="flex items-center gap-1 text-[11px] t-label text-muted cursor-pointer shrink-0">
                      <input
                        type="checkbox"
                        checked={q.required}
                        onChange={(e) => updateQuestion(idx, "required", e.target.checked)}
                        className="w-3.5 h-3.5 text-primary"
                      />
                      Req
                    </label>
                    <button onClick={() => removeQuestion(idx)} className="p-1 text-muted hover:text-semantic-error">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </Card>

            <div className="flex justify-end">
              <Button variant="primary" size="md" onClick={handleSaveVoiceConfig} disabled={saving}>
                {saving ? "Saving..." : "Save Voice Config Version"}
              </Button>
            </div>
          </div>

          {/* Right Live Preview Card */}
          <div className="lg:col-span-5 space-y-4">
            <Card className="p-5 space-y-4 sticky top-6 bg-surface-card border-hairline">
              <div className="flex items-center justify-between pb-2 border-b border-hairline">
                <div className="flex items-center gap-2">
                  <Eye className="w-4 h-4 text-primary" />
                  <h4 className="t-heading-sm text-ink">Outreach Pre-Flight Preview</h4>
                </div>
                <Button variant="outline" size="sm" onClick={loadLivePreview} disabled={loadingPreview}>
                  <RefreshCw className={`w-3 h-3 ${loadingPreview ? "animate-spin" : ""}`} />
                </Button>
              </div>

              {preview ? (
                <div className="space-y-4">
                  <div>
                    <span className="t-label text-[11px] text-muted">Rendered Opening Dialogue:</span>
                    <div className="p-3 bg-surface-strong/70 rounded-xl text-xs font-serif italic text-ink border border-hairline mt-1">
                      "{preview.rendered_opening_message}"
                    </div>
                  </div>

                  <div>
                    <span className="t-label text-[11px] text-muted">Variables Sent to Voice Provider:</span>
                    <div className="mt-1 max-h-56 overflow-y-auto rounded-lg border border-hairline divide-y divide-hairline bg-surface-strong/30">
                      {Object.entries(preview.user_data_variables || {}).map(([k, v]) => (
                        <div key={k} className="p-2 flex justify-between items-start text-xs font-mono">
                          <span className="text-muted shrink-0 mr-2">{k}:</span>
                          <span className="text-ink text-right break-all">{v || <em className="text-muted-soft">blank</em>}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="pt-2 border-t border-hairline flex items-center justify-between text-xs">
                    <span className="text-muted">Config Version: {preview.config_version}</span>
                    <Badge variant={preview.validation_report?.valid ? "success" : "danger"}>
                      {preview.validation_report?.valid ? "Schema Valid" : "Validation Errors"}
                    </Badge>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-muted t-body-xs">Click refresh to load live rendered pre-flight preview.</div>
              )}
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
