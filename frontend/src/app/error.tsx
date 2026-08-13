"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <section className="error-panel" role="alert">
      <p className="eyebrow">页面异常</p>
      <h1>暂时无法显示当前内容</h1>
      <p>请重试当前操作。如果问题持续存在，可返回工作台检查服务连接状态。</p>
      <div className="error-actions">
        <button type="button" className="button button-primary" onClick={reset}>
          重新加载
        </button>
        <Link href="/" className="button button-secondary">返回工作台</Link>
      </div>
    </section>
  );
}
