/**
 * Badge — 统一徽章
 *
 * Variants: default | success | error | warning | accent
 */
export default function Badge({ children, variant = "default", className = "", dotColor, ...props }) {
  const baseClass = "ui-badge";
  const variantClass = ` ui-badge-${variant}`;

  return (
    <span
      className={`${baseClass}${variantClass}${className ? " " + className : ""}`}
      {...props}
    >
      {dotColor && <span className="ui-badge-dot" style={{ backgroundColor: dotColor }} />}
      {children}
    </span>
  );
}
