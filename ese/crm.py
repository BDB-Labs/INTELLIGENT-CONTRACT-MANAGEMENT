"""Lightweight CRM for contract intelligence.

Tracks entities (agencies, vendors, stakeholders), contacts, interactions,
and relationship health over time. Feeds context into the RAG knowledge base
and advisory roles.

All data stored as JSON files on disk — no database required.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Contact:
    """A person associated with an entity."""

    contact_id: str
    entity_id: str
    name: str
    title: str
    email: str = ""
    phone: str = ""
    role: str = ""  # e.g. "procurement officer", "project manager", "legal counsel"
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class Interaction:
    """A recorded interaction with an entity."""

    interaction_id: str
    entity_id: str
    contact_id: str = ""
    interaction_type: str = ""  # meeting, call, email, negotiation, site_visit, etc.
    date: str = ""
    summary: str = ""
    details: str = ""
    outcome: str = ""
    follow_up_required: bool = False
    follow_up_date: str = ""
    relationship_impact: str = ""  # positive, negative, neutral
    tags: list[str] = field(default_factory=list)
    created_at: str = ""


@dataclass(frozen=True)
class Entity:
    """An organization (agency, vendor, contractor, etc.)."""

    entity_id: str
    name: str
    entity_type: str = ""  # agency, vendor, contractor, subcontractor, consultant
    industry: str = ""
    description: str = ""
    website: str = ""
    address: str = ""
    primary_contact_id: str = ""
    relationship_status: str = "active"  # active, dormant, terminated, prospective
    relationship_health: str = "neutral"  # positive, neutral, negative
    health_score: float = 0.0  # -10 to +10
    total_interactions: int = 0
    total_projects: int = 0
    average_project_value: float = 0.0
    risk_profile: str = ""  # low, medium, high
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    custom_fields: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CRM Store
# ---------------------------------------------------------------------------


class ContractCRM:
    """Lightweight CRM for contract intelligence stored on disk."""

    def __init__(self, storage_dir: str | Path):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.entities: dict[str, Entity] = {}
        self.contacts: dict[str, Contact] = {}
        self.interactions: dict[str, Interaction] = {}
        self._load()

    def _entities_path(self) -> Path:
        return self.storage_dir / "entities.json"

    def _contacts_path(self) -> Path:
        return self.storage_dir / "contacts.json"

    def _interactions_path(self) -> Path:
        return self.storage_dir / "interactions.json"

    def _load(self) -> None:
        for path, collection, cls in [
            (self._entities_path(), "entities", Entity),
            (self._contacts_path(), "contacts", Contact),
            (self._interactions_path(), "interactions", Interaction),
        ]:
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for item_data in data.get(collection, []):
                obj = cls(
                    **{
                        k: v
                        for k, v in item_data.items()
                        if k in cls.__dataclass_fields__
                    }
                )
                getattr(self, collection)[
                    getattr(
                        obj,
                        f"{cls.__name__.lower()}_id"
                        if cls != Entity
                        else "entity_id"
                        if cls == Entity
                        else "contact_id"
                        if cls == Contact
                        else "interaction_id",
                    )
                ] = obj

        # Rebuild properly
        self.entities = {}
        self.contacts = {}
        self.interactions = {}

        if self._entities_path().exists():
            data = json.loads(self._entities_path().read_text(encoding="utf-8"))
            for item_data in data.get("entities", []):
                obj = Entity(
                    **{
                        k: v
                        for k, v in item_data.items()
                        if k in Entity.__dataclass_fields__
                    }
                )
                self.entities[obj.entity_id] = obj

        if self._contacts_path().exists():
            data = json.loads(self._contacts_path().read_text(encoding="utf-8"))
            for item_data in data.get("contacts", []):
                obj = Contact(
                    **{
                        k: v
                        for k, v in item_data.items()
                        if k in Contact.__dataclass_fields__
                    }
                )
                self.contacts[obj.contact_id] = obj

        if self._interactions_path().exists():
            data = json.loads(self._interactions_path().read_text(encoding="utf-8"))
            for item_data in data.get("interactions", []):
                obj = Interaction(
                    **{
                        k: v
                        for k, v in item_data.items()
                        if k in Interaction.__dataclass_fields__
                    }
                )
                self.interactions[obj.interaction_id] = obj

    def save(self) -> None:
        """Persist all data to disk."""
        self._entities_path().write_text(
            json.dumps(
                {
                    "version": "1.0.0",
                    "entities": [
                        {k: v for k, v in e.__dict__.items()}
                        for e in self.entities.values()
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self._contacts_path().write_text(
            json.dumps(
                {
                    "version": "1.0.0",
                    "contacts": [
                        {k: v for k, v in c.__dict__.items()}
                        for c in self.contacts.values()
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self._interactions_path().write_text(
            json.dumps(
                {
                    "version": "1.0.0",
                    "interactions": [
                        {k: v for k, v in i.__dict__.items()}
                        for i in self.interactions.values()
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    # -----------------------------------------------------------------------
    # Entity CRUD
    # -----------------------------------------------------------------------

    def add_entity(self, entity: Entity) -> None:
        """Add or update an entity."""
        self.entities[entity.entity_id] = entity
        self.save()

    def get_entity(self, entity_id: str) -> Entity | None:
        return self.entities.get(entity_id)

    def find_entity_by_name(self, name: str) -> Entity | None:
        for entity in self.entities.values():
            if name.lower() in entity.name.lower():
                return entity
        return None

    def list_entities(
        self,
        *,
        entity_type: str | None = None,
        relationship_status: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Entity]:
        results = list(self.entities.values())
        if entity_type:
            results = [
                e for e in results if e.entity_type.lower() == entity_type.lower()
            ]
        if relationship_status:
            results = [
                e for e in results if e.relationship_status == relationship_status
            ]
        if tags:
            results = [e for e in results if any(t in e.tags for t in tags)]
        return sorted(results, key=lambda e: e.name)

    def update_entity_health(
        self, entity_id: str, *, health_score: float, health_status: str = ""
    ) -> None:
        """Update an entity's relationship health."""
        entity = self.entities.get(entity_id)
        if not entity:
            return
        health_score = max(-10.0, min(10.0, health_score))
        if not health_status:
            if health_score >= 3:
                health_status = "positive"
            elif health_score <= -3:
                health_status = "negative"
            else:
                health_status = "neutral"
        # Create a new frozen instance
        self.entities[entity_id] = Entity(
            entity_id=entity.entity_id,
            name=entity.name,
            entity_type=entity.entity_type,
            industry=entity.industry,
            description=entity.description,
            website=entity.website,
            address=entity.address,
            primary_contact_id=entity.primary_contact_id,
            relationship_status=entity.relationship_status,
            relationship_health=health_status,
            health_score=health_score,
            total_interactions=entity.total_interactions,
            total_projects=entity.total_projects,
            average_project_value=entity.average_project_value,
            risk_profile=entity.risk_profile,
            notes=entity.notes,
            tags=entity.tags,
            created_at=entity.created_at,
            updated_at=datetime.now(timezone.utc).isoformat(),
            custom_fields=entity.custom_fields,
        )
        self.save()

    # -----------------------------------------------------------------------
    # Contact CRUD
    # -----------------------------------------------------------------------

    def add_contact(self, contact: Contact) -> None:
        """Add or update a contact."""
        self.contacts[contact.contact_id] = contact
        # Update entity's primary contact if first contact
        entity = self.entities.get(contact.entity_id)
        if entity and not entity.primary_contact_id:
            self.update_entity_primary_contact(contact.entity_id, contact.contact_id)
        self.save()

    def get_contact(self, contact_id: str) -> Contact | None:
        return self.contacts.get(contact_id)

    def get_entity_contacts(self, entity_id: str) -> list[Contact]:
        return sorted(
            [c for c in self.contacts.values() if c.entity_id == entity_id],
            key=lambda c: c.name,
        )

    def update_entity_primary_contact(self, entity_id: str, contact_id: str) -> None:
        entity = self.entities.get(entity_id)
        if not entity:
            return
        self.entities[entity_id] = Entity(
            entity_id=entity.entity_id,
            name=entity.name,
            entity_type=entity.entity_type,
            industry=entity.industry,
            description=entity.description,
            website=entity.website,
            address=entity.address,
            primary_contact_id=contact_id,
            relationship_status=entity.relationship_status,
            relationship_health=entity.relationship_health,
            health_score=entity.health_score,
            total_interactions=entity.total_interactions,
            total_projects=entity.total_projects,
            average_project_value=entity.average_project_value,
            risk_profile=entity.risk_profile,
            notes=entity.notes,
            tags=entity.tags,
            created_at=entity.created_at,
            updated_at=datetime.now(timezone.utc).isoformat(),
            custom_fields=entity.custom_fields,
        )
        self.save()

    # -----------------------------------------------------------------------
    # Interaction CRUD
    # -----------------------------------------------------------------------

    def add_interaction(self, interaction: Interaction) -> None:
        """Record an interaction with an entity."""
        self.interactions[interaction.interaction_id] = interaction
        # Update entity interaction count
        entity = self.entities.get(interaction.entity_id)
        if entity:
            self.entities[interaction.entity_id] = Entity(
                entity_id=entity.entity_id,
                name=entity.name,
                entity_type=entity.entity_type,
                industry=entity.industry,
                description=entity.description,
                website=entity.website,
                address=entity.address,
                primary_contact_id=entity.primary_contact_id,
                relationship_status=entity.relationship_status,
                relationship_health=entity.relationship_health,
                health_score=entity.health_score,
                total_interactions=entity.total_interactions + 1,
                total_projects=entity.total_projects,
                average_project_value=entity.average_project_value,
                risk_profile=entity.risk_profile,
                notes=entity.notes,
                tags=entity.tags,
                created_at=entity.created_at,
                updated_at=datetime.now(timezone.utc).isoformat(),
                custom_fields=entity.custom_fields,
            )
        self.save()

    def get_entity_interactions(
        self,
        entity_id: str,
        *,
        limit: int = 50,
        interaction_type: str | None = None,
    ) -> list[Interaction]:
        results = [i for i in self.interactions.values() if i.entity_id == entity_id]
        if interaction_type:
            results = [i for i in results if i.interaction_type == interaction_type]
        return sorted(results, key=lambda i: i.date, reverse=True)[:limit]

    # -----------------------------------------------------------------------
    # Entity Profile Report
    # -----------------------------------------------------------------------

    def get_entity_profile(self, entity_id: str) -> dict[str, Any]:
        """Generate a comprehensive profile for an entity."""
        entity = self.entities.get(entity_id)
        if not entity:
            return {"found": False, "message": f"Entity not found: {entity_id}"}

        contacts = self.get_entity_contacts(entity_id)
        interactions = self.get_entity_interactions(entity_id, limit=20)

        # Interaction summary
        interaction_types: dict[str, int] = {}
        recent_outcomes: list[str] = []
        follow_ups: list[Interaction] = []
        for i in interactions:
            interaction_types[i.interaction_type] = (
                interaction_types.get(i.interaction_type, 0) + 1
            )
            if i.outcome:
                recent_outcomes.append(i.outcome)
            if i.follow_up_required:
                follow_ups.append(i)

        # Relationship trend
        health_history = []
        for i in interactions:
            if i.relationship_impact:
                health_history.append(
                    {
                        "date": i.date,
                        "type": i.interaction_type,
                        "impact": i.relationship_impact,
                        "summary": i.summary[:100],
                    }
                )

        return {
            "found": True,
            "entity": {
                "entity_id": entity.entity_id,
                "name": entity.name,
                "type": entity.entity_type,
                "industry": entity.industry,
                "description": entity.description,
                "relationship_status": entity.relationship_status,
                "relationship_health": entity.relationship_health,
                "health_score": entity.health_score,
                "total_interactions": entity.total_interactions,
                "total_projects": entity.total_projects,
                "risk_profile": entity.risk_profile,
                "tags": entity.tags,
                "notes": entity.notes,
            },
            "contacts": [
                {
                    "contact_id": c.contact_id,
                    "name": c.name,
                    "title": c.title,
                    "email": c.email,
                    "role": c.role,
                    "is_primary": c.contact_id == entity.primary_contact_id,
                }
                for c in contacts
            ],
            "interaction_summary": {
                "total": len(interactions),
                "by_type": interaction_types,
                "recent_outcomes": recent_outcomes[:5],
                "pending_follow_ups": len(follow_ups),
            },
            "relationship_trend": health_history[-10:],
            "pending_follow_ups": [
                {
                    "interaction_id": f.interaction_id,
                    "date": f.date,
                    "summary": f.summary,
                    "follow_up_date": f.follow_up_date,
                }
                for f in follow_ups
            ],
        }

    # -----------------------------------------------------------------------
    # CRM → Knowledge Bridge Integration
    # -----------------------------------------------------------------------

    def get_crm_context_for_knowledge_base(
        self,
        entity_name: str,
    ) -> dict[str, Any]:
        """Extract CRM data formatted for knowledge base ingestion."""
        entity = self.find_entity_by_name(entity_name)
        if not entity:
            return {"found": False}

        interactions = self.get_entity_interactions(entity.entity_id, limit=100)
        contacts = self.get_entity_contacts(entity.entity_id)

        return {
            "found": True,
            "entity_id": entity.entity_id,
            "entity_name": entity.name,
            "entity_type": entity.entity_type,
            "relationship_health": entity.relationship_health,
            "health_score": entity.health_score,
            "total_interactions": entity.total_interactions,
            "total_projects": entity.total_projects,
            "key_contacts": [
                {"name": c.name, "title": c.title, "role": c.role} for c in contacts
            ],
            "interaction_summary": {
                t: sum(1 for i in interactions if i.interaction_type == t)
                for t in {
                    i.interaction_type for i in interactions if i.interaction_type
                }
            },
            "recent_interactions": [
                {
                    "date": i.date,
                    "type": i.interaction_type,
                    "summary": i.summary,
                    "outcome": i.outcome,
                    "relationship_impact": i.relationship_impact,
                }
                for i in interactions[:10]
            ],
            "risk_profile": entity.risk_profile,
            "tags": entity.tags,
        }

    def __len__(self) -> int:
        return len(self.entities)

    def __repr__(self) -> str:
        return (
            f"ContractCRM(entities={len(self.entities)}, "
            f"contacts={len(self.contacts)}, "
            f"interactions={len(self.interactions)}, "
            f"dir={self.storage_dir})"
        )


# ---------------------------------------------------------------------------
# Factory Helpers
# ---------------------------------------------------------------------------


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID."""
    import hashlib
    import time

    raw = f"{prefix}:{time.time_ns()}:{os.urandom(4).hex()}"
    return (
        f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:10]}"
        if prefix
        else hashlib.sha256(raw.encode()).hexdigest()[:12]
    )


def create_entity(
    name: str,
    *,
    entity_type: str = "",
    industry: str = "",
    description: str = "",
    website: str = "",
    address: str = "",
    risk_profile: str = "",
    tags: list[str] | None = None,
    custom_fields: dict[str, str] | None = None,
) -> Entity:
    """Create a new entity."""
    now = datetime.now(timezone.utc).isoformat()
    return Entity(
        entity_id=generate_id("entity"),
        name=name,
        entity_type=entity_type,
        industry=industry,
        description=description,
        website=website,
        address=address,
        relationship_status="active",
        relationship_health="neutral",
        health_score=0.0,
        total_interactions=0,
        total_projects=0,
        average_project_value=0.0,
        risk_profile=risk_profile,
        tags=tags or [],
        created_at=now,
        updated_at=now,
        custom_fields=custom_fields or {},
    )


def create_contact(
    entity_id: str,
    name: str,
    title: str,
    *,
    email: str = "",
    phone: str = "",
    role: str = "",
    notes: str = "",
) -> Contact:
    """Create a new contact."""
    now = datetime.now(timezone.utc).isoformat()
    return Contact(
        contact_id=generate_id("contact"),
        entity_id=entity_id,
        name=name,
        title=title,
        email=email,
        phone=phone,
        role=role,
        notes=notes,
        created_at=now,
        updated_at=now,
    )


def create_interaction(
    entity_id: str,
    *,
    contact_id: str = "",
    interaction_type: str = "",
    date: str = "",
    summary: str = "",
    details: str = "",
    outcome: str = "",
    follow_up_required: bool = False,
    follow_up_date: str = "",
    relationship_impact: str = "",
    tags: list[str] | None = None,
) -> Interaction:
    """Create a new interaction."""
    now = datetime.now(timezone.utc).isoformat()
    return Interaction(
        interaction_id=generate_id("interaction"),
        entity_id=entity_id,
        contact_id=contact_id,
        interaction_type=interaction_type,
        date=date or now[:10],
        summary=summary,
        details=details,
        outcome=outcome,
        follow_up_required=follow_up_required,
        follow_up_date=follow_up_date,
        relationship_impact=relationship_impact,
        tags=tags or [],
        created_at=now,
    )
