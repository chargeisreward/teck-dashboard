import Icon from "./Icon";

/**
 * EmptyState — 空状态
 */
export default function EmptyState({ icon = "info", title = "暂无数据", description = "" }) {
  return (
    <div className="ui-empty-state">
      <Icon name={icon} size={32} weight="light" className="ui-empty-state-icon" />
      <div className="ui-empty-state-title">{title}</div>
      {description && <div className="ui-empty-state-desc">{description}</div>}
    </div>
  );
}
