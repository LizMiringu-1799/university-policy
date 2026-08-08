import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { queriesApi } from "../api/client.js";
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
      parts.push(
        <sup key={`${match.index}-${n}`} className="cite" title={citedPages[n] || `Source ${n}`}>
          {n}
        </sup>
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
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    const asked = question.trim();
    if (!asked || loading) return;

    setError("");
    setResult(null);
    setLoading(true);
    try {
      setResult(await queriesApi.ask(asked, token, documentId));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const citedPages = {};
  for (const c of result?.citations || []) {
    citedPages[c.n] = `${c.title}, page ${c.page}`;
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
                    <Link to={`/policies/${c.document_id}`}>{c.title}</Link>
                    <span className="ai-source-page">page {c.page}</span>
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
        </div>
      )}
    </Container>
  );
}
