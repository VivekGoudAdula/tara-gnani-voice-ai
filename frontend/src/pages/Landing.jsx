import React from "react";
import LandingNavbar from "../components/landing/LandingNavbar";
import HeroSection from "../components/landing/HeroSection";
import CapabilitiesSection from "../components/landing/CapabilitiesSection";
import HowItWorksSection from "../components/landing/HowItWorksSection";
import ModulesSection from "../components/landing/ModulesSection";
import WhyDifferentSection from "../components/landing/WhyDifferentSection";
import ComplianceSection from "../components/landing/ComplianceSection";
import StatusBand from "../components/landing/StatusBand";
import FaqSection from "../components/landing/FaqSection";
import LandingFooter from "../components/landing/LandingFooter";

/**
 * Landing Page Component
 * Modular enterprise landing page built with light design system guidelines.
 */
export default function Landing() {
  return (
    <div className="min-h-screen bg-canvas text-ink font-sans selection:bg-ink selection:text-white">
      {/* 1. Header / Navbar */}
      <LandingNavbar />

      <main>
        {/* 1 & 2. Hero Section + App Preview Mock + Proof Strip */}
        <HeroSection />

        {/* 3. Section: Built for modern lending teams */}
        <CapabilitiesSection />

        {/* 4. Section: How TARA works */}
        <HowItWorksSection />

        {/* 5. Section: One platform, every module */}
        <ModulesSection />

        {/* 6. Section: Why TARA is different */}
        <WhyDifferentSection />

        {/* 7. Section: Built for regulated banking */}
        <ComplianceSection />

        {/* 8. Status Band */}
        <StatusBand />

        {/* 9. FAQ Section */}
        <FaqSection />
      </main>

      {/* 10. Final CTA Band + Footer */}
      <LandingFooter />
    </div>
  );
}
