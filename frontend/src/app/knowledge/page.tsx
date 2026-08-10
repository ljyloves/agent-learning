"use client";

import { useState, useRef, useEffect } from "react";

interface Source {
  source: string;
  score: number;
  text: string;
}

interface QAResult {
  answer: string;
  sources: Source[];
}

export default function KnowledgePage() {
  // Upload state
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");

  // QA state
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [qaResult, setQaResult] = useState<QAResult | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [qaResult]);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setUploadMsg("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/documents/upload", { method: "POST", body: form });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      setUploadMsg(`上传成功: ${data.source}`);
      setFile(null);
    } catch {
      setUploadMsg("上传失败，请重试");
    } finally {
      setUploading(false);
    }
  };

  const handleAsk = async () => {
    const q = question.trim();
    if (!q || asking) return;
    setAsking(true);
    try {
      const res = await fetch("/api/rag/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, top_k: 3 }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setQaResult(await res.json());
    } catch {
      setQaResult({ answer: "查询失败，请重试", sources: [] });
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="space-y-8 max-w-3xl mx-auto">
      {/* Upload Section */}
      <section className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">上传文档</h2>
        <div className="flex gap-3">
          <input
            type="file"
            accept=".txt,.md,.csv"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="flex-1 text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-blue-50 file:text-blue-700"
          />
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors whitespace-nowrap"
          >
            {uploading ? "上传中..." : "上传"}
          </button>
        </div>
        {uploadMsg && <p className="mt-2 text-sm text-green-600">{uploadMsg}</p>}
      </section>

      {/* QA Section */}
      <section className="bg-white border border-gray-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">知识库问答</h2>
        <div className="flex gap-3 mb-4">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAsk()}
            placeholder="基于已上传文档提问..."
            className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={asking}
          />
          <button
            onClick={handleAsk}
            disabled={!question.trim() || asking}
            className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {asking ? "查询中..." : "提问"}
          </button>
        </div>

        {qaResult && (
          <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-sm whitespace-pre-wrap">{qaResult.answer}</p>
            </div>
            {qaResult.sources.length > 0 && (
              <details className="text-sm">
                <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
                  引用来源 ({qaResult.sources.length})
                </summary>
                <div className="mt-2 space-y-2">
                  {qaResult.sources.map((s, i) => (
                    <div key={i} className="p-3 bg-gray-50 rounded text-xs">
                      <div className="flex justify-between text-gray-400 mb-1">
                        <span>{s.source}</span>
                        <span>相似度: {s.score.toFixed(3)}</span>
                      </div>
                      <p className="text-gray-600">{s.text}</p>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
