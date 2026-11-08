import React from "react";
import { Link } from "react-router-dom";
import Button from "../Button";

export default function LandingNavbar() {
  return (
    <header className="absolute top-0 inset-x-0 z-40 bg-transparent h-16 sm:h-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-full flex items-center justify-between">
        <Link to="/" className="flex items-center">
          <img
            src="/logo.png"
            alt="TARA"
            className="h-8 sm:h-10 w-auto object-contain"
          />
        </Link>
        <nav className="hidden lg:flex items-center gap-6 xl:gap-8">
          <a href="#capabilities" className="text-sm text-ink/80 hover:text-ink transition-colors font-medium">
            Capabilities
          </a>
          <a href="#how-it-works" className="text-sm text-ink/80 hover:text-ink transition-colors font-medium">
            How it works
          </a>
          <a href="#modules" className="text-sm text-ink/80 hover:text-ink transition-colors font-medium">
            Modules
          </a>
          <a href="#compliance" className="text-sm text-ink/80 hover:text-ink transition-colors font-medium">
            Compliance
          </a>
          <a href="#faq" className="text-sm text-ink/80 hover:text-ink transition-colors font-medium">
            FAQ
          </a>
        </nav>
        <div className="flex items-center gap-2 sm:gap-3">
          <Button to="/login" variant="outline" size="sm" className="bg-surface-card/70 backdrop-blur-xs hover:bg-surface-card text-xs sm:text-sm">
            Sign in
          </Button>
          <Button to="/signup" variant="primary" size="sm" className="hidden sm:inline-flex text-xs sm:text-sm">
            Create workspace
          </Button>
        </div>
      </div>
    </header>
  );
}
