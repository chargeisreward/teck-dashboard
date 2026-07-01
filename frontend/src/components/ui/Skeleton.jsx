/**
 * Skeleton — 骨架屏加载
 *
 * Props:
 *   height: number (px) 或 '1em'
 *   width: number (px) 或 '100%'
 *   circle: boolean — 圆形头像/徽章
 *   className: string
 */
export default function Skeleton({ height = 16, width = "100%", circle = false, className = "" }) {
  const style = {
    height: typeof height === "number" ? `${height}px` : height,
    width: typeof width === "number" ? `${width}px` : width,
    borderRadius: circle ? "50%" : "var(--radius-md)",
  };

  return <div className={`ui-skeleton${className ? " " + className : ""}`} style={style} />;
}

/**
 * SkeletonCard — 卡片级骨架
 */
export function SkeletonCard({ lines = 3 }) {
  return (
    <div className="ui-skeleton-card">
      <Skeleton height={20} width="60%" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} height={14} width={i === lines - 1 ? "40%" : "100%"} />
      ))}
    </div>
  );
}

/**
 * SkeletonStatCards — stat cards 骨架
 */
export function SkeletonStatCards({ count = 4 }) {
  return (
    <div className="stats-grid">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="stat-card">
          <Skeleton height={14} width="50%" />
          <Skeleton height={32} width="70%" style={{ marginTop: 8 }} />
        </div>
      ))}
    </div>
  );
}
