# Project Objectives

Rewritten 2026-07-31 following lecturer feedback: objectives follow the SMART approach (Specific, Measurable, Achievable, Relevant, Time-bound). Role-based access is a design feature, not an objective; it lives in the system design under the admin module.

Revised 2026-08-06: objectives 1 and 2 (repository, admin module) merged into a single objective, since the admin module's upload action already implements the repository's upload requirement, there was no separate build for each. Objective 5 (analytics dashboard) added; it reads data objective 3 already logs, so it adds no new data-collection requirement and does not extend the 9-week timeline.

Revised 2026-08-08: objective 2 delivered. No objective, measure, or timeline changed; this note records the implementation choices behind the wording, since "LLM" was left open deliberately. The answering model is `openai/gpt-oss-120b` on Groq's free tier, reached over an OpenAI-compatible endpoint so the provider is configuration rather than code. Two consequences worth recording for the write-up: the platform now runs at **zero marginal cost per query**, and answers are produced by a **single grounded call** rather than the tool-use agent loop originally planned. Reasoning and the measured evidence are in [design-rag.md](design-rag.md) §9 and [implementation-plan.md](implementation-plan.md) §1.

## Main Objective

To develop and empirically evaluate a centralized web platform that hosts university policy documents and answers natural-language policy questions through retrieval-augmented generation (RAG).

## Specific Objectives

| # | Objective (SMART) | Timeline | Measure of success |
|---|---|---|---|
| 1 | To develop, by the end of Week 2, a centralized web platform for university policy documents: PDF upload and storage into a single hosted repository. | Weeks 1–2 | Platform hosts an initial corpus of ≥30 policy documents, and an administrator completes an add → replace → archive cycle entirely through the UI. |
| 2 | To integrate, by the end of Week 4, a RAG pipeline (vector embeddings + LLM, Chroma) that answers natural-language questions with citations to source policies. | Weeks 3–4 | ≥80% top-k retrieval precision on a benchmark set of 50 test questions. |
| 3 | To deploy the system, by the end of Week 6, to a test group of ≥20 users for a two-week period, logging every query (text, timestamp, retrieved documents, confidence score, unanswered queries) to the `QueryLog` table. | Weeks 5–6 | Dataset of ≥200 logged queries from real users. |
| 4 | To analyze the collected data, by the end of Week 9, benchmarking retrieval accuracy and identifying the most frequently queried and most ambiguous policies. | Weeks 7–9 | Evaluation report with accuracy metrics and policy-ambiguity charts for university leadership. |
| 5 | To surface, by the end of Week 6, the data objective 3 already logs through a live admin analytics dashboard: query volume over time, answered-vs-unanswered rate, and most-queried and most-ambiguous policies. | Week 6 (concurrent with objective 3) | Dashboard renders all four metrics live from the `QueryLog` table objective 3 already populates, no new logging beyond it. |

Total duration: 9 weeks. Objective 5 runs concurrently with objective 3, it reads the same data objective 3 is already committed to collecting, so it does not extend the timeline.

## Notes

- Target numbers (30 documents, 20 users, 200 queries, 80% precision) are working defaults; adjust to cohort size and supervisor guidance.
- Objective 2's measure is a **retrieval** metric: for each of 50 questions with labelled source documents, a hit is a labelled document appearing in top-k. It is computed without calling the language model at all, so the number can be produced and re-produced at no cost. Report it as recall@k as well as "top-k retrieval precision", so a reader checking the arithmetic is not misled (see [implementation-plan.md](implementation-plan.md) §7).
- The platform incurs no per-query cost: embeddings run locally and the answering model is on a free tier. This is a deliberate constraint, not an accident, and the design keeps the provider swappable so a paid model can be substituted for a quality comparison without rework.
- Objective 5 is deliberately scoped to read-only reporting on existing data. If it turns out to need a metric objective 3 doesn't already log, that's new scope for objective 3, not a silent expansion of objective 5.
