import { useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { queriesApi } from "../api/client.js";
import Button from "./Button.jsx";
import ThumbIcon from "./ThumbIcon.jsx";

/**
 * Thumbs up/down on one answer, identified by its query log id. Rendered with
 * `key={logId}` so each new answer starts fresh.
 *
 * The rating is posted the moment a thumb is clicked, so a user who then walks away has
 * still been counted; a comment box follows (opened automatically for a fresh thumbs
 * down, where the reason is the useful part) and sending it re-posts the same rating
 * with the text. Clicking the other thumb afterwards changes the rating and keeps the
 * comment. `initialRating`/`initialComment` seed an existing rating (chat history
 * showing a past answer already rated) rather than starting from "Was this helpful?".
 */
export default function AnswerRating({ logId, initialRating = null, initialComment = "" }) {
  const { token } = useAuth();
  const [rating, setRating] = useState(initialRating); // "up" | "down" once chosen
  const [comment, setComment] = useState(initialComment);
  const [commentOpen, setCommentOpen] = useState(false);
  const [justSent, setJustSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const hasComment = comment.trim().length > 0;

  /** POST the rating (and the comment, when given). Returns whether it succeeded. */
  async function send(payload) {
    setBusy(true);
    setError("");
    try {
      await queriesApi.feedback(logId, payload, token);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function rate(next) {
    if (busy || next === rating) return;
    const previous = rating;
    setRating(next);
    const ok = await send({ rating: next });
    if (!ok) {
      setRating(previous);
      return;
    }
    if (previous === null && next === "down") setCommentOpen(true);
  }

  async function submitComment(e) {
    e.preventDefault();
    const text = comment.trim();
    if (!text || busy) return;
    const ok = await send({ rating, comment: text });
    if (ok) {
      setJustSent(true);
      setCommentOpen(false);
    }
  }

  return (
    <div className="ai-rating">
      <div className="ai-rating-row">
        <span>{rating ? "Thanks for your feedback." : "Was this helpful?"}</span>
        <button
          type="button"
          className={`ai-rating-btn${rating === "up" ? " selected" : ""}`}
          aria-label="Helpful"
          aria-pressed={rating === "up"}
          disabled={busy}
          onClick={() => rate("up")}
        >
          <ThumbIcon />
        </button>
        <button
          type="button"
          className={`ai-rating-btn${rating === "down" ? " selected" : ""}`}
          aria-label="Not helpful"
          aria-pressed={rating === "down"}
          disabled={busy}
          onClick={() => rate("down")}
        >
          <ThumbIcon down />
        </button>
        {rating && !commentOpen && (
          <button type="button" className="ai-rating-link" onClick={() => setCommentOpen(true)}>
            {hasComment ? "Edit comment" : "Add a comment"}
          </button>
        )}
      </div>

      {rating && commentOpen && (
        <form className="ai-rating-comment" onSubmit={submitComment}>
          <textarea
            rows={2}
            maxLength={1000}
            placeholder={rating === "down" ? "What was wrong with this answer?" : "Add a comment"}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={busy}
            aria-label="Comment on this answer"
          />
          <Button type="submit" variant="secondary" disabled={busy || !comment.trim()}>
            {busy ? "Sending..." : "Send"}
          </Button>
        </form>
      )}

      {justSent && <span className="ai-rating-status">Comment sent.</span>}
      {error && <span className="field-error">{error}</span>}
    </div>
  );
}
