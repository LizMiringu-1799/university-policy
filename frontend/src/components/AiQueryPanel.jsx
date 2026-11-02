import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { queriesApi, escalationsApi } from "../api/client.js";
import Alert from "./Alert.jsx";
import AnswerBody from "./AnswerBody.jsx";
import AnswerRating from "./AnswerRating.jsx";
import Button from "./Button.jsx";
import TextField from "./TextField.jsx";

/** A per-panel session id for query logging. randomUUID needs a secure context, which
 * localhost and https both are; the fallback covers a plain-http LAN deployment. */
function newSessionId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * The "ask a question about policy" widget, reused corpus-wide on the library page and
 * scoped to one policy (via `documentId`) on the reader page. Submits to POST /ask, then
 * renders the cited answer with clickable source links, and drives the human-escalation
 * handoff: automatically forwards the question to an admin when the system can't answer
 * it, and offers a "Request clarification" button when it can. Each answer carries a
 * thumbs up/down (AnswerRating) keyed by the query log id the server returns.
 */
export default function AiQueryPanel({
  as: Container = "aside",
  className = "ai-panel",
  fieldId,
  title,
  placeholder,
  documentId,
}) {
  const { token } = useAuth();
  // One id per mount: every question asked from this panel is logged under it.
  const [sessionId] = useState(newSessionId);
  const [question, setQuestion] = useState("");
  const [askedQuestion, setAskedQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // null | "sending" | "sent" | "error" — tracks the handoff to an admin for the
  // question currently shown, whether triggered automatically or by the button below.
  const [escalation, setEscalation] = useState(null);

  /** Ask the question, show the answer, and auto-escalate to an admin if unanswered. */
  async function handleSubmit(e) {
    e.preventDefault();
    const asked = question.trim();
    if (!asked || loading) return;

    setError("");
    setResult(null);
    setEscalation(null);
    setAskedQuestion(asked);
    setLoading(true);
    try {
      const data = await queriesApi.ask(asked, token, documentId, sessionId);
      setResult(data);
      if (!data.answered) {
        // The policies don't cover this, so route it to an admin without making the
        // student ask twice for something the system already knows it can't answer.
        sendToAdmin(asked, data, "unanswered");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  /** POST an escalation for the current question/answer pair. `reason` is "unanswered"
   * (fired automatically) or "clarification" (fired by the button below). */
  async function sendToAdmin(asked, data, reason) {
    setEscalation("sending");
    try {
      await escalationsApi.create(
        {
          question: asked,
          reason,
          document_id: documentId,
          // Links the handoff to the logged exchange, so the admin queue can show the
          // rating the student leaves on this answer (often just after escalating).
          query_log_id: data.log_id,
          system_answer_md: data.answer_md,
          system_confidence: data.confidence,
        },
        token
      );
      setEscalation("sent");
    } catch {
      setEscalation("error");
    }
  }

  const citedPages = {};
  for (const c of result?.citations || []) {
    citedPages[c.n] = { label: `${c.title}, page ${c.page}`, documentId: c.document_id, page: c.page };
  }

  return (
    <Container className={className}>
      <h2>{title}</h2>
      <form onSubmit={handleSubmit}>
        <TextField
          id={fieldId}
          label="Your question"
          placeholder={placeholder}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={loading}
        />
        <Button type="submit" disabled={loading || !question.trim()}>
          {loading ? "Searching policies..." : "Ask"}
        </Button>
      </form>

      <Alert>{error}</Alert>

      {result && (
        <div className="ai-answer">
          <div className="ai-answer-body">
            <AnswerBody text={result.answer_md} citedPages={citedPages} />
          </div>

          {result.citations.length > 0 && (
            <div className="ai-sources">
              <h3>Sources</h3>
              <ol>
                {result.citations.map((c) => (
                  <li key={c.chunk_id} value={c.n}>
                    <Link to={`/policies/${c.document_id}?page=${c.page}`}>{c.title}</Link>
                    <Link to={`/policies/${c.document_id}?page=${c.page}`} className="ai-source-page">
                      page {c.page}
                    </Link>
                  </li>
                ))}
              </ol>
            </div>
          )}

          <div className="ai-answer-meta">
            {result.answered ? (
              <span className="ai-confidence">
                confidence {Math.round(result.confidence * 100)}%
              </span>
            ) : (
              <span className="ai-unanswered">not covered by the indexed policies</span>
            )}
          </div>

          {/* Shown for unanswered results too: a thumbs-down there flags a policy the
              system wrongly said it doesn't cover, which is the most useful signal. */}
          {result.log_id != null && <AnswerRating key={result.log_id} logId={result.log_id} />}

          {result.answered ? (
            <div className="ai-escalation">
              {escalation === "sent" ? (
                <span className="ai-escalation-status">Sent to an admin — check back for their reply.</span>
              ) : (
                <Button
                  variant="secondary"
                  disabled={escalation === "sending"}
                  onClick={() => sendToAdmin(askedQuestion, result, "clarification")}
                >
                  {escalation === "sending" ? "Sending..." : "Request clarification from admin"}
                </Button>
              )}
              {escalation === "error" && <span className="field-error">could not reach an admin, try again</span>}
            </div>
          ) : (
            <div className="ai-escalation">
              {escalation === "sending" && <span className="ai-escalation-status">Forwarding to an admin...</span>}
              {escalation === "sent" && (
                <span className="ai-escalation-status">
                  This wasn't in the indexed policies, so it's been sent to an admin — check back for their reply.
                </span>
              )}
              {escalation === "error" && (
                <span className="field-error">
                  couldn't reach an admin automatically — try asking again
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </Container>
  );
}
