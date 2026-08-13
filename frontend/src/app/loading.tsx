export default function Loading() {
  return (
    <div className="loading-page" aria-label="页面加载中" aria-busy="true">
      <div className="skeleton loading-line" />
      <div className="skeleton loading-panel" />
      <div className="skeleton loading-panel" />
    </div>
  );
}
