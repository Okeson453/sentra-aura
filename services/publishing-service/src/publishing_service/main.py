# ruff: noqa: B008
"""Publishing Service FastAPI service entrypoint.

Multi-platform publishing, scheduling, metadata optimization, post analytics
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sentinel_exceptions import AuthorizationError
from sentinel_security.auth import AuthContext, authenticate_request
from sentinel_security.tenant import auth_error_to_http_status, resolve_tenant_id
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

from publishing_service.config import ServiceConfig
from publishing_service.feedback import publish_publication_published

logger = logging.getLogger(__name__)

config = ServiceConfig()

# Database-backed store instead of in-memory

Base = declarative_base()

class Publication(Base):
    __tablename__ = "publications"
    publication_id = Column(String(36), primary_key=True)
    #: Owning tenant. This is a security boundary rather than metadata: every
    #: read, mutation and publish is filtered by it (see _require_tenant).
    #: Nullable only so a pre-isolation schema can be upgraded additively --
    #: such legacy rows match no tenant filter and therefore fail closed.
    tenant_id = Column(String(32), index=True)
    channel_id = Column(String(255))
    title = Column(Text)
    description = Column(Text)
    status = Column(String(50), default="draft")
    asset_id = Column(String(255))
    thumbnail_asset_id = Column(String(255))
    platforms = Column(JSON, default=[])
    scheduled_at = Column(DateTime)
    seo_metadata = Column(JSON, default={})
    tags = Column(JSON, default=[])
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PublishJob(Base):
    __tablename__ = "publish_jobs"
    job_id = Column(String(36), primary_key=True)
    publication_id = Column(String(36))
    status = Column(String(50), default="queued")
    platform_results = Column(JSON, default=[])
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime)
    error_message = Column(Text)

# Initialize database
_engine = create_engine(config.database_url, poolclass=QueuePool, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_tenant_column() -> None:
    """Add the ``tenant_id`` column to a pre-existing ``publications`` table.

    The schema is created with ``Base.metadata.create_all`` and this service has
    no applied Alembic revision, so a database created before tenant scoping
    keeps its old column set. Without this guard the new isolation filter would
    reference a column that does not exist and every request would fail. The
    ALTER is additive and nullable, so it is safe to run on every start; rows
    created before isolation keep a NULL tenant, match no tenant filter, and are
    therefore unreachable rather than exposed.
    """
    inspector = inspect(_engine)
    if "publications" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("publications")}
    if "tenant_id" in existing:
        return
    with _engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE publications ADD COLUMN tenant_id VARCHAR(32)")
        )
    logger.warning(
        "publications table predates tenant isolation; added a nullable "
        "tenant_id column (legacy rows match no tenant and are not exposed)"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config
    config = ServiceConfig()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    _ensure_tenant_column()
    logger.info("Publishing Service started: %s v%s", config.service_name, config.version)
    yield
    logger.info("Publishing Service shutting down")



def _verify_bearer(authorization: str | None = Header(None)) -> AuthContext:
    """Verify JWT token using sentinel-security."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[7:]
    try:
        return authenticate_request(token, jwt_secret=config.jwt_secret)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {e}") from e


def _require_tenant(
    auth_context: AuthContext, requested_tenant_id: str | None = None
) -> str:
    """Resolve the tenant this request is authorised to act on.

    SECURITY: the tenant is derived from the *verified* JWT claim carried in the
    Authorization header. It is never read from a client-supplied header, query
    parameter or body; ``requested_tenant_id`` is treated purely as an assertion
    to verify. Before this check the publications API was filtered by
    ``publication_id`` alone, so any authenticated principal could read, rename,
    archive and publish another tenant's publications -- broken object-level
    authorization. Missing tenant identity is a 401; a mismatched tenant is a
    403.
    """
    try:
        return resolve_tenant_id(
            auth_context,
            requested_tenant_id,
            enforce_isolation=config.enforce_tenant_isolation,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=auth_error_to_http_status(exc), detail=str(exc)
        ) from exc



app = FastAPI(
    title="SentraAura Publishing Service",
    version="1.0.0",
    lifespan=lifespan,
)




@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error_code": "VALIDATION_ERROR", "message": str(exc)})



@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check."""
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
    }


@app.get("/ready")
async def readiness_check(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Readiness check."""
    try:
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception:
        db_healthy = False

    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
        "checks": {
            "database": "healthy" if db_healthy else "unhealthy",
        },
    }


@app.post("/publications")
async def create_publication(request: Request, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Create a publication.

    The owning tenant is taken from the authenticated token. A ``tenant_id`` in
    the body is an assertion to verify, never the source of truth -- previously
    it was accepted (and silently dropped), so a caller could attempt to claim
    ownership belonging to another tenant.
    """
    body = await request.json()
    tenant = _require_tenant(authorization, body.get("tenant_id"))
    publication_id = f"pub-{uuid.uuid4().hex[:12]}"

    scheduled_at = body.get("scheduled_at")
    if scheduled_at:
        try:
            scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            scheduled_at = None

    pub = Publication(
        publication_id=publication_id,
        tenant_id=tenant,
        channel_id=body.get("channel_id", ""),
        title=body.get("title", ""),
        description=body.get("description", ""),
        status="draft",
        asset_id=body.get("asset_id", ""),
        thumbnail_asset_id=body.get("thumbnail_asset_id", ""),
        platforms=body.get("platforms", []),
        scheduled_at=scheduled_at,
        seo_metadata=body.get("seo_metadata", {}),
        tags=body.get("tags", []),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(pub)
    db.commit()
    db.refresh(pub)

    return {
        "publication_id": publication_id,
        "channel_id": pub.channel_id,
        "title": pub.title,
        "description": pub.description,
        "status": pub.status,
        "asset_id": pub.asset_id,
        "thumbnail_asset_id": pub.thumbnail_asset_id,
        "platforms": pub.platforms,
        "scheduled_at": pub.scheduled_at.isoformat() + "Z" if pub.scheduled_at else None,
        "seo_metadata": pub.seo_metadata,
        "tags": pub.tags,
        "created_at": pub.created_at.isoformat() + "Z",
        "updated_at": pub.updated_at.isoformat() + "Z",
    }


@app.get("/publications")
async def list_publications(authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """List publications owned by the authenticated tenant."""
    publications = (
        db.query(Publication)
        .filter(Publication.tenant_id == _require_tenant(authorization))
        .all()
    )
    return {
        "publications": [
            {
                "publication_id": p.publication_id,
                "channel_id": p.channel_id,
                "title": p.title,
                "status": p.status,
                "created_at": p.created_at.isoformat() + "Z",
            }
            for p in publications
        ],
        "count": len(publications),
    }


@app.get("/publications/{publication_id}")
async def get_publication(publication_id: str, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get a publication by ID, scoped to the authenticated tenant.

    A cross-tenant id is indistinguishable from a missing one (404), so the
    endpoint cannot be used to probe for other tenants' publication ids.
    """
    tenant = _require_tenant(authorization)
    pub = (
        db.query(Publication)
        .filter(
            Publication.publication_id == publication_id,
            Publication.tenant_id == tenant,
        )
        .first()
    )
    if not pub:
        raise HTTPException(status_code=404, detail="publication_id not found")

    return {
        "publication_id": pub.publication_id,
        "channel_id": pub.channel_id,
        "title": pub.title,
        "description": pub.description,
        "status": pub.status,
        "asset_id": pub.asset_id,
        "thumbnail_asset_id": pub.thumbnail_asset_id,
        "platforms": pub.platforms,
        "scheduled_at": pub.scheduled_at.isoformat() + "Z" if pub.scheduled_at else None,
        "seo_metadata": pub.seo_metadata,
        "tags": pub.tags,
        "created_at": pub.created_at.isoformat() + "Z",
        "updated_at": pub.updated_at.isoformat() + "Z",
    }


@app.put("/publications/{publication_id}")
async def update_publication(publication_id: str, request: Request, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Update a publication, scoped to the authenticated tenant."""
    body = await request.json()
    tenant = _require_tenant(authorization, body.get("tenant_id"))
    pub = (
        db.query(Publication)
        .filter(
            Publication.publication_id == publication_id,
            Publication.tenant_id == tenant,
        )
        .first()
    )
    if not pub:
        raise HTTPException(status_code=404, detail="publication_id not found")

    if "title" in body:
        pub.title = body["title"]
    if "description" in body:
        pub.description = body["description"]
    if "status" in body:
        pub.status = body["status"]
    if "asset_id" in body:
        pub.asset_id = body["asset_id"]

    if "thumbnail_asset_id" in body:
        pub.thumbnail_asset_id = body["thumbnail_asset_id"]
    if "platforms" in body:
        pub.platforms = body["platforms"]
    if "seo_metadata" in body:
        pub.seo_metadata = body["seo_metadata"]
    if "tags" in body:
        pub.tags = body["tags"]
    if "scheduled_at" in body:
        try:
            pub.scheduled_at = datetime.fromisoformat(body["scheduled_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pub.scheduled_at = None

    pub.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pub)

    return {
        "publication_id": pub.publication_id,
        "status": pub.status,
        "updated_at": pub.updated_at.isoformat() + "Z",
    }


@app.delete("/publications/{publication_id}")
async def delete_publication(publication_id: str, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> None:
    """Delete/archive a publication, scoped to the authenticated tenant."""
    pub = (
        db.query(Publication)
        .filter(
            Publication.publication_id == publication_id,
            Publication.tenant_id == _require_tenant(authorization),
        )
        .first()
    )
    if not pub:
        raise HTTPException(status_code=404, detail="publication_id not found")
    pub.status = "archived"
    db.commit()
    return None


@app.post("/publications/{publication_id}/publish")
async def publish_now(publication_id: str, request: Request, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Publish immediately, for a publication owned by the authenticated tenant.

    Without the tenant filter any principal could trigger publication of another
    tenant's content to its connected platforms.
    """
    pub = (
        db.query(Publication)
        .filter(
            Publication.publication_id == publication_id,
            Publication.tenant_id == _require_tenant(authorization),
        )
        .first()
    )
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    job_id = f"publish-{uuid.uuid4().hex[:12]}"

    # Create publish job
    publish_job = PublishJob(
        job_id=job_id,
        publication_id=publication_id,
        status="queued",
        platform_results=[],
        started_at=datetime.now(timezone.utc),
    )
    db.add(publish_job)
    db.commit()

    # Process publishing asynchronously
    asyncio.create_task(_process_publish_job(job_id, publication_id))

    return {
        "job_id": job_id,
        "publication_id": publication_id,
        "status": "queued",
        "platform_results": [],
    }


async def _process_publish_job(job_id: str, publication_id: str) -> None:
    """Background task to process a publish job.

    Calls platform adapters to perform actual publishing.

    Opens its own session and re-reads the publication: the request-scoped
    session from ``get_db`` is closed the moment the request returns, so using
    it here (and holding a detached ORM instance) meant the job could never
    complete in production.
    """
    db = SessionLocal()
    try:
        publish_job = db.query(PublishJob).filter(PublishJob.job_id == job_id).first()
        if not publish_job:
            return

        # The job runs after the request has been authorised and the publish job
        # row created, so it re-reads by id only; the tenant was already
        # enforced at the API boundary (see publish_now).
        pub = (
            db.query(Publication)
            .filter(Publication.publication_id == publication_id)
            .first()
        )
        if pub is None:
            publish_job.status = "failed"
            publish_job.error_message = f"Publication {publication_id} not found"
            publish_job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        platform_results = []
        platforms = pub.platforms or ["youtube"]

        for platform_id in platforms:
            try:
                result = await _publish_to_platform(platform_id, pub)
                platform_results.append(result)
            except Exception as e:
                platform_results.append({
                    "platform": platform_id,
                    "status": "failed",
                    "error": str(e),
                })

        confirmed_statuses = {"completed", "published", "success", "uploaded"}
        failed_results = []
        for result in platform_results:
            if result.get("status") not in confirmed_statuses or result.get("error"):
                if not result.get("error"):
                    result["error"] = (
                        "Platform did not confirm publication "
                        f"(status={result.get('status', 'missing')})"
                    )
                failed_results.append(result)
        if not failed_results:
            job_status = "completed"
            publication_status = "published"
            error_message = None
        elif len(failed_results) == len(platform_results):
            job_status = "failed"
            publication_status = "failed"
            error_message = "; ".join(
                f"{result.get('platform', 'unknown')}: {result.get('error', 'platform publish failed')}"
                for result in failed_results
            )
        else:
            job_status = "partial"
            # Publication has no partial state in the API contract. It must not be
            # advertised as published when one of its requested platforms failed.
            publication_status = "failed"
            error_message = "; ".join(
                f"{result.get('platform', 'unknown')}: {result.get('error', 'platform publish failed')}"
                for result in failed_results
            )

        publish_job.status = job_status
        publish_job.platform_results = platform_results
        publish_job.error_message = error_message
        publish_job.completed_at = datetime.now(timezone.utc)
        pub.status = publication_status
        pub.updated_at = datetime.now(timezone.utc)
        db.commit()

        # Close the feedback loop: announce only platforms that actually
        # confirmed publication, so no false "published" signal is emitted and
        # analytics only ever measures content that really went live.
        try:
            emitted = await publish_publication_published(pub, platform_results)
            if emitted:
                logger.info(
                    "emitted %d publication.published event(s) for %s",
                    emitted,
                    publication_id,
                )
        except Exception as exc:
            logger.error(
                "failed to emit publication.published for %s: %s", publication_id, exc
            )

    except Exception as e:
        publish_job = db.query(PublishJob).filter(PublishJob.job_id == job_id).first()
        if publish_job:
            publish_job.status = "failed"
            publish_job.error_message = str(e)
            publish_job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


async def _publish_to_platform(platform_id: str, pub: Publication) -> dict[str, Any]:
    """Publish to a specific platform.

    In production, this calls the actual platform adapter.
    For now, we valida
te that we have the necessary configuration.
    """
    if platform_id == "youtube":
        from publishing_service.platforms.youtube import YouTubeAdapter

        # Check if we have API credentials
        # In production, these would come from config/secret management
        adapter = YouTubeAdapter()

        # If no API key or OAuth token, fail with clear error
        if not adapter.api_key and not adapter.oauth_token:
            raise Exception("YouTube API not configured: missing api_key and oauth_token")

        # Call the actual upload method
        # Note: This will still return a fake video_id until we implement real YouTube API calls
        # But at least it won't silently succeed without configuration
        result = adapter.upload(
            video_path=pub.asset_id or "",
            title=pub.title or "",
            description=pub.description or "",
            tags=pub.tags or [],
            privacy_status="public",
            thumbnail_path=pub.thumbnail_asset_id or None,
        )

        # Mark as requiring real implementation
        if result.get("video_id", "").startswith("yt_"):
            result["warning"] = "YouTube adapter not fully implemented - returns fake video_id"

        return result
    else:
        raise Exception(f"Platform {platform_id} not yet supported")


@app.post("/publications/{publication_id}/schedule")
async def schedule_publication(publication_id: str, request: Request, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Schedule a publication, scoped to the authenticated tenant."""
    body = await request.json()
    pub = (
        db.query(Publication)
        .filter(
            Publication.publication_id == publication_id,
            Publication.tenant_id == _require_tenant(authorization),
        )
        .first()
    )
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    try:
        pub.scheduled_at = datetime.fromisoformat(body.get("scheduled_at", "").replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pub.scheduled_at = None

    pub.status = "scheduled"
    pub.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pub)

    return {
        "publication_id": publication_id,
        "status": pub.status,
        "scheduled_at": pub.scheduled_at.isoformat() + "Z" if pub.scheduled_at else None,
    }


@app.post("/publications/{publication_id}/unpublish")
async def unpublish(publication_id: str, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Unpublish from platforms, scoped to the authenticated tenant."""
    pub = (
        db.query(Publication)
        .filter(
            Publication.publication_id == publication_id,
            Publication.tenant_id == _require_tenant(authorization),
        )
        .first()
    )
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    pub.status = "archived"
    pub.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "unpublished", "publication_id": publication_id}


@app.get("/platforms")
async def list_platforms(authorization: str = Depends(_verify_bearer)) -> list[dict[str, Any]]:
    """List connected publishing platforms."""
    return [
        {
            "platform_id": "youtube",
            "name": "YouTube",
            "status": "connected",
            "capabilities": ["upload", "schedule", "analytics"],
        },
        {
            "platform_id": "tiktok",
            "name": "TikTok",
            "status": "connected",
            "capabilities": ["upload", "schedule"],
        },
    ]



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("publishing_service.main:app", host="0.0.0.0", port=config.port, reload=False)
