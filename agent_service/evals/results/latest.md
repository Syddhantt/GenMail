# GenMail Agent Service — Eval Results

_Run at 2026-05-02T15:41:12, took 44.5s._

Each feature is run against hand-labeled ground truth in `evals/ground_truth.json`.
Headline metric per row:
- F7 Thread State: multi-class accuracy across 13 threads.
- F6 Urgency: precision/recall on the HIGH+CRITICAL bucket (the one that matters most for triage).
- F5 Commitments: precision/recall vs hand-listed commitments per sent email. Substring match on recipient + what.
- F10 Cross-Thread Relevance: precision/recall on which threads get pulled per topic.

| Feature | n | Precision | Recall | F1 |
|---------|---|-----------|--------|-----|
| F7 Thread State | 13 | 1.00 | 1.00 | 1.00 |
| F6 Urgency | 7 | 1.00 | 1.00 | 1.00 |
| F5 Commitments | 4 | 1.00 | 0.75 | 0.86 |
| F10 Cross-Thread Relevance | 12 | 0.73 | 0.92 | 0.81 |

## Per-feature notes

### F7 Thread State
- Items checked: **13**, correct: **13**.

### F6 Urgency
- Items checked: **7**, correct: **5**.
- Notes:
  [email_id=8] ERROR: ConnectTimeout: 
  [email_id=14] expected LOW, got MEDIUM (score=5)
  Overall multi-class accuracy: 0.71

### F5 Commitments
- Items checked: **4**, correct: **3**.
- Notes:
  [email_id=7] missed: Sarah / stakeholders
  Placeholder violations: 0 (must be 0)

### F10 Cross-Thread Relevance
- Items checked: **12**, correct: **11**.
- Notes:
  [Phoenix] missed: ['mobile-offline-002']
  [Mobile v2.0] over-included: ['meeting-008', 'phoenix-timeline-001']
  [Initech] over-included: ['enterprise-dash-004', 'phoenix-timeline-001']
