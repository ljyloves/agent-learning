"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  { href: "/", label: "工作台", short: "台", exact: true },
  { href: "/paper-agent/tasks", label: "组卷任务", short: "卷" },
  { href: "/knowledge", label: "教师资料", short: "资" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/" className="brand" aria-label="返回 FlowGate 工作台">
          <span className="brand-mark" aria-hidden="true">FG</span>
          <span className="brand-copy">
            <strong>FlowGate</strong>
            <span>教师组卷工作台</span>
          </span>
        </Link>
        <p className="nav-label">主要功能</p>
        <nav className="primary-nav" aria-label="主要导航">
          {navigation.map((item) => {
            const active = item.exact
              ? pathname === item.href
              : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link${active ? " nav-link-active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                <span className="nav-icon" aria-hidden="true">{item.short}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-footer">高中生物 MVP</div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div>
            <div className="topbar-title">教师工作区</div>
            <div className="topbar-context">组卷、审核与文档输出</div>
          </div>
          <div className="teacher-chip" aria-label="当前角色：教师">
            <span>教师</span>
            <span className="teacher-avatar" aria-hidden="true">师</span>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
