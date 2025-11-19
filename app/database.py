"""
Database configuration and session management for ASTRA‑X‑Aggregator.

This module sets up a SQLite database using SQLAlchemy.  The database
connection string is defined relative to the project root so that it
works both inside a Docker container and when running locally.  The
`SessionLocal` factory produces scoped sessions for each request.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite database stored in the current working directory.
SQLALCHEMY_DATABASE_URL = "sqlite:///./astra_x.db"

# When using SQLite in a multithreaded environment (e.g. FastAPI), we
# must disable the same‑thread check to allow connections to be shared
# across threads.  Without this flag, SQLAlchemy will raise an error
# when reusing a connection in another thread.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# The sessionmaker constructs new Session objects when called.  We disable
# autocommit and autoflush to give us explicit control over transaction
# boundaries and flush behaviour.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our ORM models.  All model classes should inherit from
# this so that metadata is collected correctly.
Base = declarative_base()


def init_db() -> None:
    """Create all tables defined on the declarative Base."""
    import app.models  # noqa: F401 – ensure models are registered

    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency that yields a database session and commits/rolls back as needed.

    This generator is intended for use with FastAPI's dependency injection.
    It yields a SQLAlchemy session and then commits the transaction when
    the request finishes.  If an exception occurs the transaction is
    rolled back instead.  Finally the session is closed regardless of
    outcome.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()