import Link from "next/link";
import { ServiceStatus } from "@/components/service-status";

const workflow = [
  { label: "组卷配置", detail: "题型、分值、难度与知识点" },
  { label: "试卷审核", detail: "预览题目、答案与质量信息" },
  { label: "调整定稿", detail: "锁题、换题与重新组卷" },
  { label: "文档导出", detail: "学生卷、解析卷与答题卡" },
];

export default function HomePage() {
  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">高中生物</p>
          <h1>教师组卷工作台</h1>
          <p className="page-description">
            从组卷任务进入审核流程，完成调整后统一导出试卷文档。
          </p>
        </div>
        <Link href="/paper-agent/tasks" className="button button-primary">
          进入任务中心 <span aria-hidden="true">→</span>
        </Link>
      </section>

      <ServiceStatus />

      <section className="workspace-section" aria-labelledby="workflow-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">工作流程</p>
            <h2 id="workflow-title">组卷进度</h2>
          </div>
          <span className="quiet-label">4 个阶段</span>
        </div>
        <ol className="workflow-list">
          {workflow.map((item, index) => (
            <li key={item.label}>
              <span className="workflow-index">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <strong>{item.label}</strong>
                <p>{item.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="workspace-section" aria-labelledby="recent-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">最近任务</p>
            <h2 id="recent-title">待处理</h2>
          </div>
          <Link href="/paper-agent/tasks" className="text-link">
            查看全部
          </Link>
        </div>
        <div className="compact-empty">
          <div className="empty-mark" aria-hidden="true">01</div>
          <div>
            <strong>暂无组卷任务</strong>
            <p>任务创建后会显示在这里。</p>
          </div>
        </div>
      </section>
    </div>
  );
}
