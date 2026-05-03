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

export type StatsDashboard = {
  total_emails: number
  unread_count: number
  thread_count: number
  busiest_day: string
  busiest_day_count: number
  most_frequent_sender: string
  most_frequent_sender_count: number
  longest_thread_subject: string
  longest_thread_message_count: number
  most_recent_thread_subject: string
  most_recent_thread_age_hours: number
  awaiting_reply_from: string[]
  narrative: string
}

export type SynthesizedThreadRef = {
  thread_id: string
  subject: string
  why_relevant: string
}

export type CrossThreadSynthesis = {
  topic: string
  threads: SynthesizedThreadRef[]
  timeline: string[]
  key_decisions: string[]
  blockers: string[]
  people_involved: string[]
  current_status: string
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
  stats: () => request<StatsDashboard>("/ai/stats"),
  synthesize: (topic: string) =>
    request<CrossThreadSynthesis>("/ai/synthesize", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ topic }),
    }),
}
