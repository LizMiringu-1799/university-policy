import { Link } from "react-router-dom";

// Splits an answer on its [n] citation markers so they can be rendered as chips.
const MARKER = /\[\s*\d+(?:\s*,\s*\d+)*\s*\]/g;

/**
 * Render one line of answer text with its [n] citation markers replaced by superscript
 * chips: a clickable Link (with page number, styled `.cite`) when `n` resolves to a
 * retrieved source in `citedPages`, or a plain unlinked marker otherwise (the marker is
 * still shown so the answer's phrasing isn't silently changed, just not clickable —
 * e.g. chat history, where per-citation page numbers aren't stored, see queries.py).
 */
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
/** Render the LLM's answer_md as paragraphs and "- "/"* " bullet lists, with citation
 * markers on each line turned into chips via renderLine(). `citedPages` (a {n: {label,
 * documentId, page}} map) is optional — omit it where per-citation pages aren't stored
 * (chat history) and every marker renders as a plain, unlinked superscript. */
export default function AnswerBody({ text, citedPages = {} }) {
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

  for (const line of (text || "").split("\n")) {
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
