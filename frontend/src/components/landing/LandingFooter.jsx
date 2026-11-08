import React from "react";
import { Link } from "react-router-dom";
import Button from "../Button";

/**
 * LandingFooter Component
 * Renders the final conversion CTA band and institutional footer with blurred footer.png background.
 */
export default function LandingFooter() {
  return (
    <footer className="relative isolate overflow-hidden bg-canvas">
      {/* Background Image: light blur, top-aligned to preserve globe dome */}
      <div
        className="absolute inset-0 bg-cover bg-top bg-no-repeat pointer-events-none z-0 filter blur-[2px] opacity-90"
        style={{ backgroundImage: "url('/footer.png')" }}
      />
      {/* Smooth top vignette matching the above FAQ section canvas color (#f5f5f5) */}
      <div className="absolute top-0 inset-x-0 h-32 sm:h-48 bg-gradient-to-b from-[#f5f5f5] via-[#f5f5f5]/70 to-transparent pointer-events-none z-10" />

      {/* Final CTA Band */}
      <div className="relative z-20 py-16 lg:py-24 border-b border-hairline/60">
        <div className="max-w-[800px] mx-auto px-6 text-center">
          <h2 className="t-display-lg font-bold text-ink mb-4">
            Ready to see it on your own data?
          </h2>
          <p className="t-body-md text-body mb-8 font-sans">
            Create an isolated workspace in seconds.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <Button to="/signup" variant="primary" size="md">
              Create workspace
            </Button>
            <Button to="/login" variant="outline" size="md" className="bg-surface-card/85 backdrop-blur-xs">
              Sign in
            </Button>
          </div>
        </div>
      </div>

      {/* Main Footer */}
      <div className="relative z-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex flex-col sm:flex-row items-center gap-3 text-center sm:text-left">
          <Link to="/" className="flex items-center">
            <img src="/logo.png" alt="TARA" className="h-7 w-auto object-contain" />
          </Link>
          <span className="text-xs text-muted-soft hidden sm:inline">|</span>
          <p className="text-xs text-muted font-sans font-medium">
            TARA, Targeted Acquisition and Reach Agent
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-6 text-xs text-body font-sans">
          <a href="#capabilities" className="hover:text-ink transition-colors">
            Capabilities
          </a>
          <a href="#how-it-works" className="hover:text-ink transition-colors">
            How it works
          </a>
          <a href="#modules" className="hover:text-ink transition-colors">
            Modules
          </a>
          <Link to="/login" className="hover:text-ink transition-colors">
            Sign in
          </Link>
          <Link to="/signup" className="hover:text-ink transition-colors font-medium text-ink">
            Create workspace
          </Link>
        </div>

        <div className="text-xs text-muted-soft font-sans">
          &copy; 2026. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
