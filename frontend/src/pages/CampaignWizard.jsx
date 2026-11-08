import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, Target, Users, Mic, Clock, Rocket } from "lucide-react";
import { api } from "../api/client";
import Button from "../components/Button";
import WizardStep1Details from "../components/campaigns/WizardStep1Details";
import WizardStep2Audience from "../components/campaigns/WizardStep2Audience";
import WizardStep3VoiceConfig from "../components/campaigns/WizardStep3VoiceConfig";
import WizardStep4Schedule from "../components/campaigns/WizardStep4Schedule";
import WizardStep5ReviewLaunch from "../components/campaigns/WizardStep5ReviewLaunch";

export default function CampaignWizard() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [campaign, setCampaign] = useState({
    name: "",
    description: "",
    product_id: "",
    product_name: "",
    entity_type: "lead",
    objective: "",
  });
  const [recipientCount, setRecipientCount] = useState(0);
  const [loading, setLoading] = useState(Boolean(id));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function loadCampaign() {
      if (!id) return;
      try {
        const res = await api.get(`/campaigns/${id}`);
        setCampaign(res);
        const tot = Object.values(res.recipient_counts || {}).reduce((a, b) => a + b, 0);
        setRecipientCount(tot);
      } catch (err) {
        console.error("Failed to load campaign", err);
      } finally {
        setLoading(false);
      }
    }
    loadCampaign();
  }, [id]);

  const handleStep1Change = (key, val) => {
    setCampaign((prev) => ({ ...prev, [key]: val }));
  };

  const handleNext = async () => {
    if (step === 1) {
      if (!campaign.name || !campaign.product_id || !campaign.objective) {
        alert("Please complete campaign name, target product, and objective.");
        return;
      }
      setSaving(true);
      try {
        if (!campaign.id) {
          const created = await api.post("/campaigns", {
            name: campaign.name,
            description: campaign.description,
            product_id: campaign.product_id,
            entity_type: campaign.entity_type,
            objective: campaign.objective,
            test_run_label: campaign.test_run_label || null,
          });
          setCampaign(created);
          navigate(`/app/campaigns/${created.id}/edit`, { replace: true });
        } else {
          const updated = await api.put(`/campaigns/${campaign.id}`, {
            name: campaign.name,
            description: campaign.description,
            product_id: campaign.product_id,
            entity_type: campaign.entity_type,
            objective: campaign.objective,
            test_run_label: campaign.test_run_label || null,
          });
          setCampaign(updated);
        }
        setStep(2);
      } catch (err) {
        alert(err.message || "Failed to save campaign details");
      } finally {
        setSaving(false);
      }
    } else if (step === 2) {
      if (recipientCount === 0) {
        alert("Please select at least one recipient candidate before proceeding.");
        return;
      }
      setStep(3);
    } else if (step === 3) {
      setStep(4);
    } else if (step === 4) {
      setStep(5);
    }
  };

  const stepsMeta = [
    { num: 1, label: "Details", icon: Target },
    { num: 2, label: "Audience Selection", icon: Users },
    { num: 3, label: "Voice AI Persona", icon: Mic },
    { num: 4, label: "Schedule & Pacing", icon: Clock },
    { num: 5, label: "Review & Pre-Flight", icon: Rocket },
  ];

  if (loading) {
    return <div className="p-12 text-center text-muted t-body-sm">Loading campaign draft...</div>;
  }

  return (
    <div className="space-y-6 font-sans">
      {/* Top Bar */}
      <div className="flex items-center justify-between pb-3 border-b border-hairline">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => navigate("/app/campaigns")}>
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Campaigns
          </Button>
          <div>
            <h1 className="t-heading-sm text-ink">{campaign.name || "New Outreach Campaign"}</h1>
            <p className="t-body-xs text-muted">Step {step} of 5: {stepsMeta[step - 1].label}</p>
          </div>
        </div>
      </div>

      {/* Stepper Navigation */}
      <div className="grid grid-cols-5 gap-2 border-b border-hairline pb-4">
        {stepsMeta.map((s) => {
          const isDone = step > s.num;
          const isCurrent = step === s.num;
          return (
            <div
              key={s.num}
              onClick={() => campaign.id && setStep(s.num)}
              className={`flex items-center gap-2.5 p-2 rounded-xl cursor-pointer transition-colors ${
                isCurrent
                  ? "bg-primary text-white"
                  : isDone
                  ? "text-ink hover:bg-surface-strong/40"
                  : "text-muted hover:bg-surface-strong/20"
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                  isCurrent
                    ? "bg-white text-primary"
                    : isDone
                    ? "bg-emerald-600 text-white"
                    : "bg-surface-strong text-muted"
                }`}
              >
                {isDone ? <Check className="w-3.5 h-3.5" /> : s.num}
              </div>
              <span className="text-xs font-medium truncate hidden md:inline">{s.label}</span>
            </div>
          );
        })}
      </div>

      {/* Wizard Step Body */}
      <div>
        {step === 1 && <WizardStep1Details data={campaign} onChange={handleStep1Change} />}
        {step === 2 && (
          <WizardStep2Audience
            campaignId={campaign.id}
            savedRecipientCount={recipientCount}
            onAudienceSaved={(cnt) => setRecipientCount(cnt)}
          />
        )}
        {step === 3 && (
          <WizardStep3VoiceConfig
            campaignId={campaign.id}
            initialConfig={campaign.current_voice_config}
            onConfigSaved={(v) => setCampaign((prev) => ({ ...prev, config_version: v }))}
          />
        )}
        {step === 4 && (
          <WizardStep4Schedule
            campaign={campaign}
            onScheduleUpdated={() => {}}
          />
        )}
        {step === 5 && (
          <WizardStep5ReviewLaunch
            campaign={campaign}
            recipientCount={recipientCount}
          />
        )}
      </div>

      {/* Footer Stepper Controls */}
      <div className="flex items-center justify-between pt-4 border-t border-hairline">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setStep((s) => Math.max(1, s - 1))}
          disabled={step === 1}
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back
        </Button>
        {step < 5 && (
          <Button variant="primary" size="sm" onClick={handleNext} disabled={saving}>
            {saving ? "Saving..." : "Continue"} <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Button>
        )}
      </div>
    </div>
  );
}
