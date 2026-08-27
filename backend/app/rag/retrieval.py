from flask import current_app

from app.rag import store

# A literal term match is a stronger signal than any cosine similarity, so keyword hits
# are scored above the range vector search reports (which stays below 1.0 in practice).
KEYWORD_SIMILARITY = 0.99

# Capped independent of RAG_TOP_K: a common word can match many chunks, and this fallback
# only needs to rescue the one the vector search missed, not flood the prompt.
KEYWORD_FALLBACK_LIMIT = 3


def _to_hit(cid, text, meta, similarity, rank):
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


def retrieve(query_text, k=None, query_log_id=None, document_id=None):
    """Top-k policy chunks for a natural-language query, best match first.

    An in-process function rather than a route: the agent's `search_policies` tool,
    `POST /ask`, and the benchmark harness all call it directly, so there is no network
    hop or shared secret to arrange.

    `query_log_id` is accepted but unused until `query_retrievals` exists (objective 3);
    taking it now keeps that from being a signature change. See docs/design-rag.md §6.

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
