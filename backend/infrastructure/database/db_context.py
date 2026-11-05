from typing import AsyncGenerator, Generator
from fastapi import Request, Response, HTTPException
from sqlalchemy import text

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from core.config import settings


DATABASE_URL = settings.DATABASE_URL
ECHO = getattr(settings, "DATABASE_ECHO", False)

IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    if DATABASE_URL.startswith("sqlite+aiosqlite://"):
        ASYNC_DATABASE_URL = DATABASE_URL
    else:
        ASYNC_DATABASE_URL = DATABASE_URL.replace(
            "sqlite://", "sqlite+aiosqlite://", 1
        )
    SYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace(
        "sqlite+aiosqlite://", "sqlite://", 1
    )

    async_engine = create_async_engine(
        ASYNC_DATABASE_URL,
        echo=ECHO,
        connect_args={"check_same_thread": False},
    )

    sync_engine = create_engine(
        SYNC_DATABASE_URL,
        echo=ECHO,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(sync_engine, "connect")
    def _sqlite_sync_fk_on(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

    @event.listens_for(async_engine.sync_engine, "connect")
    def _sqlite_async_fk_on(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

else:
    # Vendor-neutral fallback retained for future PostgreSQL deployment.
    ASYNC_DATABASE_URL = DATABASE_URL
    SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "").replace(
        "+psycopg", ""
    )

    async_engine = create_async_engine(
        ASYNC_DATABASE_URL,
        echo=ECHO,
        pool_pre_ping=True,
    )

    sync_engine = create_engine(
        SYNC_DATABASE_URL,
        echo=ECHO,
        pool_pre_ping=True,
    )


AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Compatibility alias used by a few historical utility scripts.
async_session = AsyncSessionLocal

SyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
)

# SQLAlchemy metadata remains available to legacy imports, but schema creation is
# deliberately handled only by backend/scripts/migrate_core.py.
Base = declarative_base()


async def get_session(request: Request, response: Response) -> AsyncGenerator[AsyncSession, None]:
    """Provide one transaction for the endpoint and its successful audit event.

    Business handlers must not commit.  On a successful write/export, the audit
    event is inserted through the same AsyncSession before the single commit so a
    failed audit insert rolls back the business mutation as well.
    """
    from infrastructure.audit.services.event_writer import write_event

    async with AsyncSessionLocal() as session:
        try:
            yield session
            is_write = request.method in {"POST", "PUT", "PATCH", "DELETE"}
            is_export = bool(getattr(request.state, "audit_export", False))
            if is_write or is_export:
                action = "EXPORT" if is_export else {
                    "POST": "CREATE",
                    "PUT": "UPDATE",
                    "PATCH": "UPDATE",
                    "DELETE": "DELETE",
                }[request.method]
                for suffix, event in (
                    ("/login", "LOGIN"),
                    ("/logout", "LOGOUT"),
                    ("/refresh", "REFRESH"),
                ):
                    if request.url.path.endswith(suffix):
                        action = event
                        break
                route_status = getattr(request.scope.get("route"), "status_code", None)
                status_code = route_status or getattr(response, "status_code", None) or 200
                await write_event(session, request, action, status_code)
            await session.commit()
        except HTTPException as exc:
            await session.rollback()
            # Only authorization outcomes become REQUEST_DENIED. Business conflicts
            # (409), validation (422) and server faults remain ordinary failures;
            # the failed business transaction stays rolled back either way.
            if exc.status_code in (401, 403):
                from infrastructure.audit.services.denial_writer import write_denial_event
                await write_denial_event(request, exc.status_code, "endpoint_http_exception")
            raise
        except Exception:
            await session.rollback()
            raise



def get_sync_session() -> Generator[Session, None, None]:
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def init_db():
    async with async_engine.begin() as conn:
        version = await conn.execute(text("SELECT version FROM core_schema_versions ORDER BY version DESC LIMIT 1"))
        latest = version.scalar()
        # Any version at or past the baseline is valid; the auth-hardening
        # migration (0004) is idempotent per-table, so applying it repeatedly
        # would fail if columns already exist. Instead: detect missing columns
        # and patch them in place.
        if not latest:
            raise RuntimeError("Run backend/scripts/migrate_core.py before starting the server")
        # Non-destructive in-place patch: add 0004 columns if absent.
        existing = (await conn.exec_driver_sql("PRAGMA table_info(users)")).fetchall()
        cols = {row[1] for row in existing}
        for ddl in (
            "ALTER TABLE users ADD COLUMN mfa_secret TEXT",
            "ALTER TABLE users ADD COLUMN mfa_enabled INTEGER NOT NULL DEFAULT 0",
        ):
            col = ddl.split("ADD COLUMN ")[1].split(" ")[0]
            if col not in cols:
                await conn.exec_driver_sql(ddl)
        sess_cols = {row[1] for row in (await conn.exec_driver_sql("PRAGMA table_info(user_sessions)")).fetchall()}
        for ddl in (
            "ALTER TABLE user_sessions ADD COLUMN refresh_token_hash TEXT",
            "ALTER TABLE user_sessions ADD COLUMN mfa_verified INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE user_sessions ADD COLUMN token_kid TEXT",
        ):
            col = ddl.split("ADD COLUMN ")[1].split(" ")[0]
            if col not in sess_cols:
                await conn.exec_driver_sql(ddl)
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS jwt_keys (kid TEXT PRIMARY KEY, secret TEXT NOT NULL, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, retired_at TEXT)")
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS security_events (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id TEXT, kind TEXT NOT NULL, ip_address TEXT NOT NULL DEFAULT '', "
            "user_agent TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '', "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        await conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_security_events_user ON security_events(user_id, created_at)")
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS rate_limits (bucket TEXT PRIMARY KEY, tokens REAL NOT NULL, "
            "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        if latest != "0004_auth_hardening":
            await conn.execute(text(
                "INSERT OR IGNORE INTO core_schema_versions(version, applied_at) "
                "VALUES('0004_auth_hardening', CURRENT_TIMESTAMP)"))
        await conn.commit()


async def close_db():
    await async_engine.dispose()
    sync_engine.dispose()


def get_async_engine():
    return async_engine


def get_sync_engine():
    return sync_engine
