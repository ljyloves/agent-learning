"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import {
  listQuestionLibrary,
  listSourceLibrary,
  parseTeacherResource,
  questionTypeLabels,
  uploadTeacherResource,
  type QuestionLibraryResponse,
  type QuestionType,
  type SourceLibraryItem,
  type SourceLibraryResponse,
} from "@/lib/paper-agent";

const PAGE_SIZE = 8;
const ALLOWED_EXTENSIONS = ["pdf", "doc", "docx", "png", "jpg", "jpeg", "gif", "webp"];

const sourceTypeLabels = {
  file: "教师文件",
  website: "白名单网站",
  api: "接口",
  book: "书籍",
  manual: "人工录入",
};

const difficultyLabels = { easy: "简单", medium: "中等", hard: "困难" };

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function resourceKind(item: SourceLibraryItem) {
  if (item.resource_type === "image") return "图片";
  if (item.resource_type === "webpage") return "网页";
  if (item.mime_type?.includes("pdf")) return "PDF";
  if (item.mime_type?.includes("word") || item.mime_type?.includes("msword")) return "Word";
  return "资料";
}

function statusLabel(item: SourceLibraryItem) {
  if (!item.can_parse) return "已归档";
  return {
    uploaded: "待解析",
    processing: "解析中",
    completed: "解析成功",
    failed: "解析失败",
  }[item.processing_status];
}

function statusClass(item: SourceLibraryItem) {
  if (item.processing_status === "failed") return "status-failed";
  if (item.processing_status === "completed" || !item.can_parse) return "status-completed";
  if (item.processing_status === "processing") return "status-running";
  return "status-awaiting_review";
}

export default function KnowledgePage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [activeView, setActiveView] = useState<"sources" | "questions">("sources");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadNotice, setUploadNotice] = useState("");
  const [parsingId, setParsingId] = useState("");

  const [sourceInput, setSourceInput] = useState("");
  const [sourceKeyword, setSourceKeyword] = useState("");
  const [sourcePage, setSourcePage] = useState(1);
  const [sources, setSources] = useState<SourceLibraryResponse | null>(null);
  const [sourceError, setSourceError] = useState("");
  const [sourcesLoading, setSourcesLoading] = useState(true);

  const [questionInput, setQuestionInput] = useState("");
  const [questionKeyword, setQuestionKeyword] = useState("");
  const [questionType, setQuestionType] = useState<QuestionType | "">("");
  const [questionPage, setQuestionPage] = useState(1);
  const [questions, setQuestions] = useState<QuestionLibraryResponse | null>(null);
  const [questionError, setQuestionError] = useState("");
  const [questionsLoading, setQuestionsLoading] = useState(true);

  const loadSources = useCallback(async () => {
    setSourcesLoading(true);
    setSourceError("");
    try {
      setSources(await listSourceLibrary({
        page: sourcePage,
        pageSize: PAGE_SIZE,
        keyword: sourceKeyword,
      }));
    } catch (error) {
      setSourceError(error instanceof ApiError ? error.message : "资料列表加载失败");
    } finally {
      setSourcesLoading(false);
    }
  }, [sourceKeyword, sourcePage]);

  const loadQuestions = useCallback(async () => {
    setQuestionsLoading(true);
    setQuestionError("");
    try {
      setQuestions(await listQuestionLibrary({
        page: questionPage,
        pageSize: PAGE_SIZE,
        keyword: questionKeyword,
        questionType,
      }));
    } catch (error) {
      setQuestionError(error instanceof ApiError ? error.message : "题库加载失败");
    } finally {
      setQuestionsLoading(false);
    }
  }, [questionKeyword, questionPage, questionType]);

  useEffect(() => { void loadSources(); }, [loadSources]);
  useEffect(() => { void loadQuestions(); }, [loadQuestions]);

  function chooseFile(nextFile: File | null) {
    setUploadError("");
    setUploadNotice("");
    if (!nextFile) {
      setFile(null);
      return;
    }
    const extension = nextFile.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      setFile(null);
      setUploadError("仅支持 PDF、Word 和常见图片格式");
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    setFile(nextFile);
  }

  async function upload() {
    if (!file || uploading) return;
    setUploading(true);
    setUploadError("");
    setUploadNotice("");
    try {
      const result = await uploadTeacherResource(file);
      setUploadNotice(
        result.resource_type === "document"
          ? `“${result.original_name ?? file.name}”已上传，可在资料台账中开始解析。`
          : `“${result.original_name ?? file.name}”已安全归档。`,
      );
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      setSourcePage(1);
      await loadSources();
    } catch (error) {
      setUploadError(error instanceof ApiError ? error.message : "资料上传失败，请稍后重试");
    } finally {
      setUploading(false);
    }
  }

  async function parse(item: SourceLibraryItem) {
    if (!item.resource_id || parsingId) return;
    setParsingId(item.resource_id);
    setUploadError("");
    setUploadNotice("");
    try {
      const result = await parseTeacherResource(item.resource_id);
      setUploadNotice(`“${item.name}”解析完成，共入库 ${result.question_ids.length} 道题。`);
      await Promise.all([loadSources(), loadQuestions()]);
    } catch (error) {
      setUploadError(error instanceof ApiError ? error.message : "题目解析失败，请检查资料格式");
      await loadSources();
    } finally {
      setParsingId("");
    }
  }

  function searchSources(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSourcePage(1);
    setSourceKeyword(sourceInput.trim());
  }

  function searchQuestions(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuestionPage(1);
    setQuestionKeyword(questionInput.trim());
  }

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">教师资料</p>
          <h1>资料与题库</h1>
          <p className="page-description">上传教学资料，跟踪解析结果，并核对每道题的原始来源。</p>
        </div>
      </section>

      <section className="workspace-section resource-upload-section">
        <div className="section-heading">
          <div><p className="eyebrow">资料入库</p><h2>上传 PDF、Word 或图片</h2></div>
          <span className="quiet-label">支持单个文件上传</span>
        </div>
        <div className="upload-workspace">
          <label className="file-drop" htmlFor="teacher-resource-file">
            <strong>{file ? file.name : "选择教学资料"}</strong>
            <span>{file ? `${Math.max(1, Math.ceil(file.size / 1024))} KB` : "PDF、DOC、DOCX、PNG、JPG、GIF、WEBP"}</span>
            <input
              ref={inputRef}
              id="teacher-resource-file"
              type="file"
              accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.gif,.webp"
              onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button type="button" className="button button-primary upload-button" disabled={!file || uploading} onClick={() => void upload()}>
            {uploading ? "正在上传…" : "上传资料"}
          </button>
        </div>
        {uploadNotice && <div className="operation-notice" role="status"><strong>操作完成</strong><span>{uploadNotice}</span></div>}
        {uploadError && <div className="operation-notice operation-notice-error" role="alert"><strong>操作失败</strong><span>{uploadError}</span></div>}
      </section>

      <div className="library-tabs" role="tablist" aria-label="资料管理视图">
        <button type="button" role="tab" aria-selected={activeView === "sources"} className={activeView === "sources" ? "active" : ""} onClick={() => setActiveView("sources")}>资料台账</button>
        <button type="button" role="tab" aria-selected={activeView === "questions"} className={activeView === "questions" ? "active" : ""} onClick={() => setActiveView("questions")}>题库浏览</button>
      </div>

      {activeView === "sources" ? (
        <section className="task-table-shell" role="tabpanel">
          <div className="library-toolbar">
            <div><p className="eyebrow">来源台账</p><h2>已接收资料</h2></div>
            <form className="search-form" onSubmit={searchSources}>
              <label className="sr-only" htmlFor="source-keyword">搜索资料名称</label>
              <input id="source-keyword" value={sourceInput} onChange={(event) => setSourceInput(event.target.value)} placeholder="搜索资料名称或来源" />
              <button type="submit" className="button button-secondary">搜索</button>
            </form>
          </div>
          {sourcesLoading ? <div className="task-table-loading skeleton" aria-label="资料加载中" /> : sourceError ? (
            <div className="inline-error" role="alert"><div><strong>无法加载资料台账</strong><p>{sourceError}</p></div><button type="button" className="button button-secondary" onClick={() => void loadSources()}>重新加载</button></div>
          ) : sources && sources.items.length > 0 ? (
            <>
              <div className="table-scroll">
                <table className="task-table resource-table">
                  <thead><tr><th>资料</th><th>来源</th><th>处理状态</th><th>题目</th><th>接收时间</th><th><span className="sr-only">操作</span></th></tr></thead>
                  <tbody>{sources.items.map((item) => (
                    <tr key={item.source_id}>
                      <td><strong>{item.name}</strong><span>{resourceKind(item)}{item.mime_type ? ` · ${item.mime_type}` : ""}</span><code>{item.source_id.slice(0, 12)}</code></td>
                      <td><strong>{sourceTypeLabels[item.source_type]}</strong><span>{item.attribution ?? item.locator ?? "来源信息已记录"}</span></td>
                      <td><span className={`status-badge ${statusClass(item)}`}>{statusLabel(item)}</span>{item.failure_reason && <p className="failure-reason" title={item.failure_reason}>{item.failure_reason}</p>}</td>
                      <td><strong>{item.question_count}</strong><span className="table-unit"> 道</span></td>
                      <td>{formatDate(item.retrieved_at)}</td>
                      <td>{item.can_parse && item.processing_status !== "completed" && <button type="button" className="row-action row-action-button" disabled={Boolean(parsingId)} onClick={() => void parse(item)}>{parsingId === item.resource_id ? "解析中…" : item.processing_status === "failed" ? "重新解析" : "开始解析"}</button>}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              <div className="pagination"><span>共 {sources.total} 项，第 {sources.page}/{Math.max(sources.pages, 1)} 页</span><div><button type="button" className="button button-secondary" disabled={sourcePage <= 1} onClick={() => setSourcePage((value) => value - 1)}>上一页</button><button type="button" className="button button-secondary" disabled={sources.pages === 0 || sourcePage >= sources.pages} onClick={() => setSourcePage((value) => value + 1)}>下一页</button></div></div>
            </>
          ) : <div className="compact-empty"><strong>暂无资料</strong><p>{sourceKeyword ? "没有匹配的资料，请调整搜索条件。" : "上传第一份教学资料后会显示在这里。"}</p></div>}
        </section>
      ) : (
        <section className="task-table-shell" role="tabpanel">
          <div className="library-toolbar question-toolbar">
            <div><p className="eyebrow">结构化题库</p><h2>已入库题目</h2></div>
            <form className="search-form" onSubmit={searchQuestions}>
              <label className="sr-only" htmlFor="question-keyword">搜索题干</label>
              <input id="question-keyword" value={questionInput} onChange={(event) => setQuestionInput(event.target.value)} placeholder="搜索题干或来源" />
              <select aria-label="筛选题型" value={questionType} onChange={(event) => { setQuestionPage(1); setQuestionType(event.target.value as QuestionType | ""); }}><option value="">全部题型</option>{Object.entries(questionTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
              <button type="submit" className="button button-secondary">搜索</button>
            </form>
          </div>
          {questionsLoading ? <div className="task-table-loading skeleton" aria-label="题库加载中" /> : questionError ? (
            <div className="inline-error" role="alert"><div><strong>无法加载题库</strong><p>{questionError}</p></div><button type="button" className="button button-secondary" onClick={() => void loadQuestions()}>重新加载</button></div>
          ) : questions && questions.items.length > 0 ? (
            <>
              <div className="question-bank-list">{questions.items.map((item, index) => (
                <article key={item.question_id}>
                  <div className="question-number">{String((questionPage - 1) * PAGE_SIZE + index + 1).padStart(2, "0")}</div>
                  <div className="question-bank-main"><div className="question-bank-meta"><span>{questionTypeLabels[item.question_type]}</span><span>{difficultyLabels[item.difficulty]}</span><span>{item.has_answer ? "答案完整" : "缺少答案"}</span></div><p>{item.stem}</p><div className="provenance-line"><strong>来源</strong><span>{item.source_name}</span><span>{item.attribution ?? item.source_locator ?? sourceTypeLabels[item.source_type]}</span></div></div>
                </article>
              ))}</div>
              <div className="pagination"><span>共 {questions.total} 道题，第 {questions.page}/{Math.max(questions.pages, 1)} 页</span><div><button type="button" className="button button-secondary" disabled={questionPage <= 1} onClick={() => setQuestionPage((value) => value - 1)}>上一页</button><button type="button" className="button button-secondary" disabled={questions.pages === 0 || questionPage >= questions.pages} onClick={() => setQuestionPage((value) => value + 1)}>下一页</button></div></div>
            </>
          ) : <div className="compact-empty"><strong>暂无匹配题目</strong><p>{questionKeyword || questionType ? "调整筛选条件后重试。" : "解析结构化资料后，题目会进入这里。"}</p></div>}
        </section>
      )}
    </div>
  );
}
