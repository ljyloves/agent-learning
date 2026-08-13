import type { Metadata } from "next";
import { PaperConfigForm } from "@/components/paper-config-form";

export const metadata: Metadata = { title: "新建组卷" };

export default function NewPaperTaskPage() {
  return <PaperConfigForm />;
}
