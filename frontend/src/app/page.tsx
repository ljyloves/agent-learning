export default function HomePage() {
  return (
    <div className="space-y-10">
      <section className="text-center py-16">
        <h1 className="text-4xl font-bold mb-4">FlowGate</h1>
        <p className="text-lg text-gray-500 max-w-xl mx-auto">
          企业级安全 Agent 工作流平台 — 文档知识库、多 Agent 协作、工具调用、权限控制、链路追踪
        </p>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card
          href="/knowledge"
          title="知识库"
          desc="上传文档，基于 RAG 进行智能问答，引用来源可追溯"
        />
        <Card
          href="/tasks"
          title="任务中心"
          desc="多 Agent 协作执行复杂任务，展示每一步执行过程"
        />
        <Card
          href="/admin"
          title="后台管理"
          desc="工具注册、权限控制、审批管理、执行链路追踪"
        />
      </section>
    </div>
  );
}

function Card({ href, title, desc }: { href: string; title: string; desc: string }) {
  return (
    <a
      href={href}
      className="block p-6 bg-white rounded-lg border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all"
    >
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      <p className="text-sm text-gray-500">{desc}</p>
    </a>
  );
}
