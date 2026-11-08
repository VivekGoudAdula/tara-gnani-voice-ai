import React from "react";

/**
 * Editorial Light Card component.
 * White surface, 1px hairline border, 16px radius, 24px padding (p-6), optional hover soft shadow.
 */
export default function Card({
  children,
  className = "",
  hoverable = false,
  ...props
}) {
  return (
    <div
      className={`bg-surface-card border border-hairline rounded-xl p-6 ${
        hoverable ? "hover:shadow-soft transition-shadow" : "shadow-soft"
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
