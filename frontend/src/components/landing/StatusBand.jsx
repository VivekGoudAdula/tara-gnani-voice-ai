import React from "react";

/**
 * StatusBand Component
 * Displays the current deployment status and channel roadmap.
 */
export default function StatusBand() {
  return (
    <div className="border-y border-hairline bg-surface-base/80 py-4 px-6">
      <div className="max-w-[1200px] mx-auto flex items-center justify-center gap-2.5 text-xs text-body font-sans">
        <span className="flex h-2 w-2 relative">
          <span className="relative inline-flex rounded-full h-2 w-2 bg-semantic-success" />
        </span>
        <span className="font-medium text-ink">
          Voice outreach is live.
        </span>
        <span className="text-muted-soft">|</span>
        <span className="text-muted">
          WhatsApp, SMS and Email are on the roadmap.
        </span>
      </div>
    </div>
  );
}
