"""Tests for control-plane-api services."""
from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from control_plane_api.schemas import (
    ChannelCreate, ChannelUpdate, ChannelResponse,
    ContentPlanCreate, ScriptCreate, ScriptUpdate, VideoCreate, ClipCreate,
    PublicationCreate, PublicationUpdate,
    PerformanceCreate,
    ExperimentCreate, ExperimentUpdate,
    PolicyCreate, PolicyUpdate,
    DecisionLogCreate, DecisionLogOverride,
    PaginationParams,
)
from control_plane_api.services import (
    ChannelService, ContentService, PublishingService,
    ExperimentService, PolicyService, DecisionService,
)


def make_channel_mock(**kwargs):
    defaults = dict(
        id="ch-1", tenant_id="t-1", name="Test Channel", platform="youtube",
        platform_channel_id="UC123", status="ACTIVE", niche="tech",
        target_audience="developers", content_mix={}, schedule={},
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        created_by="user-1", updated_by="user-1",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_plan_mock(**kwargs):
    defaults = dict(
        id="plan-1", channel_id="ch-1", topic="AI", status="DRAFT",
        strategy={}, budget={}, deadline=None,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_script_mock(**kwargs):
    defaults = dict(
        id="script-1", content_plan_id="plan-1", title="Script", content="Old content",
        status="DRAFT", word_count=100, estimated_duration=60,
        disclosure_tags=[], version=1,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_video_mock(**kwargs):
    defaults = dict(
        id="vid-1", script_id="script-1", channel_id="ch-1", status="RENDERING",
        duration_seconds=0, resolution="1080p", asset_manifest={},
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_clip_mock(**kwargs):
    defaults = dict(
        id="clip-1", video_id="vid-1", channel_id="ch-1", clip_type="HOOK",
        status="READY_TO_PUBLISH", start_ms=0, end_ms=15000, duration_ms=15000,
        aspect_ratio="9:16", scores={}, lineage={},
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_pub_mock(**kwargs):
    defaults = dict(
        id="pub-1", channel_id="ch-1", video_id="vid-1", clip_id=None,
        platform="YOUTUBE", platform_id="", platform_url="", status="SCHEDULED",
        scheduled_at=None, published_at=None, metadata_json={},
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_exp_mock(**kwargs):
    defaults = dict(
        id="exp-1", channel_id="ch-1", name="Test", hypothesis="H1",
        variant_ids=[], control_id="", asset_id="", metrics=[], status="DRAFT",
        start_time=None, end_time=None, required_sample_size=1000, results={},
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_policy_mock(**kwargs):
    defaults = dict(
        id="pol-1", channel_id="ch-1", policy_type="CONTENT", autonomy_level="L2",
        rules={}, weights={}, version=1, status="ACTIVE",
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_decision_mock(**kwargs):
    defaults = dict(
        id="dec-1", channel_id="ch-1", agent_type="CLIPPING", decision="PUBLISH",
        reasoning=[], confidence=0.85, alternatives_rejected=[],
        human_override_possible=True, override_status="PENDING",
        override_by=None, override_at=None,
        created_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestChannelService:
    def test_create_channel(self):
        db = MagicMock()
        repo = MagicMock()
        repo.list.return_value = ([], 0)
        repo.create.return_value = make_channel_mock()

        with patch("control_plane_api.services.ChannelRepository", return_value=repo):
            svc = ChannelService(db)
            result = svc.create(ChannelCreate(tenant_id="t-1", name="Test Channel", platform="youtube"))
        assert result.name == "Test Channel"
        assert result.status == "ACTIVE"

    def test_channel_limit_enforced(self):
        db = MagicMock()
        repo = MagicMock()
        repo.list.return_value = ([make_channel_mock()] * 10, 10)

        with patch("control_plane_api.services.ChannelRepository", return_value=repo), \
             patch("control_plane_api.services.settings.max_channels_per_tenant", 10):
            svc = ChannelService(db)
            with pytest.raises(ValueError, match="Tenant channel limit reached"):
                svc.create(ChannelCreate(tenant_id="t-1", name="Test", platform="youtube"))

    def test_update_channel(self):
        db = MagicMock()
        repo = MagicMock()
        repo.update.return_value = make_channel_mock(name="Updated")

        with patch("control_plane_api.services.ChannelRepository", return_value=repo):
            svc = ChannelService(db)
            result = svc.update("ch-1", ChannelUpdate(name="Updated"))
        assert result.name == "Updated"

    def test_delete_channel(self):
        db = MagicMock()
        repo = MagicMock()
        repo.delete.return_value = True

        with patch("control_plane_api.services.ChannelRepository", return_value=repo):
            svc = ChannelService(db)
            assert svc.delete("ch-1") is True


class TestContentService:
    def test_create_plan(self):
        db = MagicMock()
        repo = MagicMock()
        repo.create.return_value = make_plan_mock()

        with patch("control_plane_api.services.ContentPlanRepository", return_value=repo):
            svc = ContentService(db)
            result = svc.create_plan(ContentPlanCreate(channel_id="ch-1", topic="AI"))
        assert result.topic == "AI"
        assert result.status == "DRAFT"

    def test_script_version_increment(self):
        db = MagicMock()
        script_repo = MagicMock()
        script_repo.get.return_value = make_script_mock(content="Old content", version=1)
        script_repo.update.return_value = make_script_mock(content="New content", version=2)

        with patch("control_plane_api.services.ScriptRepository", return_value=script_repo):
            svc = ContentService(db)
            result = svc.update_script("script-1", ScriptUpdate(content="New content"))
        assert result.version == 2

    def test_create_video(self):
        db = MagicMock()
        repo = MagicMock()
        repo.create.return_value = make_video_mock()

        with patch("control_plane_api.services.VideoRepository", return_value=repo):
            svc = ContentService(db)
            result = svc.create_video(VideoCreate(script_id="script-1", channel_id="ch-1"))
        assert result.status == "RENDERING"

    def test_create_clip(self):
        db = MagicMock()
        repo = MagicMock()
        repo.create.return_value = make_clip_mock()

        with patch("control_plane_api.services.ClipRepository", return_value=repo):
            svc = ContentService(db)
            result = svc.create_clip(ClipCreate(video_id="vid-1", channel_id="ch-1", clip_type="HOOK"))
        assert result.clip_type == "HOOK"


class TestPublishingService:
    def test_create_publication(self):
        db = MagicMock()
        repo = MagicMock()
        repo.create.return_value = make_pub_mock()

        with patch("control_plane_api.services.PublicationRepository", return_value=repo):
            svc = PublishingService(db)
            result = svc.create_publication(PublicationCreate(channel_id="ch-1", video_id="vid-1", platform="YOUTUBE"))
        assert result.status == "SCHEDULED"

    def test_publish_sets_published_at(self):
        db = MagicMock()
        pub_repo = MagicMock()
        pub_repo.get.return_value = make_pub_mock(status="SCHEDULED")
        pub_repo.update.return_value = make_pub_mock(status="PUBLISHED", platform_id="plat-123", published_at=datetime.utcnow())

        with patch("control_plane_api.services.PublicationRepository", return_value=pub_repo):
            svc = PublishingService(db)
            result = svc.update_publication("pub-1", PublicationUpdate(status="PUBLISHED", platform_id="plat-123"))
        assert result.status == "PUBLISHED"
        assert result.published_at is not None

    def test_channel_analytics(self):
        db = MagicMock()
        pub_repo = MagicMock()
        perf_repo = MagicMock()
        pub_repo.list.return_value = ([
            make_pub_mock(id="pub-1", channel_id="ch-1"),
            make_pub_mock(id="pub-2", channel_id="ch-1"),
        ], 2)
        perf_repo.get_by_publication.side_effect = [
            SimpleNamespace(views=1000, watch_time_seconds=5000, subscriber_gain=10, ctr=0.05, engagement_rate=0.08),
            SimpleNamespace(views=2000, watch_time_seconds=10000, subscriber_gain=20, ctr=0.06, engagement_rate=0.09),
        ]

        with patch("control_plane_api.services.PublicationRepository", return_value=pub_repo), \
             patch("control_plane_api.services.PerformanceRepository", return_value=perf_repo):
            svc = PublishingService(db)
            result = svc.get_channel_analytics("ch-1")
        assert result.total_views == 3000
        assert result.total_watch_time_seconds == 15000
        assert result.total_subscriber_gain == 30
        assert result.publication_count == 2
        assert result.avg_ctr == 0.055
        assert result.avg_engagement_rate == 0.085


class TestExperimentService:
    def test_invalid_status_transition(self):
        db = MagicMock()
        repo = MagicMock()
        repo.get.return_value = make_exp_mock(status="RUNNING")

        with patch("control_plane_api.services.ExperimentRepository", return_value=repo):
            svc = ExperimentService(db)
            with pytest.raises(ValueError, match="Invalid status transition"):
                svc.update("exp-1", ExperimentUpdate(status="DRAFT"))

    def test_valid_status_transition(self):
        db = MagicMock()
        repo = MagicMock()
        repo.get.return_value = make_exp_mock(status="DRAFT")
        repo.update.return_value = make_exp_mock(status="RUNNING", start_time=datetime.utcnow())

        with patch("control_plane_api.services.ExperimentRepository", return_value=repo):
            svc = ExperimentService(db)
            result = svc.update("exp-1", ExperimentUpdate(status="RUNNING"))
        assert result.status == "RUNNING"


class TestPolicyService:
    def test_policy_version_increment(self):
        db = MagicMock()
        repo = MagicMock()
        repo.get.return_value = make_policy_mock(version=1)
        repo.update.return_value = make_policy_mock(rules={"new": "rule"}, version=2)

        with patch("control_plane_api.services.PolicyRepository", return_value=repo):
            svc = PolicyService(db)
            result = svc.update("pol-1", PolicyUpdate(rules={"new": "rule"}))
        assert result.version == 2


class TestDecisionService:
    def test_override_decision(self):
        db = MagicMock()
        repo = MagicMock()
        repo.get.return_value = make_decision_mock(override_status="PENDING")
        repo.override.return_value = make_decision_mock(override_status="REJECTED", override_by="user-1", override_at=datetime.utcnow())
        repo.update.return_value = make_decision_mock(
            override_status="REJECTED", override_by="user-1", override_at=datetime.utcnow(),
            reasoning=[{"action": "human_override", "by": "user-1", "status": "REJECTED"}],
        )

        with patch("control_plane_api.services.DecisionLogRepository", return_value=repo):
            svc = DecisionService(db)
            result = svc.override("dec-1", "user-1", DecisionLogOverride(override_status="REJECTED", override_reason="Safety concern"))
        assert result.override_status == "REJECTED"
        assert result.override_by == "user-1"

    def test_override_already_overridden(self):
        db = MagicMock()
        repo = MagicMock()
        repo.get.return_value = make_decision_mock(override_status="REJECTED", override_by="user-1", override_at=datetime.utcnow())

        with patch("control_plane_api.services.DecisionLogRepository", return_value=repo):
            svc = DecisionService(db)
            with pytest.raises(ValueError, match="Decision already overridden"):
                svc.override("dec-1", "user-2", DecisionLogOverride(override_status="APPROVED"))


class TestSchemas:
    def test_channel_create_validation(self):
        with pytest.raises(Exception):
            ChannelCreate(tenant_id="t-1", name="", platform="youtube")

    def test_pagination_params_defaults(self):
        p = PaginationParams()
        assert p.limit == 100
        assert p.offset == 0

    def test_pagination_params_max_limit(self):
        with pytest.raises(Exception):
            PaginationParams(limit=1001)
