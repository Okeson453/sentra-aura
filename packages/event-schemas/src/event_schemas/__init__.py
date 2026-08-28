"""SentraAura event schema registry client.

Provides typed access to canonical event schemas.
"""
from event_schemas.registry_client import SchemaRegistryClient
from event_schemas.v1 import TrendDetected, ScriptDrafted, VideoRendered, ClipCandidateCreated, PublicationPublished

__all__ = [
    "SchemaRegistryClient",
    "TrendDetected",
    "ScriptDrafted",
    "VideoRendered",
    "ClipCandidateCreated",
    "PublicationPublished",
]
