"""Tests for agent contracts."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from agent_contracts.envelope import AgentMessage, PriorityLevel, AgentMessageState
from agent_contracts.budget import CostBudget, BudgetStatus
from agent_contracts.schemas.intelligence import TrendSignal, OpportunityScore
from agent_contracts.schemas.creative import ResearchBundle, Script
from agent_contracts.schemas.production import LongFormVideo
from agent_contracts.schemas.clipping import ClipCandidate, Clip
from agent_contracts.schemas.distribution import Publication, SEOMetadata
from agent_contracts.schemas.operations import PerformanceRecord, DecisionLog


def test_agent_message_defaults():
    msg = AgentMessage(agent_type="test", task_type="draft")
    assert isinstance(msg.message_id, UUID)
    assert msg.priority == PriorityLevel.NORMAL
    assert msg.agent_type == "test"


def test_agent_message_serde():
    msg = AgentMessage(agent_type="test", task_type="draft", payload={"key": "val"})
    d = msg.to_dict()
    msg2 = AgentMessage.from_dict(d)
    assert msg2.agent_type == "test"
    assert msg2.payload == {"key": "val"}


def test_cost_budget_spend():
    budget = CostBudget(total_budget_usd=100.0)
    budget.spend(30.0)
    assert budget.spent_usd == 30.0
    assert budget.remaining_usd == 70.0


def test_cost_budget_exhausted():
    budget = CostBudget(total_budget_usd=10.0)
    budget.spend(15.0)
    assert budget.status == BudgetStatus.EXHAUSTED
    assert budget.remaining_usd == 0.0


def test_trend_signal():
    ts = TrendSignal(signal_id="S1", channel_id="C1", topic="AI")
    assert ts.demand_score == 0.0


def test_research_bundle():
    rb = ResearchBundle(bundle_id="B1", topic_id="T1")
    assert rb.status == "PENDING"


def test_script():
    s = Script(script_id="SCR-1", topic_id="T1", title="Test")
    assert s.status == "DRAFT"


def test_longform_video():
    lf = LongFormVideo(video_id="LF-1", channel_id="C1", topic_id="T1")
    assert lf.status == "RENDERING"


def test_clip_candidate():
    cc = ClipCandidate(candidate_id="CC-1", source_video_id="LF-1")
    assert cc.status == "CANDIDATE"


def test_clip():
    c = Clip(clip_id="CL-1", source_video_id="LF-1")
    assert c.status == "READY_TO_PUBLISH"


def test_publication():
    p = Publication(publication_id="PUB-1", channel_id="C1")
    assert p.status == "SCHEDULED"


def test_seo_metadata():
    seo = SEOMetadata(metadata_id="SEO-1", video_id="LF-1")
    assert seo.language == "en"


def test_performance_record():
    pr = PerformanceRecord(record_id="PR-1", publication_id="PUB-1", channel_id="C1")
    assert pr.views == 0


def test_decision_log():
    dl = DecisionLog(decision_id="D1", agent_type="TestAgent", decision="approve")
    assert dl.human_override_possible is True
