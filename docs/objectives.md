# Project Objectives

Rewritten 2026-07-31 following lecturer feedback: objectives follow the SMART approach (Specific, Measurable, Achievable, Relevant, Time-bound). Role-based access is a design feature, not an objective; it lives in the system design under the admin module.

## Main Objective

To develop and empirically evaluate a centralized web platform that hosts university policy documents and answers natural-language policy questions through retrieval-augmented generation (RAG).

## Specific Objectives

| # | Objective (SMART) | Measure of success |
|---|---|---|
| 1 | To develop, by [Week X], a web platform that centralizes university policy documents into a single hosted repository with PDF upload and storage. | Platform hosts an initial corpus of ≥30 policy documents. |
| 2 | To implement, by [Week X], an administration module for maintaining the repository: adding new policies, replacing outdated versions, and archiving retired ones. | An administrator completes each maintenance action end to end. |
| 3 | To integrate, by [Week X], a RAG pipeline (vector embeddings + LLM, Chroma) that answers natural-language questions with citations to source policies. | ≥80% top-k retrieval precision on a benchmark set of 50 test questions. |
| 4 | To deploy the system, by [Week X], to a test group of ≥20 users for a two-week period, logging every query (text, timestamp, retrieved documents, confidence score, unanswered queries) to the `QueryLog` table. | Dataset of ≥200 logged queries from real users. |
| 5 | To analyze the collected data, by [Week X], benchmarking retrieval accuracy and identifying the most frequently queried and most ambiguous policies. | Evaluation report with accuracy metrics and policy-ambiguity charts for university leadership. |

## Notes

- [Week X] dates need binding to the module timetable.
- Target numbers (30 documents, 20 users, 200 queries, 80% precision) are working defaults; adjust to cohort size and supervisor guidance.
