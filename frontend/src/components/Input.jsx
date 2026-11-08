import React, { forwardRef } from "react";

/**
 * Standard input component: 44px height, 8px radius, 1px hairline-strong border, 2px ink border on focus.
 */
export const Input = forwardRef(function Input(
  { className = "", ...props },
  ref
) {
  return (
    <input
      ref={ref}
      className={`input-base ${className}`}
      {...props}
    />
  );
});

export default Input;
