const BASE_URL = "/api";
const DEFAULT_TIMEOUT_MS = 10_000;

export interface HealthResponse {
  service: string;
  status: "healthy" | "degraded";
  checks: Record<string, unknown>;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  timeoutMs?: number;
};

function buildUrl(path: string) {
  return `${BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function readResponseBody(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";
  if (response.status === 204) return undefined;
  if (contentType.includes("application/json")) return response.json();
  return response.text();
}

function getErrorMessage(status: number, details: unknown) {
  if (details && typeof details === "object" && "detail" in details) {
    const detail = (details as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string" && message.trim()) return message;
    }
  }
  if (status === 404) return "请求的内容不存在";
  if (status === 409) return "当前数据已发生变化，请刷新后重试";
  if (status === 422) return "提交内容不符合要求，请检查后重试";
  if (status >= 500) return "后端服务暂时不可用";
  return "请求失败，请稍后重试";
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, timeoutMs = DEFAULT_TIMEOUT_MS, ...init } = options;
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;

  try {
    const response = await fetch(buildUrl(path), {
      ...init,
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
      headers: {
        Accept: "application/json",
        ...(body === undefined || isFormData ? {} : { "Content-Type": "application/json" }),
        ...headers,
      },
      signal: controller.signal,
    });
    const data = await readResponseBody(response);
    if (!response.ok) throw new ApiError(getErrorMessage(response.status, data), response.status, data);
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("请求超时，请检查服务连接", 408);
    }
    throw new ApiError("无法连接后端服务", 0, error);
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

export function healthCheck() {
  return apiRequest<HealthResponse>("/health", { cache: "no-store" });
}

export function apiGet<T>(path: string, options: RequestOptions = {}) {
  return apiRequest<T>(path, { ...options, method: "GET" });
}

export function apiPost<T>(path: string, body: unknown, options: RequestOptions = {}) {
  return apiRequest<T>(path, { ...options, method: "POST", body });
}

export function apiPut<T>(path: string, body: unknown, options: RequestOptions = {}) {
  return apiRequest<T>(path, { ...options, method: "PUT", body });
}
