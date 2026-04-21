from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.engagement import EngagementModel
from app.schemas.engagements import (
    EngagementCreate,
    EngagementRead,
    EngagementStatus,
)


@dataclass(slots=True)
class EngagementEntity:
    id: UUID
    name: str
    description: str | None
    scope_cidrs: list[str]
    authorization_confirmed: bool
    authorizer_name: str
    operator_name: str
    status: EngagementStatus
    created_at: datetime
    updated_at: datetime

    def to_read_model(self) -> EngagementRead:
        return EngagementRead(
            id=self.id,
            name=self.name,
            description=self.description,
            scope_cidrs=self.scope_cidrs,
            authorization_confirmed=self.authorization_confirmed,
            authorizer_name=self.authorizer_name,
            operator_name=self.operator_name,
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class EngagementRepository(Protocol):
    def list_engagements(self) -> list[EngagementEntity]: ...

    def get_engagement(self, engagement_id: UUID) -> EngagementEntity | None: ...

    def save_engagement(self, engagement: EngagementEntity) -> EngagementEntity: ...


class InMemoryEngagementRepository:
    def __init__(self) -> None:
        self._items: dict[UUID, EngagementEntity] = {}

    def list_engagements(self) -> list[EngagementEntity]:
        return sorted(self._items.values(), key=lambda item: item.created_at)

    def get_engagement(self, engagement_id: UUID) -> EngagementEntity | None:
        return self._items.get(engagement_id)

    def save_engagement(self, engagement: EngagementEntity) -> EngagementEntity:
        self._items[engagement.id] = engagement
        return engagement


def _to_entity(model: EngagementModel) -> EngagementEntity:
    return EngagementEntity(
        id=model.id,
        name=model.name,
        description=model.description,
        scope_cidrs=list(model.scope_cidrs),
        authorization_confirmed=model.authorization_confirmed,
        authorizer_name=model.authorizer_name,
        operator_name=model.operator_name,
        status=EngagementStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyEngagementRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_engagements(self) -> list[EngagementEntity]:
        with self._session_factory() as session:
            items = session.scalars(
                select(EngagementModel).order_by(EngagementModel.created_at)
            ).all()
            return [_to_entity(item) for item in items]

    def get_engagement(self, engagement_id: UUID) -> EngagementEntity | None:
        with self._session_factory() as session:
            engagement = session.get(EngagementModel, engagement_id)
            return _to_entity(engagement) if engagement else None

    def save_engagement(self, engagement: EngagementEntity) -> EngagementEntity:
        with self._session_factory() as session:
            existing = session.get(EngagementModel, engagement.id)
            if existing is None:
                existing = EngagementModel(id=engagement.id)
                session.add(existing)

            existing.name = engagement.name
            existing.description = engagement.description
            existing.scope_cidrs = engagement.scope_cidrs
            existing.authorization_confirmed = engagement.authorization_confirmed
            existing.authorizer_name = engagement.authorizer_name
            existing.operator_name = engagement.operator_name
            existing.status = engagement.status.value
            existing.created_at = engagement.created_at
            existing.updated_at = engagement.updated_at

            session.commit()
            session.refresh(existing)
            return _to_entity(existing)


class EngagementService:
    def __init__(self, repository: EngagementRepository) -> None:
        self._repository = repository

    def list_engagements(self) -> list[EngagementRead]:
        return [
            engagement.to_read_model()
            for engagement in self._repository.list_engagements()
        ]

    def create_engagement(self, payload: EngagementCreate) -> EngagementRead:
        now = datetime.now(timezone.utc)
        engagement = EngagementEntity(
            id=uuid4(),
            name=payload.name,
            description=payload.description,
            scope_cidrs=payload.scope_cidrs,
            authorization_confirmed=payload.authorization_confirmed,
            authorizer_name=payload.authorizer_name,
            operator_name=payload.operator_name,
            status=EngagementStatus.DRAFT,
            created_at=now,
            updated_at=now,
        )
        return self._repository.save_engagement(engagement).to_read_model()

    def get_engagement(self, engagement_id: UUID) -> EngagementRead | None:
        engagement = self._repository.get_engagement(engagement_id)
        return engagement.to_read_model() if engagement else None

    def update_status(
        self,
        *,
        engagement_id: UUID,
        status: EngagementStatus,
    ) -> EngagementRead | None:
        engagement = self._repository.get_engagement(engagement_id)
        if engagement is None:
            return None

        updated = EngagementEntity(
            id=engagement.id,
            name=engagement.name,
            description=engagement.description,
            scope_cidrs=engagement.scope_cidrs,
            authorization_confirmed=engagement.authorization_confirmed,
            authorizer_name=engagement.authorizer_name,
            operator_name=engagement.operator_name,
            status=status,
            created_at=engagement.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        return self._repository.save_engagement(updated).to_read_model()
