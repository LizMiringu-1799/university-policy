import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { queriesApi, escalationsApi } from "../api/client.js";
import Alert from "./Alert.jsx";
import Button from "./Button.jsx";
import TextField from "./TextField.jsx";

// Splits an answer on its [n] citation markers so they can be rendered as chips.
const MARKER = /\[\s*\d+(?:\s*,\s*\d+)*\s*\]/g;

function renderLine(line, citedPages) {
  const parts = [];
  let cursor = 0;
  for (const match of line.matchAll(MARKER)) {
    if (match.index > cursor) parts.push(line.slice(cursor, match.index));
    const numbers = match[0].replace(/[[\]\s]/g, "").split(",");
    for (const raw of numbers) {
      const n = Number(raw);
      const citation = citedPages[n];
      parts.push(
        citation ? (
          <Link
            key={`${match.index}-${n}`}
            to={`/policies/${citation.documentId}?page=${citation.page}`}
            className="cite"
            title={citation.label}
          >
            {n}
          </Link>
        ) : (
          <sup key={`${match.index}-${n}`} className="cite" title={`Source ${n}`}>
            {n}
          </sup>
        )
      );
    }
    cursor = match.index + match[0].length;
  }
  if (cursor < line.length) parts.push(line.slice(cursor));
  return parts;
}

// The answer is light markdown: paragraphs plus "- " bullets. Rendering those two cases
// directly avoids pulling in a markdown dependency for output we control the shape of.
function AnswerBody({ text, citedPages }) {
  const blocks = [];
  let bullets = [];

  const flush = () => {
    if (bullets.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`}>
          {bullets.map((b, i) => (
            <li key={i}>{renderLine(b, citedPages)}</li>
          ))}
        </ul>
      );
      bullets = [];
    }
  };

  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) {
      flush();
    } else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      bullets.push(trimmed.slice(2));
    } else {
      flush();
      blocks.push(<p key={`p-${blocks.length}`}>{renderLine(trimmed, citedPages)}</p>);
    }
  }
  flush();
  return blocks;
}

export default function AiQueryPanel({
  as: Container = "aside",
  className = "ai-panel",
  fieldId,
  title,
  placeholder,
  documentId,
}) {
  const { token } = useAuth();
  const [question, setQuestion] = useState("");
  const [askedQuestion, setAskedQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // null | "sending" | "sent" | "error" — tracks the handoff to an admin for the
  // question currently shown, whether triggered automatically or by the button below.
  const [escalation, setEscalation] = useState(null);

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
      const data = await queriesApi.ask(asked, token, documentId);
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

  async function sendToAdmin(asked, data, reason) {
    setEscalation("sending");
    try {
      await escalationsApi.create(
        {
          question: asked,
          reason,
          document_id: documentId,
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
