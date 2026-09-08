"""YouTube platform adapter.

Handles YouTube Data API v3 upload, metadata, scheduling, and status polling.
Fully implemented with google-api-python-client and OAuth2.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

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
    
    # YouTube category IDs
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
        """Validate that adapter has required configuration."""
        if not self.api_key and not self.oauth_token and not self.client_secrets_path:
            logger.warning(
                "YouTubeAdapter initialized without API credentials. "
                "Upload operations will fail. "
                "Set YOUTUBE_API_KEY, YOUTUBE_OAUTH_TOKEN, or YOUTUBE_CLIENT_SECRETS_PATH."
            )

    def _require_credentials(self) -> None:
        """Raise exception if credentials are not configured."""
        if not self.api_key and not self.oauth_token and not self.client_secrets_path:
            raise RuntimeError(
                "YouTube API not configured. "
                "api_key, oauth_token, and client_secrets_path are all missing. "
                "Cannot perform upload operations."
            )

    def _get_credentials(self) -> Credentials:
        """Get OAuth2 credentials, using cached credentials if available."""
        if self._credentials is not None:
            return self._credentials
        
        # Try to use OAuth token if provided
        if self.oauth_token:
            self._credentials = Credentials(token=self.oauth_token)
            return self._credentials
        
        # Try to use client secrets file
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
            "No valid credentials found. "
            "Provide either oauth_token or client_secrets_path."
        )

    def _get_service(self):
        """Get or create the YouTube API service."""
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
        """Upload a video to YouTube.
        
        Implements actual YouTube Data API v3 upload using google-api-python-client.
        
        Args:
            video_path: Path to the video file to upload
            title: Video title (max 100 characters)
            description: Video description (max 5000 characters)
            tags: List of tags (max 500 tags, each max 30 characters)
            category_id: YouTube category ID (default: "22" for People & Blogs)
            privacy_status: "public", "private", or "unlisted"
            scheduled_at: ISO 8601 datetime string for scheduled publishing
            thumbnail_path: Path to thumbnail image file
            
        Returns:
            dict with platform, video_id, status, and other metadata
        """
        self._require_credentials()
        
        # Validate inputs
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
            raise ValueError(f"Invalid privacy_status: {privacy_status}. Must be 'public', 'private', or 'unlisted'")
        
        # Verify video file exists
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        service = self._get_service()
        
        # Build the video metadata
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
            },
        }
        
        # Add scheduled publishing if specified
        if scheduled_at:
            body["status"]["publishAt"] = scheduled_at
        
        # Create media file upload object
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        
        try:
            # Execute the upload request
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
            
            # Upload thumbnail if provided
            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    thumbnail_media = MediaFileUpload(thumbnail_path)
                    thumbnail_request = service.thumbnails().set(
                        videoId=video_id,
                        media_body=thumbnail_media,
                    )
                    thumbnail_response = thumbnail_request.execute()
                    logger.info("Successfully uploaded thumbnail for video %s", video_id)
                except HttpError as e:
                    logger.warning("Failed to upload thumbnail for video %s: %s", video_id, str(e))
            
            return {
                "platform": self.PLATFORM_ID,
                "video_id": video_id,
                "status": "uploaded",
                "privacy_status": privacy_status,
                "scheduled_at": scheduled_at,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "uploaded_at": datetime.utcnow().isoformat() + "Z",
            }
            
        except HttpError as e:
            error_details = getattr(e, "_content", {})
            error_message = error_details.get("error", {}).get("message", str(e))
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
        """Update video metadata on YouTube.
        
        Args:
            video_id: YouTube video ID
            title: New title
            description: New description
            tags: New list of tags
            category_id: New category ID
            
        Returns:
            dict with updated metadata
        """
        self._require_credentials()
        service = self._get_service()
        
        # Get current snippet
        try:
            request = service.videos().list(
                part="snippet",
                id=video_id,
            )
            response = request.execute()
            current_video = response.get("items", [{}])[0]
            current_snippet = current_video.get("snippet", {})
        except HttpError as e:
            raise RuntimeError(f"Failed to get current video metadata: {e}") from e
        
        # Build update body
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
            request = service.videos().update(
                part="snippet",
                body=body,
            )
            response = request.execute()
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
            error_message = error_details.get("error", {}).get("message", str(e))
            logger.error("YouTube metadata update failed: %s", error_message)
            raise RuntimeError(f"YouTube metadata update failed: {error_message}") from e

    def delete_video(self, video_id: str) -> dict[str, Any]:
        """Delete/unpublish a video from YouTube.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            dict with deletion status
        """
        self._require_credentials()
        service = self._get_service()
        
        try:
            request = service.videos().delete(
                id=video_id,
            )
            response = request.execute()
            logger.info("Successfully deleted video %s", video_id)
            return {
                "platform": self.PLATFORM_ID,
                "video_id": video_id,
                "status": "deleted",
            }
        except HttpError as e:
            error_details = getattr(e, "_content", {})
            error_message = error_details.get("error", {}).get("message", str(e))
            logger.error("YouTube delete failed: %s", error_message)
            raise RuntimeError(f"YouTube delete failed: {error_message}") from e

    def get_video_status(self, video_id: str) -> dict[str, Any]:
        """Get the processing and privacy status of a video.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            dict with video status information
        """
        self._require_credentials()
        service = self._get_service()
        
        try:
            request = service.videos().list(
                part="status,snippet,contentDetails",
                id=video_id,
            )
            response = request.execute()
            video = response.get("items", [{}])[0]
            
            if not video:
                return {
                    "platform": self.PLATFORM_ID,
                    "video_id": video_id,
                    "status": "not_found",
                    "error": "Video not found",
                }
            
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
            error_message = error_details.get("error", {}).get("message", str(e))
            logger.error("YouTube status check failed: %s", error_message)
            raise RuntimeError(f"YouTube status check failed: {error_message}") from e
