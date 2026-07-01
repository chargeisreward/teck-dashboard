import Icon from "./Icon";

/**
 * ErrorState — 错误状态
 */
export default function ErrorState({ title = "加载失败", message = "请稍后重试", onRetry }) {
  return (
    <div className="ui-error-state">
      <Icon name="error" size={32} weight="fill" className="ui-error-state-icon" />
      <div className="ui-error-state-title">{title}</div>
      {message && <div className="ui-error-state-message">{message}</div>}
      {onRetry && (
        <button className="ui-error-state-retry" onClick={onRetry}>
          重试
        </button>
      )}
    </div>
  );
}
