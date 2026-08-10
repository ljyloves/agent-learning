import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "FlowGate",
  description: "Enterprise Secure Agent Workflow Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen flex flex-col">
        <header className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <Link href="/" className="text-xl font-bold tracking-tight">
              FlowGate
            </Link>
            <nav className="flex gap-6 text-sm">
              <Link href="/chat" className="hover:text-blue-600 transition-colors">
                对话
              </Link>
              <Link href="/knowledge" className="hover:text-blue-600 transition-colors">
                知识库
              </Link>
              <Link href="/tasks" className="hover:text-blue-600 transition-colors">
                任务
              </Link>
              <Link href="/admin" className="hover:text-blue-600 transition-colors">
                管理
              </Link>
            </nav>
          </div>
        </header>
        <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
