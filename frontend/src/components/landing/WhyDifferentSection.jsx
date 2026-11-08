import React from "react";
import { Layers, ShieldCheck, Radio } from "lucide-react";

export default function WhyDifferentSection() {
  const cards = [
    {
      icon: Layers,
      title: "Multi-product fit ranking",
      body: "One lead can match many products. Eligibility is a filter, not a deletion, so the whole audience stays available.",
    },
    {
      icon: ShieldCheck,
      title: "Compliance at the dispatch layer",
      body: "Consent, a do-not-disturb flag, a 09:00 to 21:00 IST calling window and frequency caps are enforced in the communication layer before a call is placed.",
    },
    {
      icon: Radio,
      title: "Channel-agnostic API",
      body: "Campaigns are independent of providers. Voice is live; WhatsApp, SMS and Email are on the roadmap behind the same communication API.",
    },
  ];

  return (
    <section
      id="why-different"
      className="relative isolate overflow-hidden min-h-screen flex flex-col justify-center py-20 lg:py-28"
    >
      {/* Background Graphic whytara.png */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat pointer-events-none z-0"
        style={{ backgroundImage: "url('/whytara.png')" }}
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 w-full my-auto -translate-y-6 lg:-translate-y-10">
        <div className="mb-10 lg:mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/45 backdrop-blur-md border border-white/60 text-xs font-semibold text-ink mb-3 shadow-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-600" />
            <span>Architecture</span>
          </div>
          <h2 className="t-display-lg text-ink font-serif tracking-tight">Why TARA is different</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8 items-stretch">
          {cards.map((card, idx) => {
            const Icon = card.icon;
            return (
              <div
                key={idx}
                className="flex flex-col justify-between rounded-2xl bg-white/45 backdrop-blur-xl border border-white/60 p-7 sm:p-8 shadow-[inset_0_1px_1px_rgba(255,255,255,0.85),0_12px_36px_rgba(0,0,0,0.06)] hover:bg-white/60 hover:border-white/80 transition-colors"
              >
                <div>
                  <div className="w-10 h-10 rounded-xl bg-white/65 backdrop-blur-md border border-white/80 shadow-[inset_0_1px_1px_rgba(255,255,255,0.9),0_2px_8px_rgba(0,0,0,0.04)] flex items-center justify-center text-ink mb-5">
                    <Icon className="w-5 h-5 text-ink" />
                  </div>
                  <h3 className="text-xl sm:text-2xl font-serif font-bold text-ink mb-3 tracking-tight">
                    {card.title}
                  </h3>
                  <p className="t-body-sm text-body leading-relaxed font-sans">
                    {card.body}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
