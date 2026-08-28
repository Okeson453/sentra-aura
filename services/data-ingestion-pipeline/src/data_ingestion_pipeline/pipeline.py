"""Ingestion pipeline orchestrator."""
from __future__ import annotations

from typing import Any

from data_ingestion_pipeline.models import IngestionJob, RawEvent, NormalizedEvent
from data_ingestion_pipeline.collectors import BaseCollector
from data_ingestion_pipeline.normalizers import BaseNormalizer
from data_ingestion_pipeline.publisher import NATSPublisher


class IngestionPipeline:
    """Orchestrates data collection, normalization, and publishing."""

    def __init__(
        self,
        collector: BaseCollector,
        normalizer: BaseNormalizer,
        publisher: NATSPublisher | None = None,
    ) -> None:
        self.collector = collector
        self.normalizer = normalizer
        self.publisher = publisher or NATSPublisher()

    async def run(self, params: dict[str, Any], subject: str = "sentraura.events") -> IngestionJob:
        """Run the ingestion pipeline."""
        from datetime import datetime

        job = IngestionJob(source=self.collector.source)
        job.started_at = datetime.utcnow()
        job.status = "RUNNING"

        try:
            # Collect
            raw_events = await self.collector.collect(params)
            job.events_collected = len(raw_events)

            # Normalize
            normalized_events: list[NormalizedEvent] = []
            for event in raw_events:
                try:
                    ne = await self.normalizer.normalize(event)
                    normalized_events.append(ne)
                except Exception as exc:
                    job.errors.append(f"Normalize failed for {event.event_id}: {exc}")

            job.events_normalized = len(normalized_events)

            # Publish
            if self.publisher:
                published = await self.publisher.publish_batch(subject, normalized_events)
                if published != len(normalized_events):
                    job.errors.append(f"Only {published}/{len(normalized_events)} events published")

            job.status = "COMPLETED" if not job.errors else "PARTIAL"
        except Exception as exc:
            job.status = "FAILED"
            job.errors.append(str(exc))
        finally:
            job.completed_at = datetime.utcnow()

        return job
