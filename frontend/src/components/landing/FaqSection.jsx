import React, { useState } from "react";
import { ChevronDown } from "lucide-react";
import Button from "../Button";

/**
 * FaqSection Component
 * Answers common customer questions with factual, honest disclosures.
 */
export default function FaqSection() {
  const [openIdx, setOpenIdx] = useState(0);

  const faqs = [
    {
      q: "What is TARA?",
      a: "A voice-first outreach platform for banks, NBFCs and lenders: it scores customers and leads for product fit, then runs voice campaigns.",
    },
    {
      q: "Does the model decide who gets credit?",
      a: "No. It ranks fit. Eligibility comes from policy rules you configure, and a person approves every offer.",
    },
    {
      q: "What data do I need?",
      a: "A CSV of customers or leads with phone number and name, and a consent flag. Other fields improve the match.",
    },
    {
      q: "Which channels work today?",
      a: "Voice, in Hindi, Telugu and English. WhatsApp, SMS and Email are on the roadmap.",
    },
    {
      q: "How is compliance handled?",
      a: "Consent, a do-not-disturb flag, a calling-hour window and contact-frequency caps are enforced before each call. We do not currently check the national DND registry.",
    },
    {
      q: "What data reaches the voice provider?",
      a: "Only what the call needs, such as first name, product and language. Scores and income are not sent.",
    },
  ];

  const toggleFaq = (index) => {
    setOpenIdx(openIdx === index ? -1 : index);
  };

  return (
    <section id="faq" className="py-20 lg:py-28 border-t border-hairline bg-canvas">
      <div className="max-w-[880px] mx-auto px-6 lg:px-8">
        <div className="text-center mb-12">
          <span className="t-label text-muted-soft block mb-2">Clarity & Governance</span>
          <h2 className="t-display-lg font-bold text-ink">Frequently asked questions</h2>
        </div>

        <div className="space-y-3">
          {faqs.map((faq, idx) => {
            const isOpen = openIdx === idx;
            return (
              <div
                key={idx}
                className="bg-surface-card border border-hairline rounded-xl overflow-hidden transition-colors"
              >
                <button
                  type="button"
                  onClick={() => toggleFaq(idx)}
                  className="w-full py-4 px-6 text-left flex items-center justify-between gap-4"
                  aria-expanded={isOpen}
                >
                  <span className="text-sm sm:text-base font-semibold text-ink font-sans">
                    {faq.q}
                  </span>
                  <ChevronDown
                    className={`w-4 h-4 text-muted-soft shrink-0 transition-transform duration-200 ${
                      isOpen ? "rotate-180 text-ink" : ""
                    }`}
                  />
                </button>
                {isOpen && (
                  <div className="px-6 pb-5 pt-1 text-sm text-body font-sans leading-relaxed border-t border-hairline/60">
                    {faq.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Institutional Onboarding Block */}
        <div className="mt-12 bg-surface-card border border-hairline rounded-xl p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-ink font-sans">Institutional onboarding</h3>
            <p className="text-xs text-body font-sans mt-0.5">
              Need custom eligibility rules or system integrations? Talk to us.
            </p>
          </div>
          <Button
            to="/login"
            variant="outline"
            size="sm"
            className="text-xs shrink-0"
          >
            Contact team
          </Button>
        </div>
      </div>
    </section>
  );
}
