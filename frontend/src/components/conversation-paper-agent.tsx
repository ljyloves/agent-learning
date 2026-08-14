"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import {
  commandConversation,
  createPaperConversation,
  getBiologyTaxonomy,
  getConversationPlan,
  getConversationStatus,
  getPaperConversationHistory,
  questionTypeLabels,
  submitConversationMessage,
  updateConversationPlan,
  type BiologyTaxonomy,
  type ConversationGraphResponse,
  type DifficultyQuota,
  type OptimizedPaperTaskCreate,
  type PaperConversationMessage,
} from "@/lib/paper-agent";

const STORAGE_KEY = "flowgate.paper-agent.conversation-id";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const POLL_INTERVAL_MS = 2_000;
const POLLING_STATUSES = new Set(["received", "checking_feasibility", "executing"]);
const CURRENT_SUMMARY_STATUSES = new Set([
  "received",
  "checking_feasibility",
  "awaiting_confirmation",
  "executing",
  "retryable",
]);
const initialQuotas: DifficultyQuota[] = [
  { question_type: "single_choice", difficulty_level: 2, count: 4, score_per_question: 5 },
  { question_type: "single_choice", difficulty_level: 3, count: 4, score_per_question: 5 },
  { question_type: "single_choice", difficulty_level: 4, count: 2, score_per_question: 5 },
];

function newId(_prefix: string) {
  return crypto.randomUUID();
}

function statusLabel(status?: string) {
  const labels: Record<string, string> = {
    received: "已收到",
    responded: "已回复",
    needs_input: "需要补充",
    form_fallback: "请使用表单",
    checking_feasibility: "正在检查题库",
    infeasible: "当前约束不可行",
    awaiting_confirmation: "等待确认",
    executing: "正在组卷",
    retryable: "可以重试",
    completed: "已生成",
    cancelled: "已取消",
    failed: "执行失败",
  };
  return status ? labels[status] ?? status : "等待输入";
}

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : "操作失败，请稍后重试";
}

export function ConversationPaperAgent() {
  const [conversationId, setConversationId] = useState("");
  const [taxonomy, setTaxonomy] = useState<BiologyTaxonomy | null>(null);
  const [messages, setMessages] = useState<PaperConversationMessage[]>([]);
  const [graph, setGraph] = useState<ConversationGraphResponse | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [paperName, setPaperName] = useState("高一生物阶段练习");
  const [grade, setGrade] = useState("高一");
  const [examType, setExamType] = useState("阶段练习");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [moduleCode, setModuleCode] = useState("BIO-M1");
  const [quotas, setQuotas] = useState(initialQuotas);
  const [knowledgeCodes, setKnowledgeCodes] = useState<string[]>([]);
  const messageEndRef = useRef<HTMLDivElement>(null);

  const currentModule = taxonomy?.modules.find((item) => item.code === moduleCode) ?? null;
  const questionCount = quotas.reduce((sum, item) => sum + item.count, 0);
  const totalScore = quotas.reduce((sum, item) => sum + item.count * item.score_per_question, 0);
  const duplicateQuota = new Set(
    quotas.map((item) => `${item.question_type}:${item.difficulty_level}`),
  ).size !== quotas.length;
  const planValid = questionCount > 0
    && totalScore > 0
    && knowledgeCodes.length > 0
    && knowledgeCodes.length <= questionCount
    && !duplicateQuota;
  const pendingConfirmation = graph?.interrupted && graph.state.status === "awaiting_confirmation";
  const canRetry = graph?.interrupted && graph.state.retry_count > 0;

  const applyPlan = useCallback((plan: OptimizedPaperTaskCreate | null) => {
    if (!plan) return;
    setPaperName(plan.paper_info.paper_name);
    setGrade(plan.paper_info.grade);
    setExamType(plan.paper_info.exam_type);
    setDurationMinutes(plan.paper_info.duration_minutes);
    setModuleCode(plan.optimization.module_code);
    setQuotas(plan.optimization.difficulty_quotas);
    setKnowledgeCodes(plan.optimization.coverage.targets.map((target) => target.code));
  }, []);

  const refresh = useCallback(async (id: string) => {
    const [history, plan, status] = await Promise.all([
      getPaperConversationHistory(id),
      getConversationPlan(id),
      getConversationStatus(id),
    ]);
    setMessages(history.messages);
    setGraph(status);
    applyPlan(plan.plan);
  }, [applyPlan]);

  useEffect(() => {
    async function initialize() {
      setLoading(true);
      setError("");
      try {
        const loadedTaxonomy = await getBiologyTaxonomy();
        setTaxonomy(loadedTaxonomy);
        const storedId = localStorage.getItem(STORAGE_KEY);
        let id = storedId && UUID_PATTERN.test(storedId)
          ? storedId
          : newId("conversation");
        try {
          await getPaperConversationHistory(id);
        } catch (requestError) {
          if (!(requestError instanceof ApiError) || requestError.status !== 404) throw requestError;
          id = newId("conversation");
          await createPaperConversation(id);
          localStorage.setItem(STORAGE_KEY, id);
        }
        setConversationId(id);
        const defaultModule = loadedTaxonomy.modules.find((item) => item.code === "BIO-M1")
          ?? loadedTaxonomy.modules[0];
        if (defaultModule) {
          setModuleCode(defaultModule.code);
          setKnowledgeCodes(defaultModule.knowledge_points.map((point) => point.code));
        }
        await refresh(id);
      } catch (requestError) {
        setError(errorMessage(requestError));
      } finally {
        setLoading(false);
      }
    }
    void initialize();
  }, [refresh]);

  useEffect(() => {
    if (!conversationId || !graph || !POLLING_STATUSES.has(graph.state.status)) return;
    const timer = window.setInterval(() => {
      void refresh(conversationId).catch((requestError) => setError(errorMessage(requestError)));
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [conversationId, graph, refresh]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages, graph]);

  useEffect(() => {
    if (!currentModule) return;
    const available = new Set(currentModule.knowledge_points.map((point) => point.code));
    setKnowledgeCodes((codes) => {
      const retained = codes.filter((code) => available.has(code));
      return retained.length ? retained : currentModule.knowledge_points.map((point) => point.code);
    });
  }, [currentModule]);

  async function sendMessage(event: React.FormEvent) {
    event.preventDefault();
    const content = input.trim();
    if (!content || !conversationId || working || pendingConfirmation) return;
    setWorking(true);
    setError("");
    setInput("");
    try {
      setGraph(await submitConversationMessage(conversationId, newId("message"), content));
      await refresh(conversationId);
    } catch (requestError) {
      setInput(content);
      setError(errorMessage(requestError));
    } finally {
      setWorking(false);
    }
  }

  async function runCommand(action: "confirm" | "cancel" | "retry") {
    if (!conversationId || working) return;
    setWorking(true);
    setError("");
    try {
      setGraph(await commandConversation(conversationId, action));
      await refresh(conversationId);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setWorking(false);
    }
  }

  async function saveStructuredPlan(event: React.FormEvent) {
    event.preventDefault();
    if (!conversationId || !planValid || working || pendingConfirmation) return;
    const plan: OptimizedPaperTaskCreate = {
      paper_info: {
        paper_name: paperName.trim(),
        grade,
        exam_type: examType,
        duration_minutes: durationMinutes,
      },
      optimization: {
        module_code: moduleCode,
        question_count: questionCount,
        total_score: totalScore,
        difficulty_quotas: quotas,
        coverage: {
          targets: knowledgeCodes.map((code) => ({ code, minimum_count: 1 })),
          minimum_coverage_rate: 1,
        },
        diversity: {
          minimum_distinct_knowledge_points: Math.min(knowledgeCodes.length, questionCount),
          minimum_distinct_core_competencies: Math.min(2, questionCount),
          minimum_distinct_sources: 1,
          maximum_questions_per_knowledge_point: Math.max(
            1,
            Math.ceil(questionCount / knowledgeCodes.length) + 1,
          ),
          maximum_questions_per_source: questionCount,
          semantic_similarity_threshold: 1,
        },
        exclude_question_ids: [],
        random_seed: 36,
      },
    };
    setWorking(true);
    setError("");
    try {
      setGraph(await updateConversationPlan(conversationId, newId("form"), plan));
      await refresh(conversationId);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setWorking(false);
    }
  }

  function updateQuota(index: number, patch: Partial<DifficultyQuota>) {
    setQuotas((items) => items.map((item, itemIndex) => (
      itemIndex === index ? { ...item, ...patch } : item
    )));
  }

  const systemSummary = useMemo(() => {
    const report = graph?.state.reports.at(-1);
    return report?.summary ?? "描述试卷需求后，系统会整理参数并检查题库。";
  }, [graph]);

  if (loading) {
    return <div className="conversation-loading skeleton" aria-label="对话组卷加载中" />;
  }

  return (
    <div className="page-stack conversation-page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">高中生物</p>
          <h1>对话式组卷</h1>
          <p className="page-description">用自然语言说明需求，确认结构化方案后再执行组卷。</p>
        </div>
        <div className="heading-actions">
          <span className={`status-badge status-${graph?.state.status ?? "idle"}`}>
            {statusLabel(graph?.state.status)}
          </span>
          <Link href="/paper-agent/tasks/new" className="button button-secondary">使用完整表单</Link>
        </div>
      </section>

      {error && (
        <section className="inline-error" role="alert">
          <div><strong>本次操作未完成</strong><p>{error}</p></div>
          <button type="button" className="button button-secondary" onClick={() => void refresh(conversationId)}>
            刷新状态
          </button>
        </section>
      )}

      <div className="conversation-workspace">
        <section className="conversation-panel" aria-label="组卷对话">
          <header className="conversation-panel-heading">
            <div><strong>需求对话</strong><span>{statusLabel(graph?.state.status)}</span></div>
            <code>{conversationId.slice(-8)}</code>
          </header>
          <div className="message-list" aria-live="polite">
            {messages.length === 0 && (
              <div className="conversation-empty">
                <strong>开始描述您的试卷</strong>
                <p>例如：高一分子与细胞单元测验，10 道单选题，覆盖细胞结构和物质运输。</p>
              </div>
            )}
            {messages.map((message) => (
              <article key={message.message_id} className={`message message-${message.role}`}>
                <span>{message.role === "teacher" ? "教师" : "FlowGate"}</span>
                <p>{message.content}</p>
              </article>
            ))}
            {graph && CURRENT_SUMMARY_STATUSES.has(graph.state.status) && (
              <article className="message message-system">
                <span>当前处理</span>
                <p>{systemSummary}</p>
              </article>
            )}
            <div ref={messageEndRef} />
          </div>
          <form className="message-composer" onSubmit={sendMessage}>
            <label htmlFor="paper-agent-message" className="sr-only">输入组卷需求</label>
            <textarea
              id="paper-agent-message"
              value={input}
              maxLength={20_000}
              disabled={working || Boolean(pendingConfirmation)}
              onChange={(event) => setInput(event.target.value)}
              placeholder={pendingConfirmation ? "请先确认或取消当前方案" : "输入组卷需求或继续修改方案"}
            />
            <button type="submit" className="button button-primary" disabled={!input.trim() || working || Boolean(pendingConfirmation)}>
              {working ? "处理中" : "发送"}
            </button>
          </form>
        </section>

        <form className="plan-panel" onSubmit={saveStructuredPlan}>
          <header className="conversation-panel-heading">
            <div><strong>组卷方案</strong><span>版本 {graph?.state.plan_version ?? 0}</span></div>
            <span>{questionCount} 题 · {totalScore} 分</span>
          </header>
          <div className="plan-fields">
            <label className="field field-full"><span>试卷名称</span><input value={paperName} maxLength={200} onChange={(event) => setPaperName(event.target.value)} /></label>
            <label className="field"><span>年级</span><select value={grade} onChange={(event) => setGrade(event.target.value)}><option>高一</option><option>高二</option><option>高三</option></select></label>
            <label className="field"><span>考试类型</span><select value={examType} onChange={(event) => setExamType(event.target.value)}><option>阶段练习</option><option>单元测验</option><option>期中考试</option><option>期末考试</option><option>模拟考试</option></select></label>
            <label className="field"><span>时长（分钟）</span><input type="number" min={10} max={300} value={durationMinutes} onChange={(event) => setDurationMinutes(Number(event.target.value))} /></label>
            <label className="field"><span>课程模块</span><select value={moduleCode} onChange={(event) => setModuleCode(event.target.value)}>{taxonomy?.modules.map((module) => <option key={module.code} value={module.code}>{module.name}</option>)}</select></label>
          </div>

          <div className="plan-block">
            <div className="plan-block-heading"><strong>题型与难度</strong><button type="button" className="text-button" onClick={() => setQuotas((items) => [...items, { question_type: "short_answer", difficulty_level: 3, count: 1, score_per_question: 10 }])}>添加</button></div>
            <div className="compact-quota-list">
              {quotas.map((quota, index) => (
                <div key={`${index}-${quota.question_type}-${quota.difficulty_level}`}>
                  <select aria-label={`第 ${index + 1} 行题型`} value={quota.question_type} onChange={(event) => updateQuota(index, { question_type: event.target.value as DifficultyQuota["question_type"] })}>{Object.entries(questionTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
                  <select aria-label={`第 ${index + 1} 行难度`} value={quota.difficulty_level} onChange={(event) => updateQuota(index, { difficulty_level: Number(event.target.value) })}>{[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value} 级</option>)}</select>
                  <input aria-label={`第 ${index + 1} 行数量`} type="number" min={1} max={1000} value={quota.count} onChange={(event) => updateQuota(index, { count: Number(event.target.value) })} />
                  <input aria-label={`第 ${index + 1} 行分值`} type="number" min={1} max={100} value={quota.score_per_question} onChange={(event) => updateQuota(index, { score_per_question: Number(event.target.value) })} />
                  <button type="button" className="icon-action" aria-label={`删除第 ${index + 1} 行`} disabled={quotas.length === 1} onClick={() => setQuotas((items) => items.filter((_, itemIndex) => itemIndex !== index))}>×</button>
                </div>
              ))}
            </div>
            {duplicateQuota && <p className="plan-error">同一题型和难度不能重复。</p>}
          </div>

          <div className="plan-block">
            <div className="plan-block-heading"><strong>知识点</strong><span>{knowledgeCodes.length} 项</span></div>
            <div className="compact-knowledge-list">
              {currentModule?.knowledge_points.map((point) => (
                <label key={point.code} className={knowledgeCodes.includes(point.code) ? "selected" : ""}>
                  <input type="checkbox" checked={knowledgeCodes.includes(point.code)} onChange={() => setKnowledgeCodes((codes) => codes.includes(point.code) ? codes.filter((code) => code !== point.code) : [...codes, point.code])} />
                  <span>{point.name}</span>
                </label>
              ))}
            </div>
          </div>

          {graph?.state.status === "completed" && graph.state.paper_job_id ? (
            <div className="plan-actions plan-actions-complete">
              <Link href={`/paper-agent/tasks/${graph.state.paper_job_id}`} className="button button-primary">进入审核</Link>
            </div>
          ) : pendingConfirmation ? (
            <div className="plan-actions">
              <button type="button" className="button button-secondary" disabled={working} onClick={() => void runCommand("cancel")}>取消</button>
              <button type="button" className="button button-primary" disabled={working} onClick={() => void runCommand(canRetry ? "retry" : "confirm")}>{canRetry ? "确认重试" : "确认并组卷"}</button>
            </div>
          ) : (
            <div className="plan-actions">
              <button type="submit" className="button button-secondary" disabled={!planValid || working}>检查并准备确认</button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
