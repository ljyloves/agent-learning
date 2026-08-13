import { ApiError, apiGet, apiPost, apiRequest } from "@/lib/api";

export type PaperJobStatus =
  | "queued"
  | "running"
  | "awaiting_review"
  | "completed"
  | "failed"
  | "cancelled";

export type ReviewStatus =
  | "not_started"
  | "pending"
  | "approved"
  | "rejected"
  | "revision_required";

export type QuestionType =
  | "single_choice"
  | "multiple_choice"
  | "true_false"
  | "fill_blank"
  | "short_answer"
  | "composite";

export interface PaperInfo {
  paper_name: string;
  grade: string;
  exam_type: string;
  duration_minutes: number;
}

export interface OptimizedTaskListItem extends PaperInfo {
  job_id: string;
  question_count: number;
  total_score: number;
  status: PaperJobStatus;
  review_status: ReviewStatus;
  awaiting_teacher: boolean;
  created_at: string;
  updated_at: string;
}

export interface OptimizedTaskListResponse {
  items: OptimizedTaskListItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface DifficultyQuota {
  question_type: QuestionType;
  difficulty_level: number;
  count: number;
  score_per_question: number;
}

export interface OptimizedPaperTaskCreate {
  paper_info: PaperInfo;
  optimization: {
    module_code: string;
    question_count: number;
    total_score: number;
    difficulty_quotas: DifficultyQuota[];
    coverage: {
      targets: Array<{ code: string; minimum_count: number }>;
      minimum_coverage_rate: number;
    };
    diversity: {
      minimum_distinct_knowledge_points: number;
      minimum_distinct_core_competencies: number;
      minimum_distinct_sources: number;
      maximum_questions_per_knowledge_point: number | null;
      maximum_questions_per_source: number | null;
      semantic_similarity_threshold: number;
    };
    exclude_question_ids: string[];
    random_seed: number;
  };
}

export interface OptimizedTaskResponse {
  job_id: string;
  generation_mode: "optimized";
  status: PaperJobStatus;
  review_status: ReviewStatus;
  failure_reason: string | null;
  awaiting_teacher: boolean;
  paper: {
    module_code: string;
    question_count: number;
    total_score: number;
    sections: Array<{
      section_index: number;
      question_type: QuestionType;
      difficulty_level: number;
      count: number;
      score_per_question: number;
      questions: OptimizedQuestion[];
    }>;
    audit: {
      satisfied: boolean;
      coverage_rate: number;
      distinct_knowledge_point_count: number;
      distinct_core_competency_count: number;
      distinct_source_count: number;
    };
  };
  locked_question_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface OptimizedQuestion {
  question_id: string;
  question_type: QuestionType;
  difficulty_level: number;
  estimated_correct_rate: number;
  score: number;
  source_id: string;
  knowledge_point_codes: string[];
  core_competency_codes: string[];
  difficulty_analysis_id: string;
  quality_analysis_id: string;
}

export interface ReviewCommand {
  action: "approve" | "reject";
  reviewer: string;
  comment?: string;
}

export interface LockUpdate {
  question_ids: string[];
  locked: boolean;
}

export interface ReplaceQuestionCommand {
  question_id: string;
  replacement_question_id?: string;
  reviewer: string;
  comment?: string;
}

export interface ReassembleCommand {
  reviewer: string;
  comment?: string;
  random_seed?: number;
}

export interface QuestionDetail {
  id: string | null;
  question_type: QuestionType;
  difficulty: "easy" | "medium" | "hard";
  stem: string;
  source: { source_id?: string; name?: string; uri?: string; id?: string; title?: string; external_id?: string; source_type?: string };
  options: Array<{
    label: string;
    content: string | null;
    images: QuestionImage[];
  }>;
  subquestions: QuestionDetail[];
  answer: string | string[] | null;
  explanation: string | null;
  images: QuestionImage[];
}

export interface QuestionImage {
  resource_id?: string;
  uri?: string;
  storage_uri?: string;
  url?: string;
  alt_text?: string | null;
  caption?: string | null;
}

export interface KnowledgePoint {
  code: string;
  name: string;
  description: string;
  sort_order: number;
}

export interface CurriculumModule {
  code: string;
  name: string;
  course_type: string;
  description: string;
  sort_order: number;
  knowledge_points: KnowledgePoint[];
}

export interface BiologyTaxonomy {
  modules: CurriculumModule[];
  core_competencies: Array<{
    code: string;
    name: string;
    description: string;
    sort_order: number;
  }>;
}

export type SourceProcessingStatus = "uploaded" | "processing" | "completed" | "failed";
export type SourceType = "website" | "api" | "file" | "book" | "manual";
export type ResourceType = "image" | "document" | "webpage" | "attachment";

export interface SourceLibraryItem {
  source_id: string;
  resource_id: string | null;
  name: string;
  source_type: SourceType;
  resource_type: ResourceType | null;
  mime_type: string | null;
  locator: string | null;
  attribution: string | null;
  retrieved_at: string;
  processing_status: SourceProcessingStatus;
  failure_reason: string | null;
  processed_at: string | null;
  question_count: number;
  can_parse: boolean;
}

export interface SourceLibraryResponse {
  items: SourceLibraryItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface QuestionLibraryItem {
  question_id: string;
  question_type: QuestionType;
  difficulty: "easy" | "medium" | "hard";
  stem: string;
  has_answer: boolean;
  created_at: string;
  source_id: string;
  source_name: string;
  source_type: SourceType;
  source_locator: string | null;
  attribution: string | null;
}

export interface QuestionLibraryResponse {
  items: QuestionLibraryItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface TeacherUploadResponse {
  source_id: string;
  resource_id: string;
  source_type: SourceType;
  resource_type: ResourceType;
  original_name: string | null;
  storage_uri: string;
  mime_type: string;
  sha256: string;
  size_bytes: number;
}

export interface ParsedQuestionsResponse {
  source_resource_id: string;
  question_ids: string[];
  warnings: string[];
}

export const questionTypeLabels: Record<QuestionType, string> = {
  single_choice: "单项选择题",
  multiple_choice: "多项选择题",
  true_false: "判断题",
  fill_blank: "填空题",
  short_answer: "简答题",
  composite: "综合题",
};

export const taskStatusLabels: Record<PaperJobStatus, string> = {
  queued: "排队中",
  running: "组卷中",
  awaiting_review: "待审核",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

export const reviewStatusLabels: Record<ReviewStatus, string> = {
  not_started: "未开始",
  pending: "待审核",
  approved: "已通过",
  rejected: "已驳回",
  revision_required: "需修改",
};

function queryString(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export function listOptimizedTasks(params: {
  page: number;
  pageSize: number;
  keyword?: string;
  status?: string;
  reviewStatus?: string;
}) {
  return apiGet<OptimizedTaskListResponse>(
    `/paper-agent/optimized-tasks${queryString({
      page: params.page,
      page_size: params.pageSize,
      keyword: params.keyword,
      status: params.status,
      review_status: params.reviewStatus,
    })}`,
    { cache: "no-store" },
  );
}

export function getOptimizedTask(jobId: string) {
  return apiGet<OptimizedTaskResponse>(`/paper-agent/optimized-tasks/${jobId}`, {
    cache: "no-store",
  });
}

export function createOptimizedTask(payload: OptimizedPaperTaskCreate) {
  return apiPost<OptimizedTaskResponse>("/paper-agent/optimized-tasks", payload);
}

export function getBiologyTaxonomy() {
  return apiGet<BiologyTaxonomy>("/paper-agent/taxonomy/biology", {
    cache: "no-store",
  });
}

export function getQuestion(questionId: string) {
  return apiGet<QuestionDetail>(`/paper-agent/questions/${questionId}`, { cache: "no-store" });
}

export function listSourceLibrary(params: {
  page: number;
  pageSize: number;
  keyword?: string;
  sourceType?: SourceType | "";
}) {
  return apiGet<SourceLibraryResponse>(
    `/paper-agent/library/sources${queryString({
      page: params.page,
      page_size: params.pageSize,
      keyword: params.keyword,
      source_type: params.sourceType,
    })}`,
    { cache: "no-store" },
  );
}

export function listQuestionLibrary(params: {
  page: number;
  pageSize: number;
  keyword?: string;
  questionType?: QuestionType | "";
  sourceId?: string;
}) {
  return apiGet<QuestionLibraryResponse>(
    `/paper-agent/library/questions${queryString({
      page: params.page,
      page_size: params.pageSize,
      keyword: params.keyword,
      question_type: params.questionType,
      source_id: params.sourceId,
    })}`,
    { cache: "no-store" },
  );
}

export function uploadTeacherResource(file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiPost<TeacherUploadResponse>("/paper-agent/sources/files", form, {
    timeoutMs: 60_000,
  });
}

export function parseTeacherResource(resourceId: string) {
  return apiPost<ParsedQuestionsResponse>(
    `/paper-agent/sources/resources/${encodeURIComponent(resourceId)}/questions`,
    { difficulty: "medium", knowledge_point_codes: [] },
    { timeoutMs: 120_000 },
  );
}

export function updateTaskLocks(jobId: string, payload: LockUpdate) {
  return apiRequest<OptimizedTaskResponse>(`/paper-agent/optimized-tasks/${jobId}/locks`, {
    method: "PUT",
    body: payload,
  });
}

export function replaceTaskQuestion(jobId: string, payload: ReplaceQuestionCommand) {
  return apiPost<OptimizedTaskResponse>(`/paper-agent/optimized-tasks/${jobId}/replace`, payload);
}

export function reassembleTask(jobId: string, payload: ReassembleCommand) {
  return apiPost<OptimizedTaskResponse>(`/paper-agent/optimized-tasks/${jobId}/reassemble`, payload);
}

export function reviewTask(jobId: string, payload: ReviewCommand) {
  return apiPost<OptimizedTaskResponse>(`/paper-agent/optimized-tasks/${jobId}/review`, payload);
}

export type OptimizedExportDocument = "student" | "teacher-answer" | "answer-sheet";
export type OptimizedExportFormat = "docx" | "pdf";

export async function downloadTaskExport(
  jobId: string,
  documentType?: OptimizedExportDocument,
  format?: OptimizedExportFormat,
) {
  const path = documentType && format
    ? `/api/paper-agent/optimized-tasks/${encodeURIComponent(jobId)}/exports/${documentType}/${format}`
    : `/api/paper-agent/optimized-tasks/${encodeURIComponent(jobId)}/exports.zip`;
  const response = await fetch(path, {
    method: "GET",
    headers: { Accept: "application/octet-stream" },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body === "object" && "detail" in body
      ? (body as { detail?: unknown }).detail
      : null;
    throw new ApiError(
      typeof detail === "string" ? detail : "文件导出失败，请稍后重试",
      response.status,
      body,
    );
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const fallbackName = documentType && format ? `${documentType}.${format}` : "整套试卷.zip";
  const name = encoded ? decodeURIComponent(encoded) : fallbackName;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}
