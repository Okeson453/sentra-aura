"""Tests for data ingestion pipeline."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from data_ingestion_pipeline.collectors import (
    YouTubeAnalyticsCollector, YouTubeDataCollector, SocialTrendCollector,
    CompetitorCollector, RSSFeedCollector, CollectorConfig,
)
from data_ingestion_pipeline.models import RawEvent, NormalizedEvent
from data_ingestion_pipeline.publisher import NATSPublisher, NATSConfig, PublishResult
from data_ingestion_pipeline.normalizers import (
    normalize_youtube_analytics, normalize_social_trends,
    normalize_competitor_data, normalize_rss_feed,
)


class TestYouTubeAnalyticsCollector:
    @pytest.mark.asyncio
    async def test_collect_requires_channel_id(self):
        collector = YouTubeAnalyticsCollector()
        with pytest.raises(ValueError, match="channel_id is required"):
            await collector.collect({})

    @pytest.mark.asyncio
    async def test_collect_success(self):
        collector = YouTubeAnalyticsCollector()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "rows": [
                ["2024-01-01", 1000, 500, 120],
                ["2024-01-02", 1500, 600, 130],
            ]
        }
        with patch.object(collector, "_rate_limited_request", new_callable=AsyncMock, return_value=mock_response):
            events = await collector.collect({"channel_id": "UC123", "metrics": "views,estimatedMinutesWatched,averageViewDuration"})
        assert len(events) == 2
        assert events[0].source == "youtube_analytics"
        assert events[0].raw_payload["channel_id"] == "UC123"

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        collector = YouTubeAnalyticsCollector(CollectorConfig(source="youtube_analytics", source_type="platform_api", rate_limit_rps=2.0))
        mock_response = MagicMock()
        mock_response.json.return_value = {"rows": []}

        with patch.object(collector, "_rate_limited_request", new_callable=AsyncMock, return_value=mock_response) as mock_req:
            await collector.collect({"channel_id": "UC123"})
            await collector.collect({"channel_id": "UC123"})
            assert mock_req.call_count == 2


class TestYouTubeDataCollector:
    @pytest.mark.asyncio
    async def test_collect_videos(self):
        collector = YouTubeDataCollector()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {"id": {"videoId": "vid1"}, "snippet": {"title": "Test Video", "publishedAt": "2024-01-01T00:00:00Z"}},
            ]
        }
        with patch.object(collector, "_rate_limited_request", new_callable=AsyncMock, return_value=mock_response):
            events = await collector.collect({"channel_id": "UC123"})
        assert len(events) == 1
        assert events[0].raw_payload["video_id"] == "vid1"


class TestSocialTrendCollector:
    @pytest.mark.asyncio
    async def test_collect_with_fallback(self):
        collector = SocialTrendCollector()
        with patch.object(collector, "_rate_limited_request", new_callable=AsyncMock, side_effect=Exception("Network error")):
            events = await collector.collect({"geo": "US", "topic": "AI"})
        assert len(events) == 1
        assert events[0].raw_payload["topic"] == "AI"


class TestCompetitorCollector:
    @pytest.mark.asyncio
    async def test_collect_competitor_stats(self):
        collector = CompetitorCollector()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [{
                "statistics": {"subscriberCount": "10000", "videoCount": "50", "viewCount": "500000"},
                "snippet": {"title": "Competitor Channel"},
            }]
        }
        with patch.object(collector, "_rate_limited_request", new_callable=AsyncMock, return_value=mock_response):
            events = await collector.collect({"competitor_id": "UC999"})
        assert len(events) == 1
        assert events[0].raw_payload["subscriber_count"] == 10000


class TestRSSFeedCollector:
    @pytest.mark.asyncio
    async def test_collect_rss(self):
        collector = RSSFeedCollector()
        xml = """<?xml version="1.0"?><rss><channel><item><title>News 1</title><link>http://example.com/1</link></item></channel></rss>"""
        mock_response = MagicMock()
        mock_response.text = xml
        with patch.object(collector, "_rate_limited_request", new_callable=AsyncMock, return_value=mock_response):
            events = await collector.collect({"feed_url": "http://example.com/feed"})
        assert len(events) == 1
        assert events[0].raw_payload["title"] == "News 1"


class TestNATSPublisher:
    @pytest.mark.asyncio
    async def test_publish_mock_mode(self):
        publisher = NATSPublisher(NATSConfig(mock_mode=True))
        event = NormalizedEvent(
            event_id="evt-1",
            source="test",
            event_type="test_event",
            channel_id="ch-1",
            tenant_id="t-1",
            payload={"key": "value"},
        )
        result = await publisher.publish("sentraura.events.test", event)
        assert result.success is True
        assert result.event_id == "evt-1"

    @pytest.mark.asyncio
    async def test_publish_batch(self):
        publisher = NATSPublisher(NATSConfig(mock_mode=True))
        events = [
            NormalizedEvent(event_id=f"evt-{i}", source="test", event_type="test_event", channel_id="ch-1", tenant_id="t-1", payload={"i": i})
            for i in range(10)
        ]
        results = await publisher.publish_batch("sentraura.events.test", events)
        assert len(results) == 10
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_dlq_on_failure(self):
        publisher = NATSPublisher(NATSConfig(max_publish_retries=1))
        event = NormalizedEvent(event_id="evt-fail", source="test", event_type="test_event", channel_id="ch-1", tenant_id="t-1", payload={})
        publisher._connected = True
        publisher._js = AsyncMock()
        publisher._js.publish.side_effect = [OSError("publish failed"), None]

        result = await publisher.publish("sentraura.events.test", event)

        assert result.success is False
        assert result.error == "publish failed"
        assert publisher._js.publish.await_count == 2


class TestNormalizers:
    @pytest.mark.asyncio
    async def test_normalize_youtube_analytics(self):
        raw = RawEvent(
            source="youtube_analytics",
            source_type="platform_api",
            raw_payload={"channel_id": "UC123", "date": "2024-01-01", "views": 1000, "watch_time": 5000},
            channel_id="UC123",
        )
        normalized = await normalize_youtube_analytics(raw)
        assert normalized.event_type == "performance_metrics"
        assert normalized.payload["views"] == 1000

    @pytest.mark.asyncio
    async def test_normalize_social_trends(self):
        raw = RawEvent(
            source="social_trends",
            source_type="trend_api",
            raw_payload={"topic": "AI", "trend_score": 0.85, "volume": 50000},
        )
        normalized = await normalize_social_trends(raw)
        assert normalized.event_type == "trend_signal"
        assert normalized.payload["topic"] == "AI"

    @pytest.mark.asyncio
    async def test_normalize_competitor_data(self):
        raw = RawEvent(
            source="competitor_data",
            source_type="scraping",
            raw_payload={"competitor_id": "UC999", "latest_video_views": 10000},
        )
        normalized = await normalize_competitor_data(raw)
        assert normalized.event_type == "competitor_activity"
        assert normalized.payload["latest_video_views"] == 10000

    @pytest.mark.asyncio
    async def test_normalize_rss_feed(self):
        raw = RawEvent(
            source="rss_feed",
            source_type="feed",
            raw_payload={"title": "News", "url": "http://example.com"},
        )
        normalized = await normalize_rss_feed(raw)
        assert normalized.event_type == "rss_item"
        assert normalized.payload["title"] == "News"


class TestPublisherFailureContracts:
    @staticmethod
    def _event(event_id: str = "evt-1") -> NormalizedEvent:
        return NormalizedEvent(
            event_id=event_id,
            source="test",
            event_type="test_event",
            channel_id="ch-1",
            tenant_id="t-1",
            payload={},
        )

    @pytest.mark.asyncio
    async def test_missing_transport_does_not_report_success(self):
        publisher = NATSPublisher(NATSConfig(max_connect_attempts=1))
        with patch.dict("sys.modules", {"nats": None}):
            result = await publisher.publish("sentraura.events.test", self._event())

        assert result.success is False
        assert "transport unavailable" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_failed_connection_is_bounded_and_does_not_report_success(self):
        publisher = NATSPublisher(
            NATSConfig(
                max_connect_attempts=2,
                connect_timeout_seconds=0.01,
                reconnect_wait_seconds=0,
            )
        )
        with patch("nats.connect", new_callable=AsyncMock, side_effect=OSError("refused")) as connect:
            result = await publisher.publish("sentraura.events.test", self._event())

        assert result.success is False
        assert "failed after 2 attempts" in (result.error or "")
        assert "refused" in (result.error or "")
        assert connect.await_count == 2

    @pytest.mark.asyncio
    async def test_explicit_mock_mode_is_labelled(self):
        publisher = NATSPublisher(NATSConfig(mock_mode=True))
        result = await publisher.publish("sentraura.events.test", self._event())

        assert result.success is True
        assert "mock mode" in (result.error or "").lower()
        assert publisher.is_ready is True


class TestPipelinePublishAccounting:
    @staticmethod
    def _pipeline(results: list[PublishResult]):
        from data_ingestion_pipeline.pipeline import IngestionPipeline

        raw_events = [
            RawEvent(source="test", source_type="test", raw_payload={"i": i})
            for i in range(len(results))
        ]
        normalized_events = [
            NormalizedEvent(
                event_id=result.event_id,
                source="test",
                event_type="test_event",
                payload={},
            )
            for result in results
        ]
        collector = MagicMock(source="test")
        collector.collect = AsyncMock(return_value=raw_events)
        normalizer = MagicMock()
        normalizer.normalize = AsyncMock(side_effect=normalized_events)
        publisher = MagicMock()
        publisher.publish_batch = AsyncMock(return_value=results)
        return IngestionPipeline(collector, normalizer, publisher)

    @pytest.mark.asyncio
    async def test_complete_when_every_publish_succeeds(self):
        pipeline = self._pipeline([
            PublishResult(success=True, event_id="evt-1"),
            PublishResult(success=True, event_id="evt-2"),
        ])

        job = await pipeline.run({}, subject="sentraura.events.test")

        assert job.status == "COMPLETED"
        assert job.errors == []

    @pytest.mark.asyncio
    async def test_partial_lists_failing_subjects_events_and_reasons(self):
        pipeline = self._pipeline([
            PublishResult(success=True, event_id="evt-1"),
            PublishResult(success=False, event_id="evt-2", error="broker refused"),
            PublishResult(success=False, event_id="evt-3", error="ack timeout"),
        ])

        job = await pipeline.run({}, subject="sentraura.events.test")

        assert job.status == "PARTIAL"
        assert job.errors == [
            "Publish failed for subject sentraura.events.test, event evt-2: broker refused",
            "Publish failed for subject sentraura.events.test, event evt-3: ack timeout",
        ]


@pytest.mark.asyncio
async def test_nats_readiness_reflects_publisher_state():
    from data_ingestion_pipeline.main import _nats_readiness, publisher
    from service_kit.health import HealthStatus

    with patch.object(publisher.config, "mock_mode", False), patch.object(
        publisher, "_connected", False
    ):
        status, _ = await _nats_readiness()
        assert status is HealthStatus.UNHEALTHY

    with patch.object(publisher.config, "mock_mode", True):
        status, _ = await _nats_readiness()
        assert status is HealthStatus.HEALTHY
