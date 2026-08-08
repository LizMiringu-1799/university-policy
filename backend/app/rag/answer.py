import logging
import re
import time

from flask import current_app
from openai import OpenAI, OpenAIError, RateLimitError
from pydantic import BaseModel, ConfigDict, ValidationError

from app.rag.retrieval import retrieve

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You answer questions about university policy using only the numbered \
policy extracts provided with each question.

Rules:
- Use only the extracts. Never use outside knowledge about universities in general, and \
never guess at a figure, deadline, or procedure that is not written in them.
- Cite every factual claim with the number of the extract it came from, written inline in \
answer_md as [1], [2]. A sentence drawing on two extracts carries both, as [1][2].

Example of a well-formed answer_md:
  "Coursework loses 10% per day it is late [2]. After five days it scores zero [2]. \
Extensions need documentary evidence sent to the faculty office [5]."

- If the extracts do not answer the question, set answered to false and say plainly what \
is missing. Do not pad the answer with loosely related policy text. Cite nothing.
- If the question is not about university policy, set answered to false and say so.
- Write for a student: direct, a short paragraph or a few bullets, no preamble."""


class LlmAnswer(BaseModel):
    """Parsed response.

    Deliberately no `citations` field. Asked for one, the model concatenated the digits of
    the extracts it used: answering from 1, 4, 5 and 8 it emitted `[1458]`. Constraining
    the array with a JSON-schema enum did not help, because the provider validates the
    enum after generation and returns a 400 rather than decoding against it. The inline
    `[n]` markers in answer_md, meanwhile, come out correct, so those are parsed instead
    (`extract_citations`) and the array is not requested at all.
    """

    model_config = ConfigDict(extra="forbid")

    answered: bool
    answer_md: str


RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answered", "answer_md"],
    "properties": {
        "answered": {"type": "boolean"},
        "answer_md": {"type": "string"},
    },
}

# Matches [3] and [3][7], and tolerates [3, 7] which the model writes occasionally.
CITATION_MARKER = re.compile(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]")


def extract_citations(answer_md):
    """Source numbers cited inline in the answer, in order of first appearance."""
    numbers = []
    for group in CITATION_MARKER.findall(answer_md or ""):
        for part in group.split(","):
            number = int(part.strip())
            if number not in numbers:
                numbers.append(number)
    return numbers


_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = current_app.config["LLM_API_KEY"]
        if not api_key:
            raise RuntimeError("LLM_API_KEY is not set; add it to backend/.env")
        _client = OpenAI(
            api_key=api_key,
            base_url=current_app.config["LLM_BASE_URL"],
            timeout=current_app.config["LLM_TIMEOUT_SECONDS"],
            max_retries=2,
        )
    return _client


def reset_client():
    """Drop the cached client so config changes take effect. For tests and the CLI."""
    global _client
    _client = None


def render_sources(hits):
    """Number the retrieved chunks for the prompt. The numbers are what the model cites."""
    blocks = []
    for hit in hits:
        blocks.append(f"[{hit['rank']}] {hit['title']}, page {hit['page']}\n{hit['text']}")
    return "\n\n".join(blocks)


def _empty_result(question, reason):
    return {
        "log_id": None,
        "question": question,
        "answered": False,
        "answer_md": reason,
        "citations": [],
        "confidence": None,
        "response_ms": 0,
        "model": None,
    }


def answer_question(question, k=None, document_id=None):
    """Retrieve, then answer in a single grounded call. Returns the AnswerResult shape.

    Single-shot rather than an agent loop: with a fixed k the whole corpus slice already
    fits in context, so lazy retrieval buys nothing, and one call per question is what
    keeps this inside a free provider tier. Reasoning in docs/design-rag.md §9.

    `log_id` is always None until query_logs exists (objective 3).
    """
    question = (question or "").strip()
    if not question:
        return _empty_result(question, "Ask a question about a policy.")

    started = time.perf_counter()
    hits = retrieve(question, k=k, document_id=document_id)
    if not hits:
        return _empty_result(
            question,
            "No policy documents have been indexed yet, so there is nothing to search.",
        )

    model = current_app.config["LLM_MODEL"]
    try:
        completion = _get_client().chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=current_app.config["LLM_MAX_TOKENS"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"{render_sources(hits)}\n\nQuestion: {question}",
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "policy_answer",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                },
            },
        )
        parsed = LlmAnswer.model_validate_json(completion.choices[0].message.content)
    except RateLimitError as err:
        # Expected on a free tier, not an outage: the per-minute token ceiling is low
        # enough that two users asking at once can trip it. Distinguished so the UI can
        # say "try again shortly" instead of reporting a fault.
        logger.warning("Provider rate limit hit: %s", err)
        raise AnswerRateLimited("the answering service is rate limited") from err
    except (OpenAIError, ValidationError) as err:
        logger.exception("Answering failed for question %r", question[:120])
        raise AnswerError(str(err)) from err

    by_rank = {hit["rank"]: hit for hit in hits}
    citations = []
    for number in extract_citations(parsed.answer_md):
        # The marker still has to name a source that was actually offered. Drop anything
        # else rather than render a chip that points nowhere; `n` keeps the number the
        # reader sees in the text, so chips and markers line up even when non-contiguous.
        hit = by_rank.get(number)
        if not hit:
            logger.warning("Model cited source %s, which was not retrieved; dropping", number)
            continue
        citations.append(
            {
                "n": number,
                "document_id": hit["document_id"],
                "title": hit["title"],
                "version_id": hit["version_id"],
                "page": hit["page"],
                "chunk_id": hit["chunk_id"],
                "similarity": hit["similarity"],
            }
        )

    confidence = (
        sum(c["similarity"] for c in citations) / len(citations) if citations else None
    )
    threshold = current_app.config["RAG_CONFIDENCE_THRESHOLD"]
    answered = bool(parsed.answered and citations and confidence >= threshold)

    return {
        "log_id": None,
        "question": question,
        "answered": answered,
        "answer_md": parsed.answer_md,
        "citations": citations,
        "confidence": confidence,
        "response_ms": int((time.perf_counter() - started) * 1000),
        "model": model,
    }


class AnswerError(Exception):
    """The provider call or its response failed. Surfaced to the client as a 502."""


class AnswerRateLimited(AnswerError):
    """The provider's rate limit was hit. Surfaced as a 429 so the UI can invite a retry."""
