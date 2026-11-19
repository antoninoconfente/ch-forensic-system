"""Modelos relacionales del expediente. No tocan la interfaz ni los ficheros locales."""

from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


VALID_USER_ROLES = frozenset({"admin", "analyst", "viewer"})


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    role: Mapped[str] = mapped_column(String, default="viewer")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class Client(Base):
    __tablename__ = "client"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    lots: Mapped[list["Lot"]] = relationship(back_populates="client")


class Lot(Base):
    __tablename__ = "lot"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("client.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    reference_code: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    client: Mapped[Client | None] = relationship(back_populates="lots")
    cases: Mapped[list["Case"]] = relationship(back_populates="lot")


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    custom_brand: Mapped[str | None] = mapped_column(String, nullable=True)
    custom_title: Mapped[str | None] = mapped_column(String, nullable=True)
    object_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    intake_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    dictamen_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    lot_id: Mapped[str | None] = mapped_column(ForeignKey("lot.id", ondelete="SET NULL"), nullable=True)

    lot: Mapped["Lot | None"] = relationship(back_populates="cases")
    gemology_records: Mapped[list["GemologyData"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
    )
    evidences: Mapped[list["Evidence"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
    )
    embedding: Mapped["CaseEmbedding | None"] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        uselist=False,
    )


class GemologyData(Base):
    __tablename__ = "gemology_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    applies: Mapped[bool] = mapped_column(Boolean, default=False)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    metal_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    metal_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_carats: Mapped[float | None] = mapped_column(Float, nullable=True)
    valuation_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    case: Mapped[Case] = relationship(back_populates="gemology_records")


class CaseEmbedding(Base):
    __tablename__ = "case_embeddings"

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        primary_key=True,
    )
    taxonomy_key: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list] = mapped_column(Vector(768), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    case: Mapped["Case"] = relationship(back_populates="embedding")


class DomainRubric(Base):
    __tablename__ = "domain_rubrics"

    taxonomy_key: Mapped[str] = mapped_column(String, primary_key=True)
    parent_domain: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    inspection_checklist: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    authenticity_red_flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    cad_measurement_guide: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class Evidence(Base):
    __tablename__ = "evidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    storage_path: Mapped[str] = mapped_column(String)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False)

    case: Mapped[Case] = relationship(back_populates="evidences")
