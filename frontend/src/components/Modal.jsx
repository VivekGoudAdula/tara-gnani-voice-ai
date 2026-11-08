import React, { useEffect } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import Button from "./Button";

/**
 * Centered dialog box modal replacing side drawers across the application.
 * Portaled to document.body so the backdrop blur extends to the very top and all edges of the viewport.
 * Features an opaque card surface, dark backdrop overlay, and escape key handling.
 */
export default function Modal({ isOpen, onClose, title, subtitle, children, footer, maxWidth = "max-w-2xl" }) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.body.style.overflow = "unset";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const modalContent = (
    <div
      id="modal-backdrop"
      className="fixed inset-0 z-[100] overflow-y-auto bg-ink/60 backdrop-blur-sm flex items-center justify-center p-4 sm:p-6"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className={`relative w-full ${maxWidth} bg-surface-card border border-hairline rounded-xl shadow-soft overflow-hidden my-auto flex flex-col max-h-[90vh]`}>
        {/* Header */}
        <div className="px-6 py-5 border-b border-hairline flex items-center justify-between shrink-0 bg-surface-card">
          <div>
            <h3 className="t-display-sm text-ink">{title}</h3>
            {subtitle && <p className="t-caption text-muted mt-0.5">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-full text-muted hover:text-ink hover:bg-surface-strong transition-colors"
            title="Close dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5 bg-surface-card t-table">
          {children}
        </div>

        {/* Footer */}
        {footer !== undefined ? (
          footer
        ) : (
          <div className="px-6 py-4 border-t border-hairline bg-canvas-soft flex justify-end shrink-0">
            <Button
              size="sm"
              variant="primary"
              onClick={onClose}
            >
              Close
            </Button>
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
