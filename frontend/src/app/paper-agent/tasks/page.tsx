import type { Metadata } from "next";
import { TaskCenter } from "@/components/task-center";

export const metadata: Metadata = { title: "组卷任务" };

export default function PaperTasksPage() {
  return <TaskCenter />;
}
