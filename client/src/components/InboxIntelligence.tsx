import { useEffect, useState } from "react"
import { Sparkles, AlertCircle, RefreshCw, Loader2, FileText } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription } from "@/components/ui/empty"
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
  DraftReply,
  ProactiveItem,
  ProactiveSurface,
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
