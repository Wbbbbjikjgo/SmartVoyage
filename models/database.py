"""SQLAlchemy database models and utilities."""

from datetime import datetime
from typing import Generator
from sqlalchemy import (
    create_engine,
    Column,
    BigInteger,
    String,
    Date,
    Integer,
    Numeric,
    DateTime,
    JSON,
    ForeignKey,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from configs.settings import settings


# Base class for all models
Base = declarative_base()


# ============== Database Models ==============

class User(Base):
    """User model."""
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    email = Column(String(128), nullable=False, unique=True)
    preferences = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    itineraries = relationship("Itinerary", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(user_id={self.user_id}, name='{self.name}')>"


class Itinerary(Base):
    """Itinerary model."""
    __tablename__ = "itineraries"

    itinerary_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    destination = Column(String(64), nullable=False)
    start_date = Column(Date, nullable=False)
    duration = Column(Integer, nullable=False)
    budget = Column(Numeric(12, 2), nullable=True)
    status = Column(String(16), default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="itineraries")
    bookings = relationship("Booking", back_populates="itinerary", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Itinerary(itinerary_id={self.itinerary_id}, destination='{self.destination}')>"


class Booking(Base):
    """Booking model."""
    __tablename__ = "bookings"

    booking_id = Column(BigInteger, primary_key=True, autoincrement=True)
    itinerary_id = Column(BigInteger, ForeignKey("itineraries.itinerary_id"), nullable=False)
    type = Column(String(16), nullable=False)
    details = Column(JSON, nullable=True)
    status = Column(String(16), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    itinerary = relationship("Itinerary", back_populates="bookings")

    def __repr__(self) -> str:
        return f"<Booking(booking_id={self.booking_id}, type='{self.type}')>"


# ============== Database Utilities ==============

_engine = None
_SessionLocal = None


def get_engine():
    """Get or create SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.mysql_dsn,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
    return _engine


def get_session_factory():
    """Get or create session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    """Get database session (for dependency injection)."""
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """Initialize database (create all tables)."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized: {settings.mysql_database}")


def seed_default_user():
    """Ensure the default demo user (user_id=1) exists."""
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.user_id == 1).first()
        if not user:
            user = User(
                name="演示用户",
                email="demo@smartvoyage.local",
                preferences={"theme": "light", "language": "zh-CN"},
            )
            session.add(user)
            session.commit()
            print("Default demo user created (user_id=1)")
        return user.user_id
    finally:
        session.close()


def close_db():
    """Close database connections."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
        print("Database connections closed")
