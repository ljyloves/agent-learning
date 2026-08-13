"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import {
  downloadTaskExport,
  getQuestion,
  getOptimizedTask,
  questionTypeLabels,
  reassembleTask,
  replaceTaskQuestion,
  reviewStatusLabels,
  reviewTask,
  taskStatusLabels,
  updateTaskLocks,
  type OptimizedExportDocument,
  type OptimizedExportFormat,
  type OptimizedQuestion,
  type OptimizedTaskResponse,
  type QuestionDetail,
  type QuestionImage,
} from "@/lib/paper-agent";

const REVIEWER = "teacher";

type Confirmation =
  | { kind: "replace"; question: OptimizedQuestion; replacementId?: string }
  | { kind: "reassemble" };

const exportButtons: Array<{
  label: string;
  document: OptimizedExportDocument;
  format: OptimizedExportFormat;
}> = [
  { label: "学生卷 DOCX", document: "student", format: "docx" },
  { label: "教师解析 DOCX", document: "teacher-answer", format: "docx" },
  { label: "答题卡 DOCX", document: "answer-sheet", format: "docx" },
  { label: "学生卷 PDF", document: "student", format: "pdf" },
  { label: "教师解析 PDF", document: "teacher-answer", format: "pdf" },
  { label: "答题卡 PDF", document: "answer-sheet", format: "pdf" },
];

function difficultyLabel(level: number) {
  return ["", "很容易", "容易", "中等", "较难", "困难"][level] ?? `难度 ${level}`;
}

function questionNumber(sectionIndex: number, index: number) {
  return `${sectionIndex + 1}-${index + 1}`;
}

function imageUrl(image: QuestionImage) {
  if (image.url) return image.url;
  if (image.storage_uri?.startsWith("http")) return image.storage_uri;
  if (image.uri?.startsWith("http")) return image.uri;
  return image.resource_id
    ? `/api/paper-agent/resources/${encodeURIComponent(image.resource_id)}/content`
    : null;
}

function actionError(error: unknown, fallback: string) {
  if (!(error instanceof ApiError)) return fallback;
  const detail = error.details;
  if (detail && typeof detail === "object" && "detail" in detail) {
    const value = (detail as { detail?: unknown }).detail;
    if (value && typeof value === "object" && "code" in value) {
      if ((value as { code?: unknown }).code === "NO_FEASIBLE_PAPER") {
        return "当前题库没有同时满足全部约束的候选题。请解锁部分题目，或返回组卷配置放宽知识点、难度或来源约束。";
      }
    }
  }
  const message = error.message.toLowerCase();
  if (message.includes("locked") || message.includes("all selected questions")) {
    return "当前操作会影响锁定题。请先解锁需要调整的题目，再重新尝试。";
  }
  if (message.includes("required") || message.includes("unavailable")) {
    return "指定替代题不满足当前试卷约束。请清空题目 ID 使用自动换题，或选择同题型、同难度且覆盖要求一致的题目。";
  }
  if (message.includes("approved")) {
    return "仅审核通过并定稿的试卷可以导出。请先完成教师审核。";
  }
  if (message.includes("explanation is missing")) {
    return "当前试卷中有题目缺少解析，无法生成教师解析卷。请换题或补充题目解析后再通过审核。";
  }
  if (message.includes("answer is missing")) {
    return "当前试卷中有题目缺少答案。请换题或补充答案后再通过审核。";
  }
  if (message.includes("knowledge points are missing")) {
    return "当前试卷中有题目缺少知识点标注。请完成标注或换题后再通过审核。";
  }
  if (message.includes("resource") || message.includes("image")) {
    return "当前试卷引用的题图或资源不可用。请修复资源或换题后再通过审核。";
  }
  if (message.includes("template")) {
    return "文档模板当前不可用，请检查模板路径与文件后重试。";
  }
  return error.message || fallback;
}

function AnswerValue({ answer }: { answer: QuestionDetail["answer"] }) {
  if (answer == null) return <span className="detail-empty">未提供</span>;
  return <span>{Array.isArray(answer) ? answer.join("；") : answer}</span>;
}

function QuestionContent({ detail, showAnswer }: { detail: QuestionDetail; showAnswer: boolean }) {
  return (
    <div className="question-content">
      <p className="question-stem">{detail.stem}</p>
      {detail.images.length > 0 && (
        <div className="question-images">
          {detail.images.map((image, index) => {
            const src = imageUrl(image);
            return src ? (
              <figure key={`${image.resource_id ?? "image"}-${index}`}>
                <img src={src} alt={image.alt_text ?? image.caption ?? `题目图片 ${index + 1}`} />
                <figcaption>{image.caption}</figcaption>
              </figure>
            ) : null;
          })}
        </div>
      )}
      {detail.options.length > 0 && (
        <ol className="question-options" type="A">
          {detail.options.map((option) => (
            <li key={option.label}>
              <strong>{option.label}.</strong>
              <span>{option.content}</span>
              {option.images.map((image, index) => {
                const src = imageUrl(image);
                return src ? <img key={`${image.resource_id ?? "option-image"}-${index}`} src={src} alt={image.alt_text ?? image.caption ?? `选项 ${option.label} 图片`} /> : null;
              })}
            </li>
          ))}
        </ol>
      )}
      {detail.subquestions.length > 0 && (
        <div className="subquestion-list">
          {detail.subquestions.map((child, index) => (
            <article key={`${child.id ?? "subquestion"}-${index}`}>
              <strong>（{index + 1}）</strong>
              <QuestionContent detail={child} showAnswer={showAnswer} />
            </article>
          ))}
        </div>
      )}
      {showAnswer && (
        <div className="answer-block">
          <p><strong>答案：</strong><AnswerValue answer={detail.answer} /></p>
          <p><strong>解析：</strong>{detail.explanation ?? <span className="detail-empty">未提供</span>}</p>
        </div>
      )}
    </div>
  );
}

export function TaskDetail({ jobId }: { jobId: string }) {
  const [task, setTask] = useState<OptimizedTaskResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [comment, setComment] = useState("");
  const [selectedQuestion, setSelectedQuestion] = useState<OptimizedQuestion | null>(null);
  const [questionDetail, setQuestionDetail] = useState<QuestionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [replacementId, setReplacementId] = useState("");
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);

  const load = useCallback(async () => {
    setError("");
    try {
      setTask(await getOptimizedTask(jobId));
    } catch (requestError) {
      setError(actionError(requestError, "任务加载失败"));
    }
  }, [jobId]);

  useEffect(() => { void load(); }, [load]);

  async function runAction(label: string, action: () => Promise<OptimizedTaskResponse>) {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      setTask(await action());
      setNotice(`${label}已完成，预览已同步更新`);
    } catch (requestError) {
      setError(actionError(requestError, `${label}失败，请稍后重试`));
    } finally {
      setBusy("");
    }
  }

  async function runDownload(
    label: string,
    document?: OptimizedExportDocument,
    format?: OptimizedExportFormat,
  ) {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await downloadTaskExport(jobId, document, format);
      setNotice(`${label}已开始下载`);
    } catch (requestError) {
      setError(actionError(requestError, `${label}失败，请稍后重试`));
    } finally {
      setBusy("");
    }
  }

  async function toggleLock(questionId: string) {
    if (!task) return;
    const locked = !task.locked_question_ids.includes(questionId);
    await runAction(locked ? "锁题" : "解锁", () => updateTaskLocks(jobId, { question_ids: [questionId], locked }));
  }

  async function confirmRevision() {
    if (!confirmation) return;
    const command = confirmation;
    setConfirmation(null);
    if (command.kind === "reassemble") {
      await runAction("重新组卷", () => reassembleTask(jobId, {
        reviewer: REVIEWER,
        comment: comment.trim() || undefined,
        random_seed: Math.floor(Date.now() / 1000),
      }));
      return;
    }
    await runAction("换题", async () => {
      const updated = await replaceTaskQuestion(jobId, {
        question_id: command.question.question_id,
        replacement_question_id: command.replacementId,
        reviewer: REVIEWER,
        comment: comment.trim() || undefined,
      });
      setSelectedQuestion(null);
      setQuestionDetail(null);
      setReplacementId("");
      return updated;
    });
  }

  async function selectQuestion(question: OptimizedQuestion) {
    setSelectedQuestion(question);
    setQuestionDetail(null);
    setDetailLoading(true);
    setError("");
    try {
      setQuestionDetail(await getQuestion(question.question_id));
    } catch (requestError) {
      setError(actionError(requestError, "题目详情加载失败"));
    } finally {
      setDetailLoading(false);
    }
  }

  if (error && !task) {
    return <section className="inline-error" role="alert"><div><strong>无法加载组卷任务</strong><p>{error}</p></div><button type="button" className="button button-secondary" onClick={() => void load()}>重试</button></section>;
  }
  if (!task) return <div className="loading-page" aria-busy="true"><div className="skeleton loading-line" /><div className="skeleton loading-panel" /></div>;

  const reviewable = task.awaiting_teacher && task.review_status === "pending";
  const allLocked = task.locked_question_ids.length === task.paper.question_count;
  return (
    <div className="page-stack">
      <section className="page-heading">
        <div><p className="eyebrow">任务详情</p><h1>{reviewable ? "试卷审核" : "组卷任务"}</h1><p className="page-description">任务编号 {task.job_id}</p></div>
        <Link href="/paper-agent/tasks" className="button button-secondary">返回任务中心</Link>
      </section>
      {error && <div className="inline-error" role="alert"><div><strong>操作未完成</strong><p>{error}</p></div><button type="button" className="button button-secondary" onClick={() => void load()}>刷新</button></div>}
      {notice && <div className="success-panel" role="status">{notice}</div>}
      <section className="detail-metrics">
        <div><span>执行状态</span><strong>{taskStatusLabels[task.status]}</strong></div>
        <div><span>审核状态</span><strong>{reviewStatusLabels[task.review_status]}</strong></div>
        <div><span>题目数量</span><strong>{task.paper.question_count} 题</strong></div>
        <div><span>已锁定</span><strong>{task.locked_question_ids.length} 题</strong></div>
        <div><span>试卷总分</span><strong>{task.paper.total_score} 分</strong></div>
      </section>

      <section className="workspace-section">
        <div className="section-heading"><div><p className="eyebrow">试卷预览</p><h2>题目结构与约束审计</h2></div><span className="quiet-label">覆盖率 {(task.paper.audit.coverage_rate * 100).toFixed(0)}%</span></div>
        <div className="question-preview-list">
          {task.paper.sections.map((section) => (
            <div key={section.section_index} className="question-section">
              <div className="question-section-heading"><strong>{String(section.section_index + 1).padStart(2, "0")} · {questionTypeLabels[section.question_type]}</strong><span>难度 {difficultyLabel(section.difficulty_level)} · {section.count} 题 · 每题 {section.score_per_question} 分</span></div>
              {section.questions.map((question, index) => {
                const locked = task.locked_question_ids.includes(question.question_id);
                return (
                  <article className={`question-row${locked ? " question-row-locked" : ""}`} key={question.question_id}>
                    <div className="question-row-number">{questionNumber(section.section_index, index)}</div>
                    <div className="question-row-main"><strong>{question.question_id}</strong><span>难度 {difficultyLabel(question.difficulty_level)} · 预计正确率 {(question.estimated_correct_rate * 100).toFixed(0)}% · {question.score} 分</span><small>知识点：{question.knowledge_point_codes.join("、")} · 来源：{question.source_id}</small></div>
                    <div className="question-row-actions">
                      <button type="button" className="button button-secondary" disabled={Boolean(busy)} onClick={() => void selectQuestion(question)}>{selectedQuestion?.question_id === question.question_id ? "已选中" : "查看详情"}</button>
                      {reviewable && <button type="button" className="text-button" disabled={Boolean(busy)} onClick={() => void toggleLock(question.question_id)}>{locked ? "解锁" : "锁题"}</button>}
                    </div>
                  </article>
                );
              })}
            </div>
          ))}
        </div>
      </section>

      {selectedQuestion && (
        <section className="workspace-section question-inspector">
          <div className="section-heading"><div><p className="eyebrow">题目详情</p><h2>{selectedQuestion.question_id}</h2></div><button type="button" className="text-button" onClick={() => { setSelectedQuestion(null); setQuestionDetail(null); }}>关闭</button></div>
          <div className="inspector-grid"><div><span>题型</span><strong>{questionTypeLabels[selectedQuestion.question_type]}</strong></div><div><span>难度</span><strong>{difficultyLabel(selectedQuestion.difficulty_level)}</strong></div><div><span>质量审核</span><strong className="quality-passed">已通过</strong><small>{selectedQuestion.quality_analysis_id}</small></div><div><span>难度分析编号</span><strong>{selectedQuestion.difficulty_analysis_id}</strong></div><p>知识点：{selectedQuestion.knowledge_point_codes.join("、")}</p><p>核心素养：{selectedQuestion.core_competency_codes.join("、")}</p>{questionDetail && <p className="inspector-source">来源：{questionDetail.source.name ?? questionDetail.source.title ?? selectedQuestion.source_id}</p>}</div>
          <div className="question-detail-body">{detailLoading ? <div className="skeleton loading-detail" aria-busy="true" /> : questionDetail ? <QuestionContent detail={questionDetail} showAnswer /> : <p className="detail-empty">暂无题目内容</p>}</div>
          {reviewable && (
            <div className="replace-panel">
              <div><strong>换题</strong><p>系统会再次校验题量、总分、难度与覆盖约束；已锁定题目不会被替换。</p></div>
              <div className="replace-controls">
                <input aria-label="指定替代题 ID" value={replacementId} onChange={(event) => setReplacementId(event.target.value)} placeholder="替代题 ID（可选）" disabled={Boolean(busy) || task.locked_question_ids.includes(selectedQuestion.question_id)} />
                <button type="button" className="button button-secondary" disabled={Boolean(busy) || !replacementId.trim() || task.locked_question_ids.includes(selectedQuestion.question_id)} onClick={() => setConfirmation({ kind: "replace", question: selectedQuestion, replacementId: replacementId.trim() })}>指定换题</button>
                <button type="button" className="button button-primary" disabled={Boolean(busy) || task.locked_question_ids.includes(selectedQuestion.question_id)} onClick={() => setConfirmation({ kind: "replace", question: selectedQuestion })}>自动换题</button>
              </div>
              {task.locked_question_ids.includes(selectedQuestion.question_id) && <small className="field-error">该题已锁定，请先解锁再换题。</small>}
            </div>
          )}
        </section>
      )}

      {reviewable && (
        <section className="review-panel">
          <div><p className="eyebrow">教师决策</p><h2>确认这套试卷</h2><p>重新组卷只替换未锁定题目。驳回前需要填写原因。</p></div>
          <textarea value={comment} onChange={(event) => setComment(event.target.value)} maxLength={200} placeholder="审核意见（驳回时必填）" />
          <div className="review-actions">
            <button type="button" className="button button-secondary" disabled={Boolean(busy) || allLocked} onClick={() => setConfirmation({ kind: "reassemble" })}>重新组卷</button>
            <button type="button" className="button button-danger" disabled={Boolean(busy) || !comment.trim()} onClick={() => void runAction("驳回", () => reviewTask(jobId, { action: "reject", reviewer: REVIEWER, comment: comment.trim() }))}>驳回</button>
            <button type="button" className="button button-primary" disabled={Boolean(busy)} onClick={() => void runAction("通过", () => reviewTask(jobId, { action: "approve", reviewer: REVIEWER, comment: comment.trim() || undefined }))}>通过并定稿</button>
          </div>
          {allLocked && <small className="field-error">所有题目均已锁定，无法重新组卷。至少解锁一道题后再试。</small>}
        </section>
      )}

      {!reviewable && task.review_status === "approved" && (
        <section className="export-panel">
          <div><p className="eyebrow">文档输出</p><h2>下载已批准试卷</h2><p>所有文件均从当前审核通过的题目快照生成，Word 与 PDF 内容经过一致性检查。</p></div>
          <div className="export-actions">
            {exportButtons.map((item) => <button type="button" key={`${item.document}-${item.format}`} className="button button-secondary" disabled={Boolean(busy)} onClick={() => void runDownload(item.label, item.document, item.format)}>{item.label}</button>)}
            <button type="button" className="button button-primary" disabled={Boolean(busy)} onClick={() => void runDownload("整套 ZIP")}>整套 ZIP</button>
          </div>
        </section>
      )}

      {confirmation && (
        <div className="confirm-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setConfirmation(null); }}>
          <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="revision-confirm-title">
            <p className="eyebrow">确认操作</p>
            <h2 id="revision-confirm-title">{confirmation.kind === "reassemble" ? "重新生成未锁定题目？" : "确认替换当前题目？"}</h2>
            <p>{confirmation.kind === "reassemble" ? `系统将保留 ${task.locked_question_ids.length} 道锁定题，并重新校验整卷约束。` : `将替换题目 ${confirmation.question.question_id}，成功后预览会自动刷新。`}</p>
            <div className="confirm-actions"><button type="button" className="button button-secondary" onClick={() => setConfirmation(null)}>取消</button><button type="button" className="button button-primary" onClick={() => void confirmRevision()}>确认继续</button></div>
          </section>
        </div>
      )}
    </div>
  );
}
