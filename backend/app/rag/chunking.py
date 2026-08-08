import re

# Split after . ! ? or a numbered clause heading, when followed by whitespace and a
# capital/digit. Policy documents are full of "3.1 Late submission." style headings,
# and treating those as boundaries keeps a clause with its own heading.
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def split_sentences(text):
    return [s.strip() for s in SENTENCE_END.split(text) if s.strip()]


def _split_oversized(sentence, max_chars):
    """A single sentence longer than the hard cap, cut on word boundaries."""
    words = sentence.split(" ")
    pieces, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            pieces.append(current)
            current = word
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def chunk_page(text, target_chars, max_chars, overlap_chars):
    """Split one page into sentence-aligned chunks of roughly target_chars.

    Sized to the embedding model's input window rather than the LLM's: anything past
    ~256 word pieces is truncated before it reaches the vector, so a bigger chunk would
    be partly unretrievable. See docs/design-rag.md §1.
    """
    sentences = []
    for sentence in split_sentences(text):
        if len(sentence) > max_chars:
            sentences.extend(_split_oversized(sentence, max_chars))
        else:
            sentences.append(sentence)

    chunks, current = [], []

    def flush():
        if current:
            chunks.append(" ".join(current))

    for sentence in sentences:
        candidate_length = sum(len(s) + 1 for s in current) + len(sentence)
        if current and candidate_length > target_chars:
            flush()
            current = _overlap_tail(current, overlap_chars)
        current.append(sentence)

    flush()
    return chunks


def _overlap_tail(sentences, overlap_chars):
    """The trailing sentences of the chunk just emitted, up to overlap_chars.

    Carrying whole sentences rather than a raw character slice keeps the overlap
    readable, since any chunk can end up quoted as a citation.
    """
    tail, length = [], 0
    for sentence in reversed(sentences):
        if length + len(sentence) > overlap_chars:
            break
        tail.insert(0, sentence)
        length += len(sentence) + 1
    return tail


def build_chunks(pages, title, target_chars, max_chars, overlap_chars):
    """[(page_number, text)] -> [{page, chunk_index, text}] with the title/page prefix.

    The prefix is what carries document identity into the vector: without it a chunk
    reading "the penalty is 10% per day" has nothing for a query naming the policy to
    match on. Chunks never span pages, so each one has a single page to cite.
    """
    results = []
    for page_number, page_text in pages:
        for chunk in chunk_page(page_text, target_chars, max_chars, overlap_chars):
            results.append(
                {
                    "page": page_number,
                    "chunk_index": len(results),
                    "text": f"{title}, page {page_number}: {chunk}",
                }
            )
    return results
