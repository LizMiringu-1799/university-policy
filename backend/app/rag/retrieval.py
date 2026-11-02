from flask import current_app

from app.rag import store

# A literal term match is a stronger signal than any cosine similarity, so keyword hits
# are scored above the range vector search reports (which stays below 1.0 in practice).
KEYWORD_SIMILARITY = 0.99

# Capped independent of RAG_TOP_K: a common word can match many chunks, and this fallback
# only needs to rescue the one the vector search missed, not flood the prompt.
KEYWORD_FALLBACK_LIMIT = 3


def _to_hit(cid, text, meta, similarity, rank):
    """Build one retrieval result dict from a chunk's id, text, and Chroma metadata.
    Shared by both the vector-search and keyword-fallback branches of retrieve() so the
    two produce identically-shaped hits."""
    return {
        "chunk_id": cid,
        "document_id": meta["document_id"],
        "version_id": meta["version_id"],
        "version_number": meta["version_number"],
        "title": meta["title"],
        "category": meta["category"],
        "page": meta["page"],
        "text": text,
        "similarity": similarity,
        "rank": rank,
    }


def retrieve(query_text, k=None, document_id=None):
    """Top-k policy chunks for a natural-language query, best match first.

    An in-process function rather than a route: `POST /ask` and the `flask search` CLI
    command both call it directly, so there is no network hop or shared secret to
    arrange.

    Stays side-effect-free with respect to query_retrievals (objective 3): logging every
    retrieved chunk needs the QueryLog row it belongs to, which doesn't exist until after
    the whole exchange is answered, not at retrieval time. `answer_question()` returns
    its hits back up to the /ask route instead, which logs them once the row does exist
    — see queries.py's `_log_retrievals`. An earlier plan threaded a `query_log_id`
    parameter through here for the same purpose; dropped because it would require
    creating that row before retrieval even runs.

    No status filter is applied, and none is needed: the index holds exactly the current
    version of every active document, because archiving and version replacement delete
    the chunks that should no longer be searchable (docs/design-rag.md §3).
    """
    query_text = (query_text or "").strip()
    if not query_text:
        return []

    k = k or current_app.config["RAG_TOP_K"]
    result = store.query(query_text, k, document_id=document_id)

    ids = result["ids"][0]
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]

    hits = []
    seen = set()
    for cid, text, meta, distance in zip(ids, documents, metadatas, distances):
        # Chroma deletes metadata synchronously but its vector index lags behind, so a
        # just-archived document's chunks can still come back from the nearest-neighbour
        # search with metadata of None. Metadata is the authoritative record of what is
        # in the index, so a hit without it is a deleted chunk and is dropped. Skipping
        # can return fewer than k results, which is correct: the alternative is quoting
        # a policy that was archived.
        if not meta:
            continue

        # Chroma reports cosine distance; the collection pins the cosine space so this is
        # 1 - cosine similarity. Clamped because floating point can put an exact match a
        # hair outside the range.
        similarity = max(0.0, min(1.0, 1.0 - distance))
        hits.append(_to_hit(cid, text, meta, similarity, len(hits) + 1))
        seen.add(cid)

    # Keyword fallback: dense embeddings rank on topic, not tokens, so an exact term (a
    # place name, a policy code) can miss the vector top-k entirely even though a chunk
    # contains it verbatim. Splice in anything the substring scan finds that vector search
    # didn't already surface.
    for cid, text, meta in store.keyword_query(query_text, KEYWORD_FALLBACK_LIMIT, document_id=document_id):
        if cid in seen:
            continue
        hits.append(_to_hit(cid, text, meta, KEYWORD_SIMILARITY, len(hits) + 1))
        seen.add(cid)

    return hits
