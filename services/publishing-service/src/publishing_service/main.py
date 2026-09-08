"""Publishing Service FastAPI service entrypoint.

Multi-platform publishing, scheduling, metadata optimization, post analytics
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from publishing_service.config import ServiceConfig

logger = logging.getLogger(__name__)

config: ServiceConfig

# Database-backed store instead of in-memory
from sqlalchemy import create_engine, Column, String, Text, JSON, DateTime, Integer
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

Base = declarative_base()

class Publication(Base):
    __tablename__ = "publications"
    publication_id = Column(String(36), primary_key=True)
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PublishJob(Base):
    __tablename__ = "publish_jobs"
    job_id = Column(String(36), primary_key=True)
    publication_id = Column(String(36))
    status = Column(String(50), default="queued")
    platform_results = Column(JSON, default=[])
    started_at = Column(DateTime, default=datetime.utcnow)
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config
    config = ServiceConfig.from_env()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    logger.info("Publishing Service started: %s v%s", config.service_name, config.version)
    yield
    logger.info("Publishing Service shutting down")


app = FastAPI(
    title="SentraAura Publishing Service",
    version="1.0.0",
    lifespan=lifespan,
)


def _require_bearer(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization[7:]


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
        db.execute("SELECT 1")
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
async def create_publication(request: Request, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Create a publication."""
    body = await request.json()
    publication_id = f"pub-{uuid.uuid4().hex[:12]}"
    
    scheduled_at = body.get("scheduled_at")
    if scheduled_at:
        try:
            scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            scheduled_at = None
    
    pub = Publication(
        publication_id=publication_id,
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
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
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
async def list_publications(authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """List publications."""
    publications = db.query(Publication).all()
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
async def get_publication(publication_id: str, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get publication by ID."""
    pub = db.query(Publication).filter(Publication.publication_id == publication_id).first()
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
async def update_publication(publication_id: str, request: Request, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Update publication."""
    body = await request.json()
    pub = db.query(Publication).filter(Publication.publication_id == publication_id).first()
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
    
    pub.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pub)
    
    return {
        "publication_id": pub.publication_id,
        "status": pub.status,
        "updated_at": pub.updated_at.isoformat() + "Z",
    }


@app.delete("/publications/{publication_id}")
async def delete_publication(publication_id: str, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> None:
    """Delete/archive publication."""
    pub = db.query(Publication).filter(Publication.publication_id == publication_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="publication_id not found")
    pub.status = "archived"
    db.commit()
    return None


@app.post("/publications/{publication_id}/publish")
async def publish_now(publication_id: str, request: Request, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Publish immediately to configured platforms."""
    pub = db.query(Publication).filter(Publication.publication_id == publication_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    
    job_id = f"publish-{uuid.uuid4().hex[:12]}"
    
    # Create publish job
    publish_job = PublishJob(
        job_id=job_id,
        publication_id=publication_id,
        status="queued",
        platform_results=[],
        started_at=datetime.utcnow(),
    )
    db.add(publish_job)
    db.commit()
    
    # Process publishing asynchronously
    asyncio.create_task(_process_publish_job(db, job_id, publication_id, pub))
    
    return {
        "job_id": job_id,
        "publication_id": publication_id,
        "status": "queued",
        "platform_results": [],
    }


async def _process_publish_job(db: Session, job_id: str, publication_id: str, pub: Publication) -> None:
    """Background task to process publish job.
    
    Calls platform adapters to perform actual publishing.
    """
    try:
        publish_job = db.query(PublishJob).filter(PublishJob.job_id == job_id).first()
        if not publish_job:
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
        
        # Update job status
        publish_job.status = "completed"
        publish_job.platform_results = platform_results
        publish_job.completed_at = datetime.utcnow()
        db.commit()
        
        # Update publication status
        pub.status = "published"
        pub.updated_at = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        publish_job = db.query(PublishJob).filter(PublishJob.job_id == job_id).first()
        if publish_job:
            publish_job.status = "failed"
            publish_job.error_message = str(e)
            publish_job.completed_at = datetime.utcnow()
            db.commit()


async def _publish_to_platform(platform_id: str, pub: Publication) -> dict[str, Any]:
    """Publish to a specific platform.
    
    In production, this calls the actual platform adapter.
    For now, we validate that we have the necessary configuration.
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
        )
        
        # Mark as requiring real implementation
        if result.get("video_id", "").startswith("yt_"):
            result["warning"] = "YouTube adapter not fully implemented - returns fake video_id"
        
        return result
    else:
        raise Exception(f"Platform {platform_id} not yet supported")


@app.post("/publications/{publication_id}/schedule")
async def schedule_publication(publication_id: str, request: Request, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Schedule publication."""
    body = await request.json()
    pub = db.query(Publication).filter(Publication.publication_id == publication_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    
    try:
        pub.scheduled_at = datetime.fromisoformat(body.get("scheduled_at", "").replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pub.scheduled_at = None
    
    pub.status = "scheduled"
    pub.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pub)
    
    return {
        "publication_id": publication_id,
        "status": pub.status,
        "scheduled_at": pub.scheduled_at.isoformat() + "Z" if pub.scheduled_at else None,
    }


@app.post("/publications/{publication_id}/unpublish")
async def unpublish(publication_id: str, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Unpublish from platforms."""
    pub = db.query(Publication).filter(Publication.publication_id == publication_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    pub.status = "archived"
    pub.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "unpublished", "publication_id": publication_id}


@app.get("/platforms")
async def list_platforms(authorization: str = Depends(_require_bearer)) -> list[dict[str, Any]]:
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
