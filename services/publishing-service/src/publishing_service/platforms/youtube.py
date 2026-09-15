"""YouTube platform adapter.

Handles YouTube Data API v3 upload, metadata, scheduling, and status polling.
Fully implemented with google-api-python-client and OAuth2.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
except ImportError:  # pragma: no cover - optional at unit-test time
    Credentials = None  # type: ignore
    InstalledAppFlow = None  # type: ignore
    build = None  # type: ignore
    HttpError = Exception  # type: ignore
    MediaFileUpload = None  # type: ignore

logger = logging.getLogger(__name__)


class YouTubeAdapter:
    """Adapter for the YouTube Data API v3.

    Fully implemented with actual google-api-python-client calls and OAuth2.
    """

    PLATFORM_ID = "youtube"
    MAX_TITLE_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 5000
    MAX_TAGS = 500
    TAG_MAX_LENGTH = 30

    CATEGORY_IDS = {
        "film_and_animation": "1",
        "autos_and_vehicles": "2",
        "music": "10",
        "pets_and_animals": "15",
        "sports": "17",
        "travel_and_events": "19",
        "gaming": "20",
        "videoblogging": "21",
        "people_and_blogs": "22",
        "comedy": "23",
        "entertainment": "24",
        "news_and_politics": "25",
        "howto_and_style": "26",
        "education": "27",
        "science_and_technology": "28",
        "nonprofits_and_activism": "29",
    }

    def __init__(
        self,
        api_key: str | None = None,
        oauth_token: str | None = None,
        client_secrets_path: str | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.oauth_token = oauth_token or os.getenv("YOUTUBE_OAUTH_TOKEN")
        self.client_secrets_path = client_secrets_path or os.getenv("YOUTUBE_CLIENT_SECRETS_PATH")
        self.scopes = scopes or [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
            "https://www.googleapis.com/auth/youtube.readonly",
        ]
        self._credentials: Credentials | None = None
        self._service = None
        self._validate_config()
        logger.info("YouTubeAdapter initialized")

    def _validate_config(self) -> None:
        if not self.api_key and not self.oauth_token and not self.client_secrets_path:
            logger.warning(
                "YouTubeAdapter initialized without API credentials. "
                "Upload operations will fail. "
                "Set YOUTUBE_API_KEY, YOUTUBE_OAUTH_TOKEN, or YOUTUBE_CLIENT_SECRETS_PATH."
            )

    def _require_credentials(self) -> None:
        if not self.api_key and not self.oauth_token and not self.client_secrets_path:
            raise RuntimeError(
                "YouTube API not configured. "
                "api_key, oauth_token, and client_secrets_path are all missing. "
                "Cannot perform upload operations."
            )
        # Defer hard ImportError until an actual client is built so unit tests
        # that mock the adapter can exercise failure paths without google-api installed.


    def _get_credentials(self) -> Credentials:
        if self._credentials is not None:
            return self._credentials
        if self.oauth_token:
            self._credentials = Credentials(token=self.oauth_token)
            return self._credentials
        if self.client_secrets_path and os.path.exists(self.client_secrets_path):
            flow = InstalledAppFlow.from_client_secrets_file(
                self.client_secrets_path,
                scopes=self.scopes,
            )
            self._credentials = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent",
            )
            return self._credentials
        raise RuntimeError(
            "No valid credentials found. Provide either oauth_token or client_secrets_path."
        )

    def _get_service(self):
        if self._service is not None:
            return self._service
        if self.api_key:
            self._service = build("youtube", "v3", developerKey=self.api_key)
        else:
            credentials = self._get_credentials()
            self._service = build("youtube", "v3", credentials=credentials)
        return self._service

    def upload(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str] | None = None,
        category_id: str = "22",
        privacy_status: str = "private",
        scheduled_at: str | None = None,
        thumbnail_path: str | None = None,
    ) -> dict[str, Any]:
        self._require_credentials()
        if len(title) > self.MAX_TITLE_LENGTH:
            raise ValueError(f"Title exceeds maximum length of {self.MAX_TITLE_LENGTH} characters")
        if len(description) > self.MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"Description exceeds maximum length of {self.MAX_DESCRIPTION_LENGTH} characters")
        if tags:
            if len(tags) > self.MAX_TAGS:
                raise ValueError(f"Exceeds maximum of {self.MAX_TAGS} tags")
            for tag in tags:
                if len(tag) > self.TAG_MAX_LENGTH:
                    raise ValueError(f"Tag exceeds maximum length of {self.TAG_MAX_LENGTH} characters")
        if privacy_status not in ("public", "private", "unlisted"):
            raise ValueError(f"Invalid privacy_status: {privacy_status}")
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        service = self._get_service()
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": {"privacyStatus": privacy_status},
        }
        if scheduled_at:
            body["status"]["publishAt"] = scheduled_at
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

        try:
            request = service.videos().insert(
                part=",".join(["snippet", "status"]),
                body=body,
                media_body=media,
            )
            response = request.execute()
            video_id = response.get("id")
            if not video_id:
                raise RuntimeError(f"Upload failed: No video ID returned. Response: {response}")
            logger.info("Successfully uploaded video %s to YouTube: %s", video_id, title)
            if thumbnail_path:
                if not os.path.exists(thumbnail_path):
                    raise FileNotFoundError(f"Thumbnail file not found: {thumbnail_path}")
                try:
                    thumbnail_media = MediaFileUpload(thumbnail_path)
                    service.thumbnails().set(videoId=video_id, media_body=thumbnail_media).execute()
                    logger.info("Successfully uploaded thumbnail for video %s", video_id)
                except HttpError as e:
                    raise RuntimeError(f"YouTube thumbnail upload failed: {e}") from e
            return {
                "platform": self.PLATFORM_ID,
                "video_id": video_id,
                "status": "uploaded",
                "privacy_status": privacy_status,
                "scheduled_at": scheduled_at,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "uploaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        except HttpError as e:
            error_details = getattr(e, "_content", {})
            error_message = error_details.get("error", {}).get("message", str(e)) if isinstance(error_details, dict) else str(e)
            logger.error("YouTube upload failed: %s", error_message)
            raise RuntimeError(f"YouTube upload failed: {error_message}") from e

    def update_metadata(
        self,
        video_id: str,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        category_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_credentials()
        service = self._get_service()
        try:
            response = service.videos().list(part="snippet", id=video_id).execute()
            current_snippet = response.get("items", [{}])[0].get("snippet", {})
        except HttpError as e:
            raise RuntimeError(f"Failed to get current video metadata: {e}") from e
        body = {
            "id": video_id,
            "snippet": {
                "title": title if title is not None else current_snippet.get("title", ""),
                "description": description if description is not None else current_snippet.get("description", ""),
                "tags": tags if tags is not None else current_snippet.get("tags", []),
                "categoryId": category_id if category_id is not None else current_snippet.get("categoryId", "22"),
            },
        }
        try:
            service.videos().update(part="snippet", body=body).execute()
            logger.info("Successfully updated metadata for video %s", video_id)
            return {
                "platform": self.PLATFORM_ID,
                "video_id": video_id,
                "status": "updated",
                "title": body["snippet"]["title"],
                "description": body["snippet"]["description"],
                "tags": body["snippet"]["tags"],
                "category_id": body["snippet"]["categoryId"],
            }
        except HttpError as e:
            error_details = getattr(e, "_content", {})
            error_message = error_details.get("error", {}).get("message", str(e)) if isinstance(error_details, dict) else str(e)
            raise RuntimeError(f"YouTube metadata update failed: {error_message}") from e

    def delete_video(self, video_id: str) -> dict[str, Any]:
        self._require_credentials()
        service = self._get_service()
        try:
            service.videos().delete(id=video_id).execute()
            logger.info("Successfully deleted video %s", video_id)
            return {"platform": self.PLATFORM_ID, "video_id": video_id, "status": "deleted"}
        except HttpError as e:
            error_details = getattr(e, "_content", {})
            error_message = error_details.get("error", {}).get("message", str(e)) if isinstance(error_details, dict) else str(e)
            raise RuntimeError(f"YouTube delete failed: {error_message}") from e

    def get_video_status(self, video_id: str) -> dict[str, Any]:
        self._require_credentials()
        service = self._get_service()
        try:
            response = service.videos().list(part="status,snippet,contentDetails", id=video_id).execute()
            video = response.get("items", [{}])[0]
            if not video:
                return {"platform": self.PLATFORM_ID, "video_id": video_id, "status": "not_found", "error": "Video not found"}
            status = video.get("status", {})
            snippet = video.get("snippet", {})
            content_details = video.get("contentDetails", {})
            return {
                "platform": self.PLATFORM_ID,
                "video_id": video_id,
                "status": status.get("uploadStatus", "unknown"),
                "privacy_status": status.get("privacyStatus", "unknown"),
                "rejection_reasons": status.get("rejectionReasons", []),
                "failure_reason": status.get("failureReason", ""),
                "published_at": snippet.get("publishedAt"),
                "live_broadcast_content": snippet.get("liveBroadcastContent"),
                "duration": content_details.get("duration"),
                "dimension": content_details.get("dimension"),
                "definition": content_details.get("definition"),
                "caption": content_details.get("caption"),
                "licensed_content": content_details.get("licensedContent"),
            }
        except HttpError as e:
            error_details = getattr(e, "_content", {})
            error_message = error_details.get("error", {}).get("message", str(e)) if isinstance(error_details, dict) else str(e)
            raise RuntimeError(f"YouTube status check failed: {error_message}") from e
