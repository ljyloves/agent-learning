export default function AdminPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">后台管理</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="font-semibold mb-2">工具管理</h3>
          <p className="text-sm text-gray-400">注册、启用、禁用工具 — 待实现</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="font-semibold mb-2">审批管理</h3>
          <p className="text-sm text-gray-400">高风险操作人工审批 — 待实现</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="font-semibold mb-2">Trace 日志</h3>
          <p className="text-sm text-gray-400">执行链路追踪与成本统计 — 待实现</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="font-semibold mb-2">安全策略</h3>
          <p className="text-sm text-gray-400">Prompt Injection 检测与敏感信息过滤 — 待实现</p>
        </div>
      </div>
    </div>
  );
}
