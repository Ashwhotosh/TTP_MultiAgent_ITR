"""
vector_store.py -- ChromaDB vector store for semantic retrieval.

Used by OptimizerAgent for open-ended strategy discovery.
Complements PageIndex (structured verification lookups).

Corpus: CBDT circulars, section text, worked examples.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class VectorStore:
    """ChromaDB-backed semantic search over tax knowledge corpus."""

    def __init__(self, persist_dir: str = "./data/chroma_db",
                 collection_name: str = "tax_corpus"):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._embedder = None

    def _ensure_loaded(self):
        """Lazy-load ChromaDB client and sentence-transformer."""
        if self._client is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(path=self.persist_dir)
                self._collection = self._client.get_or_create_collection(
                    self.collection_name
                )
            except Exception as e:
                print(f"[VECTOR_STORE] ChromaDB init failed: {e}")
                self._client = "FALLBACK"

        if self._embedder is None and self._client != "FALLBACK":
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as e:
                print(f"[VECTOR_STORE] Embedder init failed: {e}")
                self._embedder = "FALLBACK"

    def build_index(self, corpus_path: str = "corpus/") -> int:
        """Build vector index from corpus. Returns chunk count.

        Loads from itr_text_corpus.py and itr_knowledge_base.json,
        chunks into ~200 token segments, embeds and stores.
        """
        self._ensure_loaded()

        if self._client == "FALLBACK" or self._embedder == "FALLBACK":
            print("[VECTOR_STORE] Running in fallback mode - no embedding")
            return 0

        corpus_dir = Path(corpus_path)
        chunks = []

        # Load from itr_text_corpus.py
        try:
            from corpus.itr_text_corpus import ITR_CORPUS
            for node_id, node in ITR_CORPUS.items():
                if node_id == "root":
                    continue
                text = node.get("full_text") or node.get("summary", "")
                if text:
                    # Split into chunks of ~200 tokens (~800 chars)
                    for i, chunk in enumerate(self._chunk_text(text, max_chars=800)):
                        chunks.append({
                            "id": f"corpus_{node_id}_{i}",
                            "text": chunk,
                            "metadata": {
                                "source": "itr_text_corpus",
                                "section": node.get("title", node_id),
                                "node_id": node_id,
                            },
                        })
        except ImportError:
            print("[VECTOR_STORE] Could not import itr_text_corpus")

        # Load from itr_knowledge_base.json
        kb_path = corpus_dir / "itr_knowledge_base.json"
        if kb_path.exists():
            import json
            kb = json.loads(kb_path.read_text(encoding="utf-8"))
            # Index deduction sections
            for regime_key in ("old_regime", "new_regime"):
                regime = kb.get(regime_key, {})
                deductions = regime.get("deductions", regime.get("allowed_deductions", {}))
                for section_key, section_data in deductions.items():
                    if isinstance(section_data, dict):
                        text = f"Section {section_data.get('section', section_key)}: "
                        text += f"{section_data.get('title', '')}. "
                        text += f"Max limit: {section_data.get('max_limit', 'N/A')}. "
                        if section_data.get('note'):
                            text += section_data['note']
                        chunks.append({
                            "id": f"kb_{regime_key}_{section_key}",
                            "text": text,
                            "metadata": {
                                "source": "knowledge_base",
                                "section": section_data.get('section', section_key),
                                "regime": regime_key,
                            },
                        })

        if not chunks:
            return 0

        # Embed and store
        texts = [c["text"] for c in chunks]
        ids = [c["id"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        embeddings = self._embedder.encode(texts, show_progress_bar=False)
        embeddings_list = [emb.tolist() for emb in embeddings]

        # Upsert in batches (ChromaDB limit)
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            end = min(i + batch_size, len(chunks))
            self._collection.upsert(
                ids=ids[i:end],
                documents=texts[i:end],
                embeddings=embeddings_list[i:end],
                metadatas=metadatas[i:end],
            )

        return len(chunks)

    def query(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Semantic search. Returns [{text, section, score}].

        Args:
            query: Natural language query
            top_k: Number of results to return

        Returns:
            List of {text, section, score, source}
        """
        self._ensure_loaded()

        if self._client == "FALLBACK" or self._embedder == "FALLBACK":
            return self._fallback_query(query, top_k)

        try:
            # Check if collection has documents
            if self._collection.count() == 0:
                # Auto-build index
                count = self.build_index()
                if count == 0:
                    return self._fallback_query(query, top_k)

            query_embedding = self._embedder.encode([query])[0].tolist()
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, self._collection.count()),
            )

            output = []
            if results and results.get("documents"):
                docs = results["documents"][0]
                metadatas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0]

                for i, doc in enumerate(docs):
                    meta = metadatas[i] if i < len(metadatas) else {}
                    dist = distances[i] if i < len(distances) else 1.0
                    score = max(0, 1.0 - dist)  # Convert distance to similarity

                    output.append({
                        "text": doc,
                        "section": meta.get("section", "unknown"),
                        "score": round(score, 4),
                        "source": meta.get("source", "unknown"),
                    })

            return output

        except Exception as e:
            print(f"[VECTOR_STORE] Query error: {e}")
            return self._fallback_query(query, top_k)

    def _fallback_query(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Keyword-based fallback when ChromaDB/embedder unavailable."""
        try:
            from corpus.itr_text_corpus import ITR_CORPUS
        except ImportError:
            return []

        query_lower = query.lower()
        query_terms = set(re.findall(r'\b\w{3,}\b', query_lower))

        scored = []
        for node_id, node in ITR_CORPUS.items():
            if node_id == "root":
                continue
            text = (node.get("full_text", "") + " " + node.get("summary", "")).lower()
            overlap = sum(1 for t in query_terms if t in text)
            if overlap > 0:
                scored.append((overlap, {
                    "text": node.get("full_text") or node.get("summary", ""),
                    "section": node.get("title", node_id),
                    "score": round(overlap / max(len(query_terms), 1), 4),
                    "source": "itr_text_corpus",
                }))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:top_k]]

    @staticmethod
    def _chunk_text(text: str, max_chars: int = 800) -> list[str]:
        """Split text into chunks of approximately max_chars."""
        if len(text) <= max_chars:
            return [text]

        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current = ""

        for sent in sentences:
            if len(current) + len(sent) > max_chars and current:
                chunks.append(current.strip())
                current = sent
            else:
                current += " " + sent if current else sent

        if current.strip():
            chunks.append(current.strip())

        return chunks
