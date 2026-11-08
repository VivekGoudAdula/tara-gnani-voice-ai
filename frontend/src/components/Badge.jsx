import React from "react";

/**
 * Editorial status badge: neutral surface-strong pill with a subtle semantic dot.
 * Uses .t-label typography token.
 */
export default function Badge({ variant = "default", dot = true, children, className = "" }) {
  const dotStyles = {
    default: "bg-muted",
    success: "bg-semantic-success",
    danger: "bg-semantic-error",
    warning: "bg-amber-600",
    info: "bg-sky-600",
    purple: "bg-indigo-600",
  };

  const selectedDot = dotStyles[variant] || dotStyles.default;

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full t-label bg-surface-strong text-body-strong border border-hairline ${className}`}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full mr-1.5 shrink-0 ${selectedDot}`} />}
      <span>{children}</span>
    </span>
  );
}
