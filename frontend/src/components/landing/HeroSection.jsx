import React from "react";
import { ArrowRight, Shield, Sparkles, Languages, Clock } from "lucide-react";
import Button from "../Button";

/**
 * HeroSection Component
 * Displays the main value proposition, primary CTAs, and capability proof strip.
 */
export default function HeroSection() {
  const proofTags = [
    { text: "Explainable product matching", icon: Sparkles },
    { text: "Voice AI in 3 Indian languages", icon: Languages },
    { text: "Consent and calling-hour controls", icon: Clock },
    { text: "Per-bank data isolation", icon: Shield },
  ];

  return (
    <section className="relative isolate overflow-hidden min-h-screen min-h-[100dvh] w-full flex flex-col justify-between pt-20 sm:pt-24 lg:pt-28 pb-6 sm:pb-10 bg-[#d8eef3]">
      {/* Background Hero Image - Full coverage across all aspect ratios with soft blur */}
      <div
        className="absolute inset-0 w-full h-full bg-cover bg-center bg-no-repeat pointer-events-none z-0 filter blur-[5px] scale-[1.03]"
        style={{
          backgroundImage: "url('/hero.png')",
          backgroundPosition: "center center",
          backgroundSize: "cover",
        }}
      />

      {/* Subtle top vignette for crystal clear navbar legibility */}
      <div className="absolute top-0 inset-x-0 h-20 sm:h-24 bg-gradient-to-b from-white/60 via-white/20 to-transparent pointer-events-none z-10" />

      {/* Subtle bottom edge blend into canvas (#f5f5f5) */}
      <div
        className="absolute bottom-0 inset-x-0 h-12 bg-gradient-to-t from-[#f5f5f5] to-transparent pointer-events-none z-10"
      />

      {/* Center Hero Content (vertically centered on any viewport height) */}
      <div className="relative z-20 max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 my-auto py-4 sm:py-8 text-center flex flex-col items-center">
        <div className="w-full mx-auto">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-surface-card/90 backdrop-blur-sm border border-hairline text-xs sm:text-sm text-body mb-4 sm:mb-6 shadow-soft">
            <span className="w-1.5 h-1.5 rounded-full bg-semantic-success" />
            <span>Enterprise customer intelligence for lenders</span>
          </div>

          {/* Fluid Headline */}
          <h1
            className="!font-normal text-ink mb-4 sm:mb-6 tracking-tight font-serif"
            style={{
              fontSize: "clamp(2.25rem, 4.5vw + 0.5rem, 5.25rem)",
              lineHeight: 1.08,
            }}
          >
            Turn customer data into
            <span className="block font-bold text-ink">targeted growth</span>
          </h1>

          {/* Fluid Subheadline */}
          <p
            className="text-body max-w-2xl lg:max-w-3xl mx-auto mb-6 sm:mb-8 font-sans leading-relaxed"
            style={{
              fontSize: "clamp(0.95rem, 1.1vw + 0.2rem, 1.25rem)",
            }}
          >
            TARA helps lending teams identify high-fit prospects, understand why each one fits, and reach them with a voice AI agent in Hindi, Telugu or English.
          </p>

          {/* Actions */}
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button to="/signup" variant="primary" size="md" className="shadow-md text-xs sm:text-sm px-5 py-2.5">
              <span>Create workspace</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
            <Button to="/login" variant="outline" size="md" className="bg-surface-card/80 backdrop-blur-xs text-xs sm:text-sm px-5 py-2.5">
              <span>Sign in</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Bottom Proof Strip (anchored nicely above the fold) */}
      <div className="relative z-20 max-w-6xl w-full mx-auto px-4 sm:px-6 lg:px-8 pb-2 sm:pb-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3.5">
          {proofTags.map((tag, idx) => {
            const Icon = tag.icon;
            return (
              <div
                key={idx}
                className="flex items-center gap-2.5 p-2.5 sm:p-3 rounded-xl bg-surface-card/90 backdrop-blur-sm border border-hairline shadow-soft"
              >
                <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-surface-strong flex items-center justify-center text-ink shrink-0">
                  <Icon className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-ink" />
                </div>
                <span className="text-xs sm:text-sm font-medium text-ink">{tag.text}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
