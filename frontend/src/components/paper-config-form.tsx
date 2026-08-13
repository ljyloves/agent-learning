"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import {
  createOptimizedTask,
  getBiologyTaxonomy,
  questionTypeLabels,
  type BiologyTaxonomy,
  type DifficultyQuota,
  type OptimizedPaperTaskCreate,
} from "@/lib/paper-agent";

const initialQuotas: DifficultyQuota[] = [
  { question_type: "single_choice", difficulty_level: 2, count: 4, score_per_question: 5 },
  { question_type: "single_choice", difficulty_level: 3, count: 4, score_per_question: 5 },
  { question_type: "single_choice", difficulty_level: 4, count: 2, score_per_question: 5 },
];

const difficultyLabels: Record<number, string> = { 1: "很容易", 2: "容易", 3: "中等", 4: "较难", 5: "困难" };

export function PaperConfigForm() {
  const router = useRouter();
  const [taxonomy, setTaxonomy] = useState<BiologyTaxonomy | null>(null);
  const [taxonomyError, setTaxonomyError] = useState("");
  const [paperName, setPaperName] = useState("高一生物阶段练习");
  const [grade, setGrade] = useState("高一");
  const [examType, setExamType] = useState("阶段练习");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [moduleCode, setModuleCode] = useState("BIO-M1");
  const [quotas, setQuotas] = useState(initialQuotas);
  const [selectedKnowledge, setSelectedKnowledge] = useState<string[]>([]);
  const [minimumCoverageRate, setMinimumCoverageRate] = useState(1);
  const [minimumCompetencies, setMinimumCompetencies] = useState(2);
  const [minimumSources, setMinimumSources] = useState(1);
  const [similarityThreshold, setSimilarityThreshold] = useState(1);
  const [randomSeed, setRandomSeed] = useState(36);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const currentModule = taxonomy?.modules.find((module) => module.code === moduleCode) ?? null;
  const questionCount = quotas.reduce((sum, quota) => sum + quota.count, 0);
  const totalScore = quotas.reduce((sum, quota) => sum + quota.count * quota.score_per_question, 0);
  const quotaKeys = quotas.map((quota) => `${quota.question_type}:${quota.difficulty_level}`);
  const duplicateQuota = new Set(quotaKeys).size !== quotaKeys.length;
  const formValid = paperName.trim().length > 0 && durationMinutes > 0 && questionCount > 0 && totalScore > 0 && selectedKnowledge.length > 0 && !duplicateQuota && selectedKnowledge.length <= questionCount && minimumCompetencies <= questionCount && minimumSources <= questionCount;

  useEffect(() => {
    getBiologyTaxonomy()
      .then((data) => {
        setTaxonomy(data);
        const defaultModule = data.modules.find((item) => item.code === "BIO-M1") ?? data.modules[0];
        if (defaultModule) {
          setModuleCode(defaultModule.code);
          setSelectedKnowledge(defaultModule.knowledge_points.map((point) => point.code));
        }
      })
      .catch((error) => setTaxonomyError(error instanceof ApiError ? error.message : "标签体系加载失败"));
  }, []);

  useEffect(() => {
    if (!currentModule) return;
    const available = new Set(currentModule.knowledge_points.map((point) => point.code));
    setSelectedKnowledge((codes) => {
      const retained = codes.filter((code) => available.has(code));
      return retained.length > 0 ? retained : currentModule.knowledge_points.map((point) => point.code);
    });
  }, [currentModule]);

  const summary = useMemo(() => ({ questionCount, totalScore }), [questionCount, totalScore]);

  function updateQuota(index: number, patch: Partial<DifficultyQuota>) {
    setQuotas((items) => items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  }

  function addQuota() {
    setQuotas((items) => [...items, { question_type: "short_answer", difficulty_level: 3, count: 1, score_per_question: 10 }]);
  }

  function toggleKnowledge(code: string) {
    setSelectedKnowledge((codes) => codes.includes(code) ? codes.filter((item) => item !== code) : [...codes, code]);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!formValid || submitting) return;
    setSubmitting(true);
    setSubmitError("");
    const payload: OptimizedPaperTaskCreate = {
      paper_info: { paper_name: paperName.trim(), grade, exam_type: examType, duration_minutes: durationMinutes },
      optimization: {
        module_code: moduleCode,
        question_count: questionCount,
        total_score: totalScore,
        difficulty_quotas: quotas,
        coverage: { targets: selectedKnowledge.map((code) => ({ code, minimum_count: 1 })), minimum_coverage_rate: minimumCoverageRate },
        diversity: {
          minimum_distinct_knowledge_points: Math.min(selectedKnowledge.length, questionCount),
          minimum_distinct_core_competencies: minimumCompetencies,
          minimum_distinct_sources: minimumSources,
          maximum_questions_per_knowledge_point: Math.max(1, Math.ceil(questionCount / selectedKnowledge.length) + 1),
          maximum_questions_per_source: questionCount,
          semantic_similarity_threshold: similarityThreshold,
        },
        exclude_question_ids: [],
        random_seed: randomSeed,
      },
    };
    try {
      const task = await createOptimizedTask(payload);
      router.push(`/paper-agent/tasks/${task.job_id}`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 422 && error.details && typeof error.details === "object") {
        const detail = "detail" in error.details ? (error.details as { detail?: unknown }).detail : null;
        if (detail && typeof detail === "object" && "code" in detail && detail.code === "NO_FEASIBLE_PAPER") {
          const count = "candidate_count" in detail ? detail.candidate_count : 0;
          setSubmitError(`当前约束下没有可行试卷（候选题 ${count} 道）。请减少知识点或放宽题型、难度和多样性要求。`);
        } else setSubmitError(error.message);
      } else setSubmitError(error instanceof ApiError ? error.message : "创建组卷任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="paper-form page-stack" onSubmit={submit}>
      <section className="page-heading">
        <div><p className="eyebrow">新建组卷</p><h1>配置高中生物试卷</h1><p className="page-description">确定基础信息、题型难度和知识点覆盖后提交智能组卷。</p></div>
        <div className="form-summary"><span>{summary.questionCount} 题</span><strong>{summary.totalScore} 分</strong><span>{durationMinutes} 分钟</span></div>
      </section>

      <section className="form-section">
        <div className="form-section-heading"><div><span>01</span><h2>基础信息</h2></div><p>用于任务识别和试卷页眉</p></div>
        <div className="form-grid four-columns">
          <label className="field field-wide"><span>试卷名称</span><input required maxLength={80} value={paperName} onChange={(event) => setPaperName(event.target.value)} /></label>
          <label className="field"><span>年级</span><select value={grade} onChange={(event) => setGrade(event.target.value)}><option>高一</option><option>高二</option><option>高三</option></select></label>
          <label className="field"><span>考试类型</span><select value={examType} onChange={(event) => setExamType(event.target.value)}><option>阶段练习</option><option>单元测试</option><option>期中考试</option><option>期末考试</option><option>模拟考试</option></select></label>
          <label className="field"><span>考试时长（分钟）</span><input type="number" min={10} max={300} value={durationMinutes} onChange={(event) => setDurationMinutes(Number(event.target.value))} /></label>
          <label className="field"><span>课程模块</span><select value={moduleCode} disabled={!taxonomy} onChange={(event) => setModuleCode(event.target.value)}>{taxonomy?.modules.map((module) => <option key={module.code} value={module.code}>{module.name}</option>)}</select></label>
        </div>
      </section>

      <section className="form-section">
        <div className="form-section-heading"><div><span>02</span><h2>题型与难度</h2></div><button type="button" className="text-button" onClick={addQuota}>+ 添加配额</button></div>
        <div className="quota-table-wrap"><table className="quota-table"><thead><tr><th>题型</th><th>难度</th><th>数量</th><th>每题分值</th><th>小计</th><th><span className="sr-only">操作</span></th></tr></thead><tbody>{quotas.map((quota, index) => <tr key={`${index}-${quota.question_type}-${quota.difficulty_level}`}><td><select aria-label={`第 ${index + 1} 行题型`} value={quota.question_type} onChange={(event) => updateQuota(index, { question_type: event.target.value as DifficultyQuota["question_type"] })}>{Object.entries(questionTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></td><td><select aria-label={`第 ${index + 1} 行难度`} value={quota.difficulty_level} onChange={(event) => updateQuota(index, { difficulty_level: Number(event.target.value) })}>{Object.entries(difficultyLabels).map(([value, label]) => <option key={value} value={value}>{value} · {label}</option>)}</select></td><td><input aria-label={`第 ${index + 1} 行数量`} type="number" min={1} max={1000} value={quota.count} onChange={(event) => updateQuota(index, { count: Number(event.target.value) })} /></td><td><input aria-label={`第 ${index + 1} 行分值`} type="number" min={1} max={100} value={quota.score_per_question} onChange={(event) => updateQuota(index, { score_per_question: Number(event.target.value) })} /></td><td><strong>{quota.count * quota.score_per_question} 分</strong></td><td><button type="button" className="icon-action" aria-label={`删除第 ${index + 1} 行配额`} disabled={quotas.length === 1} onClick={() => setQuotas((items) => items.filter((_, itemIndex) => itemIndex !== index))}>×</button></td></tr>)}</tbody><tfoot><tr><td colSpan={2}>合计</td><td>{questionCount} 题</td><td /><td>{totalScore} 分</td><td /></tr></tfoot></table></div>
        {duplicateQuota && <p className="field-error" role="alert">同一题型和难度只能配置一次。</p>}
      </section>

      <section className="form-section">
        <div className="form-section-heading"><div><span>03</span><h2>知识点覆盖</h2></div><p>已选 {selectedKnowledge.length}/{currentModule?.knowledge_points.length ?? 0}</p></div>
        {taxonomyError ? <div className="inline-error" role="alert"><div><strong>标签体系加载失败</strong><p>{taxonomyError}</p></div></div> : !currentModule ? <div className="knowledge-loading skeleton" /> : <div className="knowledge-grid">{currentModule.knowledge_points.map((point) => <label key={point.code} className={`knowledge-option${selectedKnowledge.includes(point.code) ? " selected" : ""}`}><input type="checkbox" checked={selectedKnowledge.includes(point.code)} onChange={() => toggleKnowledge(point.code)} /><span><strong>{point.name}</strong><small>{point.code}</small></span></label>)}</div>}
        {selectedKnowledge.length > questionCount && <p className="field-error" role="alert">知识点数量不能超过题目数量。</p>}
      </section>

      <section className="form-section">
        <div className="form-section-heading"><div><span>04</span><h2>高级约束</h2></div><p>默认值适配当前 MVP 题库</p></div>
        <div className="form-grid four-columns">
          <label className="field"><span>最低覆盖率</span><select value={minimumCoverageRate} onChange={(event) => setMinimumCoverageRate(Number(event.target.value))}><option value={1}>100%</option><option value={0.8}>80%</option><option value={0.6}>60%</option></select></label>
          <label className="field"><span>核心素养种类</span><input type="number" min={1} max={4} value={minimumCompetencies} onChange={(event) => setMinimumCompetencies(Number(event.target.value))} /></label>
          <label className="field"><span>题目来源种类</span><input type="number" min={1} max={questionCount || 1} value={minimumSources} onChange={(event) => setMinimumSources(Number(event.target.value))} /></label>
          <label className="field"><span>语义相似度阈值</span><input type="number" min={0.8} max={1} step={0.01} value={similarityThreshold} onChange={(event) => setSimilarityThreshold(Number(event.target.value))} /></label>
          <label className="field"><span>随机种子</span><input type="number" min={0} max={2147483647} value={randomSeed} onChange={(event) => setRandomSeed(Number(event.target.value))} /></label>
        </div>
      </section>

      {submitError && <div className="inline-error" role="alert"><div><strong>无法完成组卷</strong><p>{submitError}</p></div></div>}
      <div className="form-actions"><button type="button" className="button button-secondary" onClick={() => router.push("/paper-agent/tasks")}>取消</button><button type="submit" className="button button-primary" disabled={!formValid || submitting}>{submitting ? "正在智能组卷…" : "创建并开始组卷"}</button></div>
    </form>
  );
}
