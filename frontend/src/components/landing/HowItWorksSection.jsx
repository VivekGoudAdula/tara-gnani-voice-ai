import React from "react";
import Card from "../Card";

export default function HowItWorksSection() {
  const steps = [
    {
      step: "01",
      title: "Import and unify",
      desc: "Load customer and lead records with consent captured.",
    },
    {
      step: "02",
      title: "Score and match",
      desc: "Rank each record for each product, with reason codes.",
    },
    {
      step: "03",
      title: "Build and configure",
      desc: "Choose the audience, then set the voice prompt, questions to collect and retry policy.",
    },
    {
      step: "04",
      title: "Call and capture",
      desc: "The voice agent calls; interest, amount and callback time appear in Interaction History.",
    },
  ];

  return (
    <section id="how-it-works" className="py-16 lg:py-24 border-t border-hairline bg-canvas">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-10 lg:mb-12">
          <span className="t-label text-muted-soft block mb-2">Workflow</span>
          <h2 className="t-display-lg font-bold text-ink mb-2">How TARA works</h2>
          <p className="t-body-md text-muted font-sans">
            From raw data to conversations in four steps.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 items-stretch">
          {steps.map((item) => (
            <Card key={item.step} hoverable className="flex flex-col justify-between p-6">
              <div>
                <span className="t-label text-muted block mb-3 font-mono">{item.step}</span>
                <h3 className="t-title-sm text-ink mb-2">{item.title}</h3>
                <p className="t-body-sm text-body leading-relaxed font-sans">{item.desc}</p>
              </div>
            </Card>
          ))}
        </div>

        <p className="mt-8 text-center text-xs text-muted-soft font-sans">
          Learning from outcomes back into scoring is on the roadmap.
        </p>
      </div>
    </section>
  );
}
