"""Upload state machine.

Manages the lifecycle of a platform upload from draft through published/archived.
"""
from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class UploadState(str, Enum):
    """States in the upload lifecycle."""
    DRAFT = "draft"
    VALIDATING = "validating"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    ARCHIVED = "archived"


class UploadStateMachine:
    """State machine for platform upload lifecycle management."""

    VALID_TRANSITIONS: dict[UploadState, set[UploadState]] = {
        UploadState.DRAFT: {UploadState.VALIDATING, UploadState.FAILED, UploadState.ARCHIVED},
        UploadState.VALIDATING: {UploadState.UPLOADING, UploadState.FAILED, UploadState.ARCHIVED},
        UploadState.UPLOADING: {UploadState.PROCESSING, UploadState.FAILED, UploadState.ARCHIVED},
        UploadState.PROCESSING: {UploadState.SCHEDULED, UploadState.PUBLISHED, UploadState.FAILED},
        UploadState.SCHEDULED: {UploadState.PUBLISHED, UploadState.FAILED, UploadState.ARCHIVED},
        UploadState.PUBLISHED: {UploadState.ARCHIVED, UploadState.FAILED},
        UploadState.FAILED: {UploadState.DRAFT, UploadState.ARCHIVED},
        UploadState.ARCHIVED: set(),
    }

    def __init__(self, upload_id: str, platform_id: str, asset_id: str) -> None:
        self.upload_id = upload_id
        self.platform_id = platform_id
        self.asset_id = asset_id
        self.state = UploadState.DRAFT
        self.error_message: str | None = None
        self.platform_video_id: str | None = None
        self.platform_url: str | None = None
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self._history: list[tuple[UploadState, UploadState, datetime]] = []

    def transition(self, new_state: UploadState, error_message: str | None = None) -> None:
        """Transition to a new state with validation."""
        if new_state not in self.VALID_TRANSITIONS.get(self.state, set()):
            raise ValueError(f"Invalid transition: {self.state.value} -> {new_state.value}")
        old_state = self.state
        self.state = new_state
        self.error_message = error_message
        self.updated_at = datetime.utcnow()
        self._history.append((old_state, new_state, self.updated_at))
        logger.info("Upload %s: %s -> %s", self.upload_id, old_state.value, new_state.value)

    def to_dict(self) -> dict[str, Any]:
        """Serialize state machine to dict."""
        return {
            "upload_id": self.upload_id,
            "platform_id": self.platform_id,
            "asset_id": self.asset_id,
            "state": self.state.value,
            "error_message": self.error_message,
            "platform_video_id": self.platform_video_id,
            "platform_url": self.platform_url,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "history": [
                {"from": old.value, "to": new.value, "at": ts.isoformat()}
                for old, new, ts in self._history
            ],
        }
