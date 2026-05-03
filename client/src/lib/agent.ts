// TypeScript types and client for the agent service (:5001).
// Types mirror the Pydantic schemas in agent_service/schemas.py.

import { AGENT_API_BASE } from "@/constants"

// --- shared response types -------------------------------------------------

export type ThreadSummary = {
  thread_id: string | null
  subject: string | null
  participants: string[]
  summary: string
  key_decisions: string[]
  open_questions: string[]
}

export type DraftReply = {
  in_reply_to_email_id: number | null
  thread_id: string | null
  subject: string
  body: string
  tone_notes: string | null
}

export type ProactiveItemKind = "needs_response" | "commitment_due" | "stalled"

export type ProactiveItem = {
  kind: ProactiveItemKind
  title: string
  detail: string
  why: string
  score: number
  email_id: number | null
  thread_id: string | null
}

export type ProactiveSurface = {
  needs_response: ProactiveItem[]
  commitments_due: ProactiveItem[]
  stalled: ProactiveItem[]
  generated_at: string
}

// --- client ----------------------------------------------------------------

async function request<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${AGENT_API_BASE}${path}`, init)
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(`Agent ${res.status}: ${text || res.statusText}`)
  }
  return res.json() as Promise<T>
}

export const agentApi = {
  proactive: () => request<ProactiveSurface>("/ai/proactive"),
  summarizeThread: (threadId: string) =>
    request<ThreadSummary>(`/ai/summarize/${encodeURIComponent(threadId)}`, {
      method: "POST",
    }),
  draftReply: (emailId: number) =>
    request<DraftReply>(`/ai/draft-reply/${emailId}`, { method: "POST" }),
}
