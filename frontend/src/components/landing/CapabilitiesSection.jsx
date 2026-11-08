import React from "react";
import Card from "../Card";

export default function CapabilitiesSection() {
  const capabilities = [
    {
      num: "01",
      title: "Data import",
      body: "Bring customers and leads in from CSV, or load sample data to explore. Database connectors are on the roadmap.",
    },
    {
      num: "02",
      title: "Predictive, explainable matching",
      body: "Every customer and lead is scored against every product, with reasons and policy eligibility checks. Lower scores are never deleted.",
    },
    {
      num: "03",
      title: "Campaigns and voice outreach",
      body: "Build an audience by fit band and eligibility, configure the voice agent, preview, and launch.",
    },
    {
      num: "04",
      title: "Governance and audit",
      body: "Consent, do-not-disturb flag, calling-hour window and contact-frequency cap are checked before each call, and every attempt is logged.",
    },
  ];

  return (
    <section id="capabilities" className="py-16 lg:py-24 bg-canvas">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-10 lg:mb-12">
          <span className="t-label text-muted-soft block mb-2">Capabilities</span>
          <h2 className="t-display-lg font-bold text-ink">Built for modern lending teams</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 items-stretch">
          {capabilities.map((item) => (
            <Card key={item.num} hoverable className="flex flex-col justify-between p-6">
              <div>
                <span className="t-label text-muted block mb-3 font-mono">{item.num}</span>
                <h3 className="t-title-sm text-ink mb-2">{item.title}</h3>
                <p className="t-body-sm text-body leading-relaxed font-sans">{item.body}</p>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
