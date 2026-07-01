import { forwardRef } from "react";

/**
 * Button — 统一按钮
 *
 * Variants: primary | secondary | ghost | danger
 * Sizes: sm | md
 */
const Button = forwardRef(function Button(
  {
    children,
    variant = "primary",
    size = "md",
    className = "",
    isLoading = false,
    disabled = false,
    ...props
  },
  ref
) {
  const baseClass = "ui-button";
  const variantClass = ` ui-button-${variant}`;
  const sizeClass = ` ui-button-${size}`;
  const loadingClass = isLoading ? " ui-button-loading" : "";
  const disabledClass = disabled || isLoading ? " ui-button-disabled" : "";

  return (
    <button
      ref={ref}
      className={`${baseClass}${variantClass}${sizeClass}${loadingClass}${disabledClass}${className ? " " + className : ""}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && <span className="ui-button-spinner" />}
      <span className={isLoading ? "ui-button-text-hidden" : ""}>{children}</span>
    </button>
  );
});

export default Button;
