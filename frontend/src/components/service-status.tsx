"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, healthCheck, type HealthResponse } from "@/lib/api";

type RequestState =
  | { status: "loading" }
  | { status: "online"; data: HealthResponse }
  | { status: "error"; message: string };

export function ServiceStatus() {
  const [state, setState] = useState<RequestState>({ status: "loading" });

  const check = useCallback(async () => {
    setState({ status: "loading" });
    try {
      const data = await healthCheck();
      if (data.status !== "healthy") {
        setState({ status: "error", message: "后端服务部分组件不可用" });
        return;
      }
      setState({ status: "online", data });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "无法连接后端服务";
      setState({ status: "error", message });
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  if (state.status === "loading") {
    return (
      <div className="status-strip" aria-live="polite" aria-busy="true">
        <div className="status-main">
          <span className="status-dot" />
          <div className="status-copy">
            <strong>正在连接 FlowGate 服务</strong>
            <span>检查后端与依赖服务状态</span>
          </div>
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="status-strip status-error" role="alert">
        <div className="status-main">
          <span className="status-dot" />
          <div className="status-copy">
            <strong>服务连接失败</strong>
            <span>{state.message}</span>
          </div>
        </div>
        <button type="button" className="status-action" onClick={() => void check()}>
          重新检查
        </button>
      </div>
    );
  }

  return (
    <div className="status-strip status-online" aria-live="polite">
      <div className="status-main">
        <span className="status-dot" />
        <div className="status-copy">
          <strong>FlowGate 服务正常</strong>
          <span>{state.data.service} 后端及依赖服务已连接</span>
        </div>
      </div>
      <span className="quiet-label">可开始组卷</span>
    </div>
  );
}
