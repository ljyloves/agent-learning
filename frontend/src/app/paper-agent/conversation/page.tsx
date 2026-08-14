import type { Metadata } from "next";
import { ConversationPaperAgent } from "@/components/conversation-paper-agent";

export const metadata: Metadata = { title: "对话式组卷" };

export default function ConversationPaperPage() {
  return <ConversationPaperAgent />;
}
