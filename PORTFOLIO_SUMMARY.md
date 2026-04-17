# SPEC-1 Intelligence Engine — Portfolio Summary

## What This Is

SPEC-1 is an automated open-source intelligence (OSINT) system built for real-time national security signal monitoring. It harvests, filters, investigates, and analyzes signals from authoritative sources — producing structured intelligence records and daily written briefs without manual intervention.

The system is designed to do one thing well: separate signal from noise in a high-volume information environment, and surface what actually matters to a human analyst.

---

## The Problem It Solves

Anyone working in national security, geopolitical risk, or threat intelligence faces the same daily reality: there is far more credible reporting than any human can process. Feeds from think tanks, investigative journalists, and defense research organizations produce dozens of new pieces every day. Most are not actionable. A small fraction are.

The challenge is not access to information — it is triage.

SPEC-1 automates that triage. It monitors a curated set of high-credibility sources continuously, evaluates each new signal through a structured scoring framework, and surfaces only those that clear every threshold. Signals that pass are handed off to an investigation and verification workflow powered by Claude. The result is a compressed, high-confidence set of intelligence records and a daily written brief — ready for human review without the noise.

---

## System Architecture

The system is built as a sequential pipeline with seven stages:

```
Harvest → Parse → Score → Investigate → Verify → Analyze → Store
```

Each stage transforms the data and gates what moves forward. A separate briefing module runs after the cycle completes, consuming the stored records to produce a structured daily brief. A FastAPI service wraps the pipeline for scheduled and on-demand operation.

### 1. Harvest

A harvester module fetches RSS/Atom feeds from a curated list of national security sources. These are authoritative publishers — think tanks, investigative outlets, and defense policy organizations with consistent editorial standards and subject matter expertise.

The harvester handles SSL edge cases, malformed XML, and timeout conditions gracefully. A failed feed does not stop the cycle — it is logged and skipped. The output is a collection of raw `Signal` objects, each carrying the source identifier, URL, raw text, author, publication timestamp, and available engagement metadata.

### 2. Parse

Each raw signal passes through a parser that strips HTML markup, extracts clean prose, identifies keywords and named entities, and measures content volume. The parser uses BeautifulSoup for HTML cleaning and applies lightweight NLP heuristics — no external model dependencies.

The output is a `ParsedSignal`: normalized text, a keyword set, an entity set, word count, and detected language.

### 3. Score (The Four-Gate Framework)

This is the core filtering layer. Every parsed signal must clear four independent gates to advance. Any single failure removes the signal from further processing.

The gates evaluate:

- **Credibility** — Is this source trustworthy? Each source carries an internal credibility rating based on editorial standards, domain expertise, and track record. Signals from lower-rated sources do not advance regardless of content.

- **Volume** — Does this signal contain sufficient substance? Brief posts and summaries are filtered out. Only signals with meaningful content depth continue.

- **Velocity** — Is this signal fresh? Intelligence value degrades rapidly. The scoring rewards recency and penalizes stale signals, with a sliding scale across time windows.

- **Novelty** — Does this signal touch high-value intelligence domains? A keyword evaluation checks for subject matter relevance — signals about inconsequential topics are excluded regardless of source credibility.

Signals clearing all four gates become `Opportunity` objects. Each carries a composite score that blends the four gate dimensions with specific weightings. Opportunities are classified by priority tier based on their composite score.

This framework is the engineered core of the system. The specific thresholds, weights, keyword taxonomy, and time-window parameters represent the accumulated judgment of what separates actionable intelligence signals from background noise. They are not published here.

### 4. Investigate

Each opportunity is handed to an investigation generator that constructs a structured `Investigation` object. This includes:

- A stated hypothesis about what the signal may indicate
- A set of research queries targeting authoritative external sources
- A list of analyst leads — known subject matter experts whose prior work is relevant to the domain

The analyst selection is domain-aware. Signals about Russian military operations surface different leads than signals about cyber operations or energy infrastructure. The system maintains an internal registry of analysts weighted by domain expertise and credibility.

### 5. Verify

Each investigation is submitted to Claude (Haiku model) for hypothesis verification. Claude evaluates the hypothesis against the available evidence and returns a structured classification:

- **Corroborated** — evidence supports the hypothesis
- **Escalate** — high-confidence, high-urgency finding
- **Investigate** — hypothesis plausible, more research needed
- **Monitor** — signal is real but not yet actionable
- **Conflicted** — evidence is contradictory
- **Archive** — signal does not warrant further attention

Each classification carries a confidence score. If the API call fails for any reason, the system falls back gracefully — the cycle continues and the failure is logged. The pipeline never crashes on a verification error.

### 6. Analyze

The analyzer synthesizes the signal, investigation, and verification outcome into a final `IntelligenceRecord`. This stage blends confidence signals from multiple sources — the verification confidence, source credibility, analyst credibility, and outcome classification — into a single composite confidence value.

The weighting of these blended inputs reflects the relative epistemic weight each source carries. A highly credible source with a corroborated hypothesis from a top-tier analyst carries more weight than a mid-tier source with a speculative outcome. These weights are calibrated, not arbitrary.

The analyzer also extracts a pattern description — a concise characterization of what the signal represents — and assigns a final domain classification.

### 7. Store

Completed `IntelligenceRecord` objects are written to a JSONL file via a thread-safe, append-only store. A threading lock enforces single-writer access. Records are never overwritten — the store is an immutable log. Filtering and counting operations are supported for downstream access.

---

## Quantitative Signal Domain

Alongside the text-based OSINT pipeline, SPEC-1 monitors a curated watchlist of publicly traded equities across four sectors: defense primes, cybersecurity vendors, energy majors, and macro instruments.

Market signals are processed through their own four-gate framework evaluating watchlist membership, relative volume, daily return magnitude, and deduplication. Signals clearing all four gates enter the same investigation, verification, and analysis pipeline as text signals.

The rationale: defense and cybersecurity equities often move on information that has not yet surfaced publicly in text form. Anomalous volume and price action in these names can be an early signal worth investigating.

---

## Daily Intelligence Brief

After each pipeline cycle, a briefing generator collects the scored intelligence records and calls Claude Sonnet to produce a structured written brief.

The brief follows a consistent format:

- Executive summary of cycle findings
- Elevated signals requiring immediate attention
- Domain briefings covering cyber and geopolitical developments separately
- Story leads for further investigation
- Watch list items for ongoing monitoring

Claude is prompted to write as a professional intelligence editor — precise, sourced, and without speculation beyond what the evidence supports. Every claim in the brief traces back to a scored signal. If the API call fails, a structured fallback brief is generated from the raw record data.

---

## API and Scheduling

A FastAPI application wraps the pipeline for operational use. The API exposes endpoints for:

- Triggering an immediate pipeline cycle
- Querying cycle status and statistics
- Retrieving recent signals, intelligence records, and briefs
- Kill-switch control for scheduled execution

The scheduler runs the pipeline on a fixed daily cron cadence. A kill-file mechanism allows operators to pause scheduled execution without modifying configuration. An environment variable enables an immediate run on service startup for operational testing.

---

## How the System Learns and Improves

SPEC-1 does not use a trained machine learning model in the traditional sense. There is no gradient descent, no neural network, no embedding space. The scoring framework is rule-based and deterministic.

But the system is designed to improve — through a different kind of learning.

### Calibration as Learning

The four-gate framework and the composite scoring weights are not fixed arbitrarily. They were developed through iterative exposure to the signal environment — observing what the system surfaced, evaluating whether those signals were genuinely actionable, and adjusting thresholds accordingly.

This is the same process a human analyst undergoes when developing judgment. The difference is that the rules are explicit, documented, and testable. When a threshold is wrong — when the system is surfacing too much noise or missing real signals — the failure is diagnosable. The specific threshold that failed can be identified and adjusted.

A neural network learns implicitly. SPEC-1 learns explicitly. The tradeoff is transparency and control in exchange for automation.

### Source Credibility as a Dynamic Signal

Source credibility ratings are not static. They reflect a judgment about a publisher's editorial standards, domain expertise, and historical accuracy. As publishers change — in quality, focus, or reliability — their ratings can be updated. A source that degrades in quality over time can be downweighted. A new authoritative source can be added with an initial credibility assessment.

This is a form of structured knowledge maintenance, analogous to how a human analyst updates their mental model of which sources to trust.

### Analyst Registry as Accumulated Knowledge

The analyst registry encodes domain expertise — which researchers and journalists have demonstrated sustained accuracy and depth in specific subject areas. This registry grows over time as new experts establish track records and existing analysts shift focus.

Connecting signal domains to specific analyst leads is itself a form of learned judgment. The initial mapping reflects prior research into the field. It can be expanded and refined as the system processes more signals and identifies patterns in which analysts' frameworks best explain what is observed.

### Outcome Feedback Loop (Structural)

The verification stage produces outcome classifications with confidence scores. Over time, the distribution of outcomes across sources, domains, and time periods is a structured dataset. Patterns in this data — sources that consistently produce corroborated signals, domains where the pipeline performs well or poorly, time periods with elevated signal density — are legible from the stored JSONL records.

This data can drive calibration decisions. A source that consistently produces high-confidence corroborated signals may warrant a credibility upgrade. A domain where the system regularly classifies signals as "Monitor" but human review finds them actionable suggests a threshold that needs adjustment.

The system does not automate this feedback loop — that would require human validation data that the current architecture does not collect. But the data structure supports it. The path from observation to calibration is clear.

### Test Suite as a Learning Anchor

The system has 145 tests with 97% coverage. This is not incidental — it is structural. The test suite encodes expected system behavior. When a threshold or weight changes during calibration, the tests verify that the change does not break intended behavior elsewhere. This makes calibration safe: changes can be made and validated without fear of silent regressions.

The tests also document assumptions. When a gate threshold is tested with a specific boundary case, that test is a record of a decision — why this threshold, not a looser or tighter one. The test suite is, in a real sense, a changelog of accumulated judgment.

---

## What Is Not Here

This document does not publish:

- Specific gate thresholds or cutoff values
- Composite scoring weights or their derivation
- The keyword taxonomy used for novelty detection
- Individual source credibility ratings
- Individual analyst credibility scores or the weighting scheme

These are the calibrated parameters that represent the operational intelligence of the system. They are the result of iterative refinement and constitute the functional differentiation of SPEC-1 from a naive feed aggregator. They are not appropriate for public documentation.

---

## Technical Summary

| Dimension | Detail |
|---|---|
| Language | Python 3.11+ |
| Pipeline stages | 7 (harvest → store) |
| Signal sources | RSS feeds from 6 authoritative publishers |
| Scoring framework | 4-gate deterministic filtering |
| AI integration | Claude Haiku (verification), Claude Sonnet (briefing) |
| Market signals | 4-sector equity watchlist via yfinance |
| Persistence | Append-only JSONL with thread-safe writes |
| API | FastAPI with APScheduler for daily cron |
| Test coverage | 97% (145 tests) |
| Architecture version | v0.2.0 |

---

## Why This Matters

The bottleneck in intelligence work is not information — it is attention. SPEC-1 is designed to protect analyst attention by doing the triage work that does not require human judgment: fetching, cleaning, filtering, and structuring. What reaches the human is already scored, investigated, verified, and written up.

The human role is then what it should be: evaluating the findings, directing follow-on research, and making decisions. The system handles the volume. The analyst handles the judgment.

That division of labor is the point.
