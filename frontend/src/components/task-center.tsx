"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import {
  listOptimizedTasks,
  reviewStatusLabels,
  taskStatusLabels,
  type OptimizedTaskListResponse,
} from "@/lib/paper-agent";

const PAGE_SIZE = 8;

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function TaskCenter() {
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<OptimizedTaskListResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await listOptimizedTasks({ page, pageSize: PAGE_SIZE, keyword, status, reviewStatus }));
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : "任务列表加载失败");
    } finally {
      setLoading(false);
    }
  }, [keyword, page, reviewStatus, status]);

  useEffect(() => {
    void load();
  }, [load]);

  function applyKeyword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setKeyword(keywordInput.trim());
  }

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">教师组卷</p>
          <h1>组卷任务</h1>
          <p className="page-description">查看组卷进度，快速进入待审核试卷继续处理。</p>
        </div>
        <Link href="/paper-agent/tasks/new" className="button button-primary">
          新建组卷 <span aria-hidden="true">+</span>
        </Link>
      </section>

      <section className="task-toolbar" aria-label="任务筛选">
        <form className="search-form" onSubmit={applyKeyword}>
          <label className="sr-only" htmlFor="task-keyword">搜索试卷名称或任务编号</label>
          <input
            id="task-keyword"
            value={keywordInput}
            onChange={(event) => setKeywordInput(event.target.value)}
            placeholder="搜索试卷名称或任务编号"
          />
          <button type="submit" className="button button-secondary">搜索</button>
        </form>
        <div className="filter-group">
          <label>
            <span>执行状态</span>
            <select value={status} onChange={(event) => { setPage(1); setStatus(event.target.value); }}>
              <option value="">全部</option>
              {Object.entries(taskStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label>
            <span>审核状态</span>
            <select value={reviewStatus} onChange={(event) => { setPage(1); setReviewStatus(event.target.value); }}>
              <option value="">全部</option>
              {Object.entries(reviewStatusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        </div>
      </section>

      {loading ? (
        <section className="task-table-shell" aria-busy="true" aria-label="任务列表加载中">
          <div className="task-table-loading skeleton" />
        </section>
      ) : error ? (
        <section className="inline-error" role="alert">
          <div><strong>无法加载任务列表</strong><p>{error}</p></div>
          <button type="button" className="button button-secondary" onClick={() => void load()}>重新加载</button>
        </section>
      ) : data && data.items.length > 0 ? (
        <section className="task-table-shell">
          <div className="table-scroll">
            <table className="task-table">
              <thead><tr><th>试卷</th><th>规模</th><th>执行状态</th><th>审核状态</th><th>更新时间</th><th><span className="sr-only">操作</span></th></tr></thead>
              <tbody>
                {data.items.map((task) => (
                  <tr key={task.job_id}>
                    <td><strong>{task.paper_name}</strong><span>{task.grade} · {task.exam_type} · {task.duration_minutes} 分钟</span><code>{task.job_id.slice(0, 8)}</code></td>
                    <td>{task.question_count} 题<br /><span>{task.total_score} 分</span></td>
                    <td><span className={`status-badge status-${task.status}`}>{taskStatusLabels[task.status]}</span></td>
                    <td>{reviewStatusLabels[task.review_status]}</td>
                    <td>{formatDate(task.updated_at)}</td>
                    <td><Link className="row-action" href={`/paper-agent/tasks/${task.job_id}`}>{task.awaiting_teacher ? "继续审核" : "查看"} →</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination">
            <span>共 {data.total} 项，第 {data.page}/{Math.max(data.pages, 1)} 页</span>
            <div><button type="button" className="button button-secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>上一页</button><button type="button" className="button button-secondary" disabled={data.pages === 0 || page >= data.pages} onClick={() => setPage((value) => value + 1)}>下一页</button></div>
          </div>
        </section>
      ) : (
        <section className="full-empty">
          <div><div className="empty-mark" aria-hidden="true">01</div><h2>暂无符合条件的任务</h2><p>{keyword || status || reviewStatus ? "调整筛选条件后重试，或创建一项新任务。" : "创建第一项组卷任务后会显示在这里。"}</p><Link href="/paper-agent/tasks/new" className="button button-primary empty-action">新建组卷</Link></div>
        </section>
      )}
    </div>
  );
}
