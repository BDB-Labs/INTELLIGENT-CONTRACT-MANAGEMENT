"""RAG knowledge base for contract intelligence.

Stores past contract analyses as vector embeddings for retrieval
when reviewing new contracts. Enables the system to learn from
historical negotiations and provide entity-specific intelligence.

Uses a lightweight BM25 + cosine similarity approach with no
external vector database dependency — all stored on disk as JSON.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tokenizer & Text Utilities
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "not",
        "no",
        "as",
        "if",
        "when",
        "than",
        "then",
        "so",
        "just",
        "about",
        "above",
        "below",
        "between",
        "into",
        "through",
        "during",
        "before",
        "after",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "only",
        "own",
        "same",
        "very",
        "what",
        "which",
        "who",
        "whom",
        "how",
        "any",
        "all",
        "also",
        "up",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "here",
        "there",
        "where",
        "why",
        "because",
        "while",
        "must",
        "upon",
        "within",
        "without",
        "against",
        "among",
        "along",
        "around",
        "since",
        "until",
        "whether",
        "however",
        "therefore",
        "although",
        "though",
        "yet",
        "still",
        "already",
        "even",
    }
)

_CONTRACT_TERMS = frozenset(
    {
        "indemnify",
        "indemnification",
        "indemnity",
        "liability",
        "termination",
        "change-order",
        "change order",
        "dispute",
        "arbitration",
        "mediation",
        "liquidated",
        "damages",
        "warranty",
        "defect",
        "performance",
        "bond",
        "payment",
        "retainage",
        "retainage",
        "substantial",
        "completion",
        "force",
        "majeure",
        "insurance",
        "additional",
        "insured",
        "waiver",
        "subrogation",
        "pay-if-paid",
        "pay-when-paid",
        "davis-bacon",
        "prevailing",
        "wage",
        "dbE",
        "disadvantaged",
        "business",
        "enterprise",
        "gmp",
        "guaranteed",
        "maximum",
        "price",
        "cmgc",
        "design-bid-build",
        "design-build",
        "progress",
        "schedule",
        "delay",
        "excusable",
        "compensable",
        "notice",
        "claim",
        "differing",
        "site",
        "condition",
        "flow-down",
        "flowdown",
        "pass-through",
        "subcontractor",
        "prime",
        "contractor",
        "owner",
        "agency",
        "appropriation",
        "funding",
        "certified",
        "payroll",
        "procurement",
        "solicitation",
        "bid",
        "proposal",
        "award",
        "amendment",
        "modification",
        "addendum",
        "general",
        "conditions",
        "special",
        "provisions",
        "technical",
        "specifications",
        "scope",
        "work",
        "deliverable",
        "milestone",
        "acceptance",
        "closeout",
        "final",
        "settlement",
        "release",
        "assignment",
        "successor",
        "governing",
        "law",
        "jurisdiction",
        "venue",
        "severability",
        "waiver",
        "amendment",
        "integration",
        "entire",
        "agreement",
        "counterpart",
        "electronic",
        "signature",
    }
)


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, remove stop words."""
    text = text.lower()
    text = re.sub(r"[^\w\s\-]", " ", text)
    tokens = text.split()
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 2]


def extract_key_phrases(text: str, max_phrases: int = 50) -> list[str]:
    """Extract contract-relevant key phrases."""
    tokens = tokenize(text)
    # Boost contract-specific terms
    boosted = []
    for t in tokens:
        if t in _CONTRACT_TERMS:
            boosted.extend([t, t])  # double weight
        else:
            boosted.append(t)
    # Bigrams
    bigrams = []
    for i in range(len(boosted) - 1):
        phrase = f"{boosted[i]} {boosted[i + 1]}"
        if phrase in _CONTRACT_TERMS or any(
            t in _CONTRACT_TERMS for t in [boosted[i], boosted[i + 1]]
        ):
            bigrams.append(phrase)
    # Count frequencies
    freq: dict[str, int] = {}
    for t in boosted + bigrams:
        freq[t] = freq.get(t, 0) + 1
    sorted_phrases = sorted(freq.items(), key=lambda x: -x[1])
    return [p for p, _ in sorted_phrases[:max_phrases]]


# ---------------------------------------------------------------------------
# BM25 Index
# ---------------------------------------------------------------------------


class BM25Index:
    """Lightweight BM25 full-text search index stored on disk."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_ids: list[str] = []
        self.doc_lengths: dict[str, int] = {}
        self.doc_tokens: dict[str, list[str]] = {}
        self.idf: dict[str, float] = {}
        self.avg_doc_length: float = 0.0
        self._built = False

    def add_document(self, doc_id: str, text: str) -> None:
        """Add a document to the index."""
        tokens = tokenize(text)
        self.doc_ids.append(doc_id)
        self.doc_lengths[doc_id] = len(tokens)
        self.doc_tokens[doc_id] = tokens
        self._built = False

    def build(self) -> None:
        """Build IDF table. Must be called before searching."""
        if self._built:
            return
        n_docs = len(self.doc_ids)
        if n_docs == 0:
            return
        self.avg_doc_length = sum(self.doc_lengths.values()) / n_docs
        df: dict[str, int] = {}
        for tokens in self.doc_tokens.values():
            for t in set(tokens):
                df[t] = df.get(t, 0) + 1
        for term, count in df.items():
            self.idf[term] = math.log(1 + (n_docs - count + 0.5) / (count + 0.5))
        self._built = True

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Search for documents matching the query."""
        if not self._built:
            self.build()
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scores: dict[str, float] = {doc_id: 0.0 for doc_id in self.doc_ids}
        for doc_id, doc_tokens in self.doc_tokens.items():
            doc_len = self.doc_lengths[doc_id]
            norm = 1 - self.b + self.b * (doc_len / max(self.avg_doc_length, 1))
            for qt in query_tokens:
                idf = self.idf.get(qt, 0.0)
                if idf == 0.0:
                    continue
                tf = doc_tokens.count(qt)
                score = idf * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)
                scores[doc_id] += score
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return [(doc_id, score) for doc_id, score in ranked[:top_k] if score > 0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "k1": self.k1,
            "b": self.b,
            "doc_ids": self.doc_ids,
            "doc_lengths": self.doc_lengths,
            "doc_tokens": self.doc_tokens,
            "idf": self.idf,
            "avg_doc_length": self.avg_doc_length,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BM25Index":
        idx = cls(k1=data["k1"], b=data["b"])
        idx.doc_ids = data["doc_ids"]
        idx.doc_lengths = data["doc_lengths"]
        idx.doc_tokens = data["doc_tokens"]
        idx.idf = data["idf"]
        idx.avg_doc_length = data["avg_doc_length"]
        idx._built = True
        return idx


# ---------------------------------------------------------------------------
# Knowledge Base Entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KnowledgeEntry:
    """A single entry in the knowledge base."""

    entry_id: str
    entity_name: str
    project_name: str
    project_type: str
    document_types: list[str]
    key_findings: list[str]
    relationship_impact_score: float
    negotiation_outcome: str
    summary: str
    full_text: str
    key_phrases: list[str]
    created_at: str
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------


class ContractKnowledgeBase:
    """Persistent knowledge base for contract intelligence RAG."""

    def __init__(self, storage_dir: str | Path):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.entries: dict[str, KnowledgeEntry] = {}
        self.bm25 = BM25Index()
        self._load()

    def _index_path(self) -> Path:
        return self.storage_dir / "knowledge_index.json"

    def _bm25_path(self) -> Path:
        return self.storage_dir / "bm25_index.json"

    def _load(self) -> None:
        index_path = self._index_path()
        if not index_path.exists():
            return
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
            logger.warning("Failed to load knowledge base index: %s", e)
            return
        for entry_data in data.get("entries", []):
            entry = KnowledgeEntry(
                entry_id=entry_data["entry_id"],
                entity_name=entry_data["entity_name"],
                project_name=entry_data["project_name"],
                project_type=entry_data["project_type"],
                document_types=entry_data.get("document_types", []),
                key_findings=entry_data.get("key_findings", []),
                relationship_impact_score=entry_data.get(
                    "relationship_impact_score", 0.0
                ),
                negotiation_outcome=entry_data.get("negotiation_outcome", ""),
                summary=entry_data["summary"],
                full_text=entry_data.get("full_text", ""),
                key_phrases=entry_data.get("key_phrases", []),
                created_at=entry_data.get("created_at", ""),
                tags=entry_data.get("tags", []),
            )
            self.entries[entry.entry_id] = entry
            self.bm25.add_document(
                entry.entry_id, entry.summary + " " + " ".join(entry.key_findings)
            )
        self.bm25.build()

        bm25_path = self._bm25_path()
        if bm25_path.exists():
            bm25_data = json.loads(bm25_path.read_text(encoding="utf-8"))
            self.bm25 = BM25Index.from_dict(bm25_data)

    def save(self) -> None:
        """Persist the knowledge base to disk."""
        index_data = {
            "version": "1.0.0",
            "entries": [
                {
                    "entry_id": e.entry_id,
                    "entity_name": e.entity_name,
                    "project_name": e.project_name,
                    "project_type": e.project_type,
                    "document_types": e.document_types,
                    "key_findings": e.key_findings,
                    "relationship_impact_score": e.relationship_impact_score,
                    "negotiation_outcome": e.negotiation_outcome,
                    "summary": e.summary,
                    "full_text": e.full_text,
                    "key_phrases": e.key_phrases,
                    "created_at": e.created_at,
                    "tags": e.tags,
                }
                for e in self.entries.values()
            ],
        }
        self._index_path().write_text(
            json.dumps(index_data, indent=2), encoding="utf-8"
        )
        bm25_data = self.bm25.to_dict()
        self._bm25_path().write_text(json.dumps(bm25_data, indent=2), encoding="utf-8")

    def add_entry(self, entry: KnowledgeEntry) -> None:
        """Add a new entry to the knowledge base."""
        self.entries[entry.entry_id] = entry
        self.bm25.add_document(
            entry.entry_id, entry.summary + " " + " ".join(entry.key_findings)
        )
        self.bm25.build()
        self.save()

    def search(
        self,
        query: str,
        *,
        entity_filter: str | None = None,
        project_type_filter: str | None = None,
        top_k: int = 5,
    ) -> list[tuple[KnowledgeEntry, float]]:
        """Search the knowledge base with optional filters."""
        results = self.bm25.search(query, top_k=top_k * 3)
        filtered: list[tuple[KnowledgeEntry, float]] = []
        for entry_id, score in results:
            entry = self.entries.get(entry_id)
            if entry is None:
                continue
            if entity_filter and entity_filter.lower() not in entry.entity_name.lower():
                continue
            if (
                project_type_filter
                and project_type_filter.lower() not in entry.project_type.lower()
            ):
                continue
            filtered.append((entry, score))
        return sorted(filtered, key=lambda x: -x[1])[:top_k]

    def find_similar_entity_history(
        self,
        entity_name: str,
        *,
        top_k: int = 10,
    ) -> list[tuple[KnowledgeEntry, float]]:
        """Find all past analyses for a specific entity."""
        results: list[tuple[KnowledgeEntry, float]] = []
        for entry in self.entries.values():
            if entity_name.lower() in entry.entity_name.lower():
                results.append((entry, entry.relationship_impact_score))
        return sorted(results, key=lambda x: -abs(x[1]), reverse=False)[:top_k]

    def get_entity_pattern_summary(
        self,
        entity_name: str,
    ) -> dict[str, Any]:
        """Generate a pattern summary for a specific entity."""
        entries = [
            e
            for e in self.entries.values()
            if entity_name.lower() in e.entity_name.lower()
        ]
        if not entries:
            return {
                "found": False,
                "message": f"No historical data for entity: {entity_name}",
            }

        avg_impact = sum(e.relationship_impact_score for e in entries) / len(entries)
        outcomes: dict[str, int] = {}
        for e in entries:
            outcomes[e.negotiation_outcome] = outcomes.get(e.negotiation_outcome, 0) + 1
        common_findings: dict[str, int] = {}
        for e in entries:
            for f in e.key_findings:
                common_findings[f] = common_findings.get(f, 0) + 1

        return {
            "found": True,
            "entity_name": entity_name,
            "total_analyses": len(entries),
            "average_relationship_impact": round(avg_impact, 2),
            "negotiation_outcomes": outcomes,
            "common_findings": dict(
                sorted(common_findings.items(), key=lambda x: -x[1])[:10]
            ),
            "project_types": list({e.project_type for e in entries}),
            "document_types": list({dt for e in entries for dt in e.document_types}),
        }

    def build_rag_context(
        self,
        *,
        entity_name: str = "",
        project_type: str = "",
        key_issues: list[str] | None = None,
        max_entries: int = 5,
    ) -> str:
        """Build a RAG context string to inject into role prompts."""
        parts: list[str] = []

        # Entity history
        if entity_name:
            pattern = self.get_entity_pattern_summary(entity_name)
            if pattern.get("found"):
                parts.append(
                    f"HISTORICAL PATTERN FOR {entity_name.upper()}:\n"
                    f"- {pattern['total_analyses']} prior analyses\n"
                    f"- Average relationship impact: {pattern['average_relationship_impact']}/10\n"
                    f"- Common outcomes: {', '.join(f'{k} ({v})' for k, v in pattern['negotiation_outcomes'].items())}\n"
                    f"- Recurring findings: {', '.join(list(pattern['common_findings'].keys())[:5])}"
                )

        # Similar past analyses
        if key_issues:
            query = " ".join(key_issues)
            if entity_name:
                query += f" {entity_name}"
            if project_type:
                query += f" {project_type}"
            similar = self.search(query, top_k=max_entries)
            if similar:
                parts.append("\nSIMILAR PAST ANALYSES:")
                for i, (entry, score) in enumerate(similar, 1):
                    parts.append(
                        f"\n  {i}. {entry.project_name} ({entry.entity_name}) — Score: {score:.2f}\n"
                        f"     Outcome: {entry.negotiation_outcome}\n"
                        f"     Findings: {'; '.join(entry.key_findings[:3])}\n"
                        f"     Relationship Impact: {entry.relationship_impact_score}/10"
                    )

        return "\n\n".join(parts) if parts else ""

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        return f"ContractKnowledgeBase(entries={len(self.entries)}, dir={self.storage_dir})"


# ---------------------------------------------------------------------------
# Factory: Create entry from bid review results
# ---------------------------------------------------------------------------


def create_entry_from_bid_review(
    *,
    project_id: str,
    entity_name: str,
    project_name: str,
    project_type: str,
    document_types: list[str],
    key_findings: list[str],
    relationship_impact_score: float,
    negotiation_outcome: str,
    summary: str,
    full_text: str = "",
    tags: list[str] | None = None,
) -> KnowledgeEntry:
    """Create a knowledge base entry from bid review results."""
    from datetime import datetime, timezone

    key_phrases = extract_key_phrases(summary + " " + " ".join(key_findings))
    return KnowledgeEntry(
        entry_id=f"entry_{hashlib.sha256(f'{project_id}:{entity_name}'.encode()).hexdigest()[:12]}",
        entity_name=entity_name,
        project_name=project_name,
        project_type=project_type,
        document_types=document_types,
        key_findings=key_findings,
        relationship_impact_score=relationship_impact_score,
        negotiation_outcome=negotiation_outcome,
        summary=summary,
        full_text=full_text,
        key_phrases=key_phrases,
        created_at=datetime.now(timezone.utc).isoformat(),
        tags=tags or [],
    )
