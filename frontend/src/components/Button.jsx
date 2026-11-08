import React from "react";
import { Link } from "react-router-dom";

/**
 * Editorial Light Button component.
 * Variants:
 *  - primary: ink pill (primary token, white text, rounded-full)
 *  - outline: hairline-strong border, rounded-full
 *  - text: inline link
 * Sizes:
 *  - md: 40px height
 *  - sm: 32px height
 */
export default function Button({
  variant = "primary",
  size = "md",
  to,
  href,
  children,
  className = "",
  disabled = false,
  type = "button",
  onClick,
  ...props
}) {
  const baseClasses =
    "inline-flex items-center justify-center gap-2 t-button transition-colors select-none";

  const sizeClasses = {
    md: "h-[40px] px-5 rounded-full",
    sm: "h-[32px] px-3.5 rounded-full",
  };

  const variantClasses = {
    primary: "btn-primary disabled:opacity-50 disabled:cursor-not-allowed",
    outline: "btn-outline disabled:opacity-40 disabled:cursor-not-allowed",
    text:
      "text-body hover:text-ink underline-offset-4 hover:underline !h-auto !px-0 disabled:opacity-40",
  };

  const combinedClass =
    variant === "text"
      ? `${baseClasses} ${variantClasses.text} ${className}`
      : `${baseClasses} ${sizeClasses[size] || sizeClasses.md} ${variantClasses[variant] || variantClasses.primary} ${className}`;

  if (to) {
    return (
      <Link to={to} className={combinedClass} {...props}>
        {children}
      </Link>
    );
  }

  if (href) {
    return (
      <a href={href} className={combinedClass} {...props}>
        {children}
      </a>
    );
  }

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={combinedClass}
      {...props}
    >
      {children}
    </button>
  );
}
