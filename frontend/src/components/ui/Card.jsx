import { forwardRef } from "react";

/**
 * Card — 统一卡片容器
 *
 * Usage:
 *   <Card>content</Card>
 *   <Card className="extra" hover>content</Card>
 */
const Card = forwardRef(function Card(
  { children, className = "", hover = false, padding = "normal", as: Tag = "div", ...props },
  ref
) {
  const paddingClass =
    padding === "none" ? "" : padding === "loose" ? " card-padded-loose" : " card-padded";
  const hoverClass = hover ? " card-hover" : "";
  return (
    <Tag ref={ref} className={`ui-card${paddingClass}${hoverClass}${className ? " " + className : ""}`} {...props}>
      {children}
    </Tag>
  );
});

export default Card;
