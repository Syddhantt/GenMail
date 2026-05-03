import { useEffect, useState } from "react"
import {
  Sparkles,
  AlertCircle,
  RefreshCw,
  Loader2,
  FileText,
  ChevronDown,
  ChevronRight,
  BarChart3,
  Search,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerFooter,
  DrawerClose,
} from "@/components/ui/drawer"
import { Textarea } from "@/components/ui/textarea"
import { agentApi } from "@/lib/agent"
import type {
  CrossThreadSynthesis,
  DraftReply,
  ProactiveItem,
  ProactiveSurface,
  StatsDashboard,
  ThreadSummary,
} from "@/lib/agent"
import type { Email } from "@/types"

interface InboxIntelligenceProps {
  selectedEmail: Email | null
  threadEmails: Email[]
}

const KIND_STYLE: Record<
  ProactiveItem["kind"],
  { label: string; classes: string; icon: string }
> = {
  needs_response: {
    label: "Needs response",
    classes:
      "border-red-200 bg-red-50/50 dark:border-red-900/60 dark:bg-red-950/30",
    icon: "🔴",
  },
  commitment_due: {
    label: "Commitment due",
    classes:
      "border-amber-200 bg-amber-50/50 dark:border-amber-900/60 dark:bg-amber-950/30",
    icon: "⏳",
  },
  stalled: {
    label: "Stalled",
    classes:
      "border-slate-200 bg-slate-50/50 dark:border-slate-700 dark:bg-slate-900/40",
    icon: "⚠️",
  },
}

export function InboxIntelligence({ selectedEmail, threadEmails }: InboxIntelligenceProps) {
  const [proactive, setProactive] = useState<ProactiveSurface | null>(null)
  const [proactiveLoading, setProactiveLoading] = useState(false)
  const [proactiveError, setProactiveError] = useState<string | null>(null)

  const [summary, setSummary] = useState<ThreadSummary | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)

  const [draft, setDraft] = useState<DraftReply | null>(null)
  const [draftLoading, setDraftLoading] = useState(false)
  const [draftOpen, setDraftOpen] = useState(false)

  const fetchProactive = async () => {
    setProactiveLoading(true)
    setProactiveError(null)
    try {
      setProactive(await agentApi.proactive())
    } catch (e) {
      setProactiveError(e instanceof Error ? e.message : String(e))
    } finally {
      setProactiveLoading(false)
    }
  }

  useEffect(() => {
    fetchProactive()
  }, [])

  // Reset summary/draft when the user navigates to a different thread.
  useEffect(() => {
    setSummary(null)
    setDraft(null)
  }, [selectedEmail?.thread_id])

  const handleSummarize = async () => {
    if (!selectedEmail) return
    setSummaryLoading(true)
    try {
      setSummary(await agentApi.summarizeThread(selectedEmail.thread_id))
    } catch (e) {
      console.error(e)
    } finally {
      setSummaryLoading(false)
    }
  }

  const handleDraft = async () => {
    if (!selectedEmail) return
    setDraftLoading(true)
    setDraftOpen(true)
    try {
      // Draft a reply to the most recent message in the thread, not the
      // selected one (matches what a user would mean by "draft a reply").
      const latest = threadEmails[threadEmails.length - 1] || selectedEmail
      setDraft(await agentApi.draftReply(latest.id))
    } catch (e) {
      console.error(e)
    } finally {
      setDraftLoading(false)
    }
  }

  return (
    <>
      <aside className="w-full h-full border-l bg-muted/40 dark:bg-muted/20 flex flex-col min-w-0">
        <div className="p-4 border-b flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-violet-500" />
            <h3 className="font-semibold text-sm">Inbox Intelligence</h3>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchProactive}
            disabled={proactiveLoading}
            title="Refresh"
          >
            {proactiveLoading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <RefreshCw className="size-4" />
            )}
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Per-thread actions appear at top when an email is selected */}
          {selectedEmail && (
            <ThreadActions
              summary={summary}
              summaryLoading={summaryLoading}
              onSummarize={handleSummarize}
              onDraft={handleDraft}
              draftLoading={draftLoading}
            />
          )}

          {proactiveError && (
            <Card className="border-red-200 bg-red-50/50">
              <CardContent className="py-3 text-sm text-red-700 flex items-start gap-2">
                <AlertCircle className="size-4 mt-0.5 shrink-0" />
                <div>
                  <div className="font-medium">Could not load insights</div>
                  <div className="text-xs mt-1 break-all">{proactiveError}</div>
                </div>
              </CardContent>
            </Card>
          )}

          {!proactive && !proactiveError && proactiveLoading && (
            <Empty className="py-8">
              <EmptyHeader>
                <Loader2 className="size-6 animate-spin mx-auto text-muted-foreground" />
                <EmptyTitle className="mt-2 text-sm">Analyzing inbox…</EmptyTitle>
                <EmptyDescription className="text-xs">
                  Running urgency, commitments, and thread state in parallel.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}

          {proactive && (
            <ProactiveBuckets surface={proactive} />
          )}

          <MoreInsights />
        </div>
      </aside>

      <DraftDrawer
        open={draftOpen}
        onOpenChange={setDraftOpen}
        draft={draft}
        loading={draftLoading}
      />
    </>
  )
}

// --- subcomponents ---------------------------------------------------------

function ThreadActions({
  summary,
  summaryLoading,
  onSummarize,
  onDraft,
  draftLoading,
}: {
  summary: ThreadSummary | null
  summaryLoading: boolean
  onSummarize: () => void
  onDraft: () => void
  draftLoading: boolean
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground">
          This thread
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={onSummarize}
            disabled={summaryLoading}
            className="flex-1"
          >
            {summaryLoading ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <FileText className="size-3" />
            )}
            Summarize
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={onDraft}
            disabled={draftLoading}
            className="flex-1"
          >
            {draftLoading ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />}
            Draft reply
          </Button>
        </div>
        {summary && (
          <div className="text-sm space-y-2">
            <p className="leading-snug">{summary.summary}</p>
            {summary.key_decisions.length > 0 && (
              <div>
                <div className="text-xs font-medium text-muted-foreground mt-2">
                  Decisions
                </div>
                <ul className="list-disc list-inside text-xs space-y-0.5">
                  {summary.key_decisions.map((d, i) => (
                    <li key={i}>{d}</li>
                  ))}
                </ul>
              </div>
            )}
            {summary.open_questions.length > 0 && (
              <div>
                <div className="text-xs font-medium text-muted-foreground mt-2">
                  Open questions
                </div>
                <ul className="list-disc list-inside text-xs space-y-0.5">
                  {summary.open_questions.map((q, i) => (
                    <li key={i}>{q}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ProactiveBuckets({ surface }: { surface: ProactiveSurface }) {
  const buckets: Array<{ kind: ProactiveItem["kind"]; items: ProactiveItem[] }> = [
    { kind: "needs_response", items: surface.needs_response },
    { kind: "commitment_due", items: surface.commitments_due },
    { kind: "stalled", items: surface.stalled },
  ]
  const totalItems = buckets.reduce((n, b) => n + b.items.length, 0)
  if (totalItems === 0) {
    return (
      <Empty className="py-8">
        <EmptyHeader>
          <EmptyTitle className="text-sm">Inbox zero — nice.</EmptyTitle>
          <EmptyDescription className="text-xs">
            Nothing currently needs your attention.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }
  return (
    <>
      {buckets.map((b) =>
        b.items.length > 0 ? (
          <Bucket key={b.kind} kind={b.kind} items={b.items} />
        ) : null
      )}
      <Separator />
      <p className="text-[10px] text-muted-foreground text-center">
        Generated at {new Date(surface.generated_at).toLocaleString()}
      </p>
    </>
  )
}

function Bucket({ kind, items }: { kind: ProactiveItem["kind"]; items: ProactiveItem[] }) {
  const style = KIND_STYLE[kind]
  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
        <span>{style.icon}</span>
        <span>
          {style.label} <span className="font-normal">({items.length})</span>
        </span>
      </div>
      {items.map((item, idx) => (
        <Card key={idx} className={style.classes}>
          <CardContent className="py-3 space-y-1">
            <div className="flex items-start justify-between gap-2">
              <div className="text-sm font-medium leading-snug">{item.title}</div>
              <Badge variant="outline" className="text-[10px] shrink-0">
                {item.score}/10
              </Badge>
            </div>
            <div className="text-xs text-muted-foreground leading-snug">
              {item.detail}
            </div>
            <div className="text-[10px] italic text-muted-foreground/80">
              {item.why}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function DraftDrawer({
  open,
  onOpenChange,
  draft,
  loading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  draft: DraftReply | null
  loading: boolean
}) {
  const [body, setBody] = useState("")

  // Sync the draft body into the textarea once the response arrives.
  useEffect(() => {
    if (draft) setBody(draft.body)
  }, [draft])

  return (
    <Drawer direction="right" open={open} onOpenChange={onOpenChange}>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle>
            {loading ? "Drafting reply…" : draft ? draft.subject : "Draft reply"}
          </DrawerTitle>
        </DrawerHeader>
        <div className="flex flex-col gap-3 p-4">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Drafting…
            </div>
          )}
          {draft && (
            <>
              <Textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                className="min-h-[300px] text-sm"
              />
              {draft.tone_notes && (
                <p className="text-xs text-muted-foreground italic">
                  Tone: {draft.tone_notes}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                Drafts are AI-generated. Review before sending. (This panel
                doesn't actually send the email — copy the text and use the
                main reply button.)
              </p>
            </>
          )}
        </div>
        <DrawerFooter>
          <DrawerClose asChild>
            <Button variant="outline">Close</Button>
          </DrawerClose>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  )
}

// --- More insights (collapsible) ------------------------------------------

function MoreInsights() {
  const [open, setOpen] = useState(false)
  return (
    <div className="space-y-2">
      <Separator />
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setOpen((v) => !v)}
        className="w-full justify-start text-muted-foreground hover:text-foreground"
      >
        {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        More insights
      </Button>
      {open && (
        <div className="space-y-3">
          <StatsCard />
          <SynthesisCard />
        </div>
      )}
    </div>
  )
}

function StatsCard() {
  const [stats, setStats] = useState<StatsDashboard | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    agentApi
      .stats()
      .then((s) => !cancelled && setStats(s))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <BarChart3 className="size-4 text-violet-500" />
          Inbox stats
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
            <Loader2 className="size-4 animate-spin" /> Loading…
          </div>
        )}
        {error && <div className="text-sm text-red-500 break-all">{error}</div>}
        {stats && (
          <>
            {/* Three big stat tiles */}
            <div className="grid grid-cols-3 gap-2">
              <StatTile
                value={stats.total_emails}
                label="Total"
                tone="bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-900/60"
              />
              <StatTile
                value={stats.unread_count}
                label="Unread"
                tone={
                  stats.unread_count > 0
                    ? "bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-900/60"
                    : "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-900/60"
                }
              />
              <StatTile
                value={stats.thread_count}
                label="Threads"
                tone="bg-violet-50 dark:bg-violet-950/40 border-violet-200 dark:border-violet-900/60"
              />
            </div>

            {/* Facts list with proper rhythm */}
            <div className="space-y-2.5">
              <FactRow
                label="Busiest day"
                value={stats.busiest_day}
                badge={`${stats.busiest_day_count} emails`}
              />
              <FactRow
                label="Top sender"
                value={shortName(stats.most_frequent_sender)}
                badge={`${stats.most_frequent_sender_count} emails`}
              />
              <FactRow
                label="Longest thread"
                value={stats.longest_thread_subject}
                badge={`${stats.longest_thread_message_count} msgs`}
              />
              {stats.awaiting_reply_from.length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Awaiting reply from
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {stats.awaiting_reply_from.map((p) => (
                      <Badge
                        key={p}
                        variant="outline"
                        className="text-xs font-normal py-1 px-2"
                      >
                        {shortName(p)}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Narrative as a tinted callout */}
            {stats.narrative && (
              <div className="rounded-md border-l-4 border-violet-500 bg-violet-50/60 dark:bg-violet-950/20 p-3">
                <div className="text-[11px] uppercase tracking-wide font-semibold text-violet-600 dark:text-violet-400 mb-1.5 flex items-center gap-1">
                  <Sparkles className="size-3" />
                  AI summary
                </div>
                <p className="text-sm leading-relaxed">{stats.narrative}</p>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

function SynthesisCard() {
  const [topic, setTopic] = useState("")
  const [result, setResult] = useState<CrossThreadSynthesis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRun = async () => {
    if (!topic.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      setResult(await agentApi.synthesize(topic.trim()))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Search className="size-4 text-violet-500" />
          Cross-thread synthesis
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleRun()}
            placeholder='Try: "Phoenix" or "Initech"'
            className="text-sm"
          />
          <Button size="sm" onClick={handleRun} disabled={loading || !topic.trim()}>
            {loading ? (
              <>
                <Loader2 className="size-3.5 animate-spin" />
                <span className="ml-1">Running…</span>
              </>
            ) : (
              "Run"
            )}
          </Button>
        </div>

        {loading && (
          <p className="text-xs text-muted-foreground italic">
            Filtering relevant threads, then synthesizing — typically 30-60s on free tier.
          </p>
        )}
        {error && <div className="text-sm text-red-500 break-all">{error}</div>}

        {result && (
          <div className="space-y-3">
            {/* Hero status callout */}
            <div className="rounded-md border-l-4 border-violet-500 bg-violet-50/60 dark:bg-violet-950/20 p-3">
              <div className="text-[11px] uppercase tracking-wide font-semibold text-violet-600 dark:text-violet-400 mb-1.5 flex items-center gap-1">
                <Sparkles className="size-3" />
                Current status — {result.topic}
              </div>
              <p className="text-sm leading-relaxed">{result.current_status}</p>
            </div>

            {/* Threads as compact cards */}
            {result.threads.length > 0 && (
              <SectionBlock
                label={`Relevant threads (${result.threads.length})`}
                tone="neutral"
              >
                <div className="space-y-1.5">
                  {result.threads.map((t) => (
                    <div
                      key={t.thread_id}
                      className="rounded border bg-card p-2"
                    >
                      <div className="text-sm font-medium leading-snug">{t.subject}</div>
                      <div className="text-xs text-muted-foreground leading-snug mt-0.5">
                        {t.why_relevant}
                      </div>
                    </div>
                  ))}
                </div>
              </SectionBlock>
            )}

            {result.timeline.length > 0 && (
              <SectionBlock label="Timeline" tone="blue">
                <BulletList items={result.timeline} />
              </SectionBlock>
            )}

            {result.key_decisions.length > 0 && (
              <SectionBlock label="Decisions" tone="green">
                <BulletList items={result.key_decisions} />
              </SectionBlock>
            )}

            {result.blockers.length > 0 && (
              <SectionBlock label="Blockers" tone="red">
                <BulletList items={result.blockers} />
              </SectionBlock>
            )}

            {result.people_involved.length > 0 && (
              <SectionBlock label="People involved" tone="neutral">
                <div className="flex flex-wrap gap-1.5">
                  {result.people_involved.map((p) => (
                    <Badge
                      key={p}
                      variant="outline"
                      className="text-xs font-normal py-1 px-2"
                    >
                      {p}
                    </Badge>
                  ))}
                </div>
              </SectionBlock>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function StatTile({
  value,
  label,
  tone,
}: {
  value: number | string
  label: string
  tone: string
}) {
  return (
    <div className={`rounded-md border ${tone} p-2.5 text-center`}>
      <div className="text-2xl font-bold leading-none tabular-nums">{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1.5 font-medium">
        {label}
      </div>
    </div>
  )
}

function FactRow({
  label,
  value,
  badge,
}: {
  label: string
  value: string
  badge?: string
}) {
  return (
    <div className="flex items-start justify-between gap-2 text-sm">
      <div className="min-w-0 flex-1">
        <div className="text-xs text-muted-foreground uppercase tracking-wide font-medium">
          {label}
        </div>
        <div className="font-medium truncate">{value}</div>
      </div>
      {badge && (
        <Badge variant="secondary" className="text-[10px] shrink-0 mt-1">
          {badge}
        </Badge>
      )}
    </div>
  )
}

const TONE_CLASSES = {
  blue: "border-blue-200 dark:border-blue-900/60 bg-blue-50/40 dark:bg-blue-950/20",
  green: "border-emerald-200 dark:border-emerald-900/60 bg-emerald-50/40 dark:bg-emerald-950/20",
  red: "border-red-200 dark:border-red-900/60 bg-red-50/40 dark:bg-red-950/20",
  neutral: "border-border bg-muted/30",
} as const

const TONE_LABEL_CLASSES = {
  blue: "text-blue-700 dark:text-blue-400",
  green: "text-emerald-700 dark:text-emerald-400",
  red: "text-red-700 dark:text-red-400",
  neutral: "text-muted-foreground",
} as const

function SectionBlock({
  label,
  tone,
  children,
}: {
  label: string
  tone: keyof typeof TONE_CLASSES
  children: React.ReactNode
}) {
  return (
    <div className={`rounded-md border ${TONE_CLASSES[tone]} p-3 space-y-2`}>
      <div
        className={`text-[11px] uppercase tracking-wide font-semibold ${TONE_LABEL_CLASSES[tone]}`}
      >
        {label}
      </div>
      {children}
    </div>
  )
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5 text-sm">
      {items.map((it, i) => (
        <li key={i} className="leading-snug flex gap-2">
          <span className="text-muted-foreground shrink-0">•</span>
          <span>{it}</span>
        </li>
      ))}
    </ul>
  )
}

function shortName(email: string): string {
  // "sarah.chen@acme.com" → "sarah.chen"; leaves vendor emails intact.
  if (!email.endsWith("@acme.com")) return email
  return email.slice(0, email.indexOf("@"))
}
