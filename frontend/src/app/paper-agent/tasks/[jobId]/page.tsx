import type { Metadata } from "next";
import { TaskDetail } from "@/components/task-detail";

export const metadata: Metadata = { title: "组卷任务详情" };

export default function PaperTaskDetailPage({ params }: { params: { jobId: string } }) {
  return <TaskDetail jobId={params.jobId} />;
}
