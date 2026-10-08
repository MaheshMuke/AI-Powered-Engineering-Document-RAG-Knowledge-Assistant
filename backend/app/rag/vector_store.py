"""
ChromaDB Vector Store Manager with Multi-Tenant Project Isolation.
Ensures project A vectors are never visible or retrievable by project B.
"""
import os
import math
from typing import List, Dict, Any, Optional
from backend.app.config import settings
from backend.app.rag.embeddings import embedding_provider

class ProjectVectorStore:
    def __init__(self, persist_dir: str = settings.CHROMA_PERSIST_DIRECTORY):
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)
        self._chroma_client = None
        self._memory_fallback: Dict[int, List[Dict[str, Any]]] = {}
        self._init_chroma()

    def _init_chroma(self):
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            self._chroma_client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
        except Exception as e:
            # Fallback to local memory dictionary if Chroma fails to initialize
            self._chroma_client = None

    def _get_collection_name(self, project_id: int) -> str:
        return f"project_{project_id}_docs"

    def add_chunks(self, project_id: int, chunks: List[Dict[str, Any]]):
        """
        Indexes chunks into the project-specific vector collection.
        """
        if not chunks:
            return

        texts = [c["content"] for c in chunks]
        embeddings = embedding_provider.embed_documents(texts)
        ids = [c["chunk_id"] for c in chunks]
        metadatas = [
            {
                "project_id": str(project_id),
                "document_id": str(c["document_id"]),
                "document_version": str(c["document_version"]),
                "filename": c["filename"],
                "page": int(c["page"]),
                "section": str(c.get("section", "")),
                "token_count": int(c.get("token_count", 0)),
                "content_type": str(c.get("content_type", "text"))
            }
            for c in chunks
        ]

        if self._chroma_client is not None:
            try:
                col_name = self._get_collection_name(project_id)
                collection = self._chroma_client.get_or_create_collection(
                    name=col_name,
                    metadata={"project_id": str(project_id)}
                )
                collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas
                )
                return
            except Exception:
                pass

        # In-memory fallback
        if project_id not in self._memory_fallback:
            self._memory_fallback[project_id] = []
        for i, c in enumerate(chunks):
            self._memory_fallback[project_id].append({
                "id": ids[i],
                "embedding": embeddings[i],
                "document": texts[i],
                "metadata": metadatas[i]
            })

    def _rerank_candidates(self, query: str, candidates: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """
        Applies hybrid lexical reranking to vector results.
        Prioritizes chunks where query entities (especially identifiers like SWC_CameraProcessing)
        match section titles, headings, and definitions.
        """
        import re
        q_raw_tokens = re.findall(r'[a-zA-Z0-9_]+', query)
        q_tokens_lower = [t.lower() for t in q_raw_tokens if t.lower() not in {
            'what', 'is', 'the', 'of', 'and', 'a', 'an', 'in', 'on', 'to', 'for', 'with', 'by', 'at', 'from',
            'does', 'do', 'are', 'was', 'were', 'it', 'its', 'this', 'that', 'these', 'those', 'how', 'which'
        }]
        # Technical identifiers (e.g. SWC_CameraProcessing)
        identifiers = [t for t in q_raw_tokens if '_' in t]

        scored = []
        for c in candidates:
            content = c.get("content", "")
            first_line = content.splitlines()[0].lower() if content.splitlines() else ""
            c_lower = content.lower()
            base_sim = float(c.get("similarity", 0.5))

            # Start with vector similarity component (weight: 1.0)
            score = base_sim * 1.5

            # Identifier exact matches
            for ident in identifiers:
                ident_low = ident.lower()
                if ident_low in first_line:
                    # Target component is the subject of this chunk's heading!
                    score += 15.0
                elif ident_low in c_lower:
                    score += 4.0

            # General keyword matches
            for t in q_tokens_lower:
                if t in first_line:
                    score += 3.0
                elif t in c_lower:
                    score += 0.8

            scored.append({
                **c,
                "_rank_score": score
            })

        scored.sort(key=lambda x: x["_rank_score"], reverse=True)
        # Normalize top similarity scores for downstream display
        result = []
        for i, item in enumerate(scored[:top_k]):
            item_copy = dict(item)
            # Re-normalize similarity to reflect rank confidence
            item_copy.pop("_rank_score", None)
            result.append(item_copy)
        return result

    def search(
        self,
        project_id: int,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs vector search strictly scoped to the specified project_id.
        """
        query_emb = embedding_provider.embed_text(query)

        if self._chroma_client is not None:
            try:
                col_name = self._get_collection_name(project_id)
                collection = self._chroma_client.get_collection(name=col_name)
                # Chroma query
                where_filter = {"project_id": str(project_id)}
                if filters:
                    for k, v in filters.items():
                        where_filter[k] = str(v)

                # Retrieve a candidate pool for reranking
                pool_size = max(top_k * 2, min(15, collection.count()))
                res = collection.query(
                    query_embeddings=[query_emb],
                    n_results=min(pool_size, max(1, collection.count())),
                    where=where_filter
                )
                
                results = []
                if res and res.get("documents") and len(res["documents"]) > 0:
                    docs = res["documents"][0]
                    metas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(docs)
                    dists = res["distances"][0] if res.get("distances") else [0.0] * len(docs)
                    ids = res["ids"][0] if res.get("ids") else [""] * len(docs)

                    for i in range(len(docs)):
                        # Similarity conversion
                        sim = max(0.0, 1.0 - (dists[i] / 2.0)) if dists[i] is not None else 0.8
                        results.append({
                            "chunk_id": ids[i],
                            "content": docs[i],
                            "metadata": metas[i],
                            "similarity": round(sim, 3)
                        })
                return self._rerank_candidates(query, results, top_k)
            except Exception:
                pass

        # Memory Fallback Search
        if project_id not in self._memory_fallback:
            return []

        scored = []
        for item in self._memory_fallback[project_id]:
            # Cosine similarity
            dot = sum(a * b for a, b in zip(query_emb, item["embedding"]))
            scored.append({
                "chunk_id": item["id"],
                "content": item["document"],
                "metadata": item["metadata"],
                "similarity": round(dot, 3)
            })

        return self._rerank_candidates(query, scored, top_k)

vector_store = ProjectVectorStore()
