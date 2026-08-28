"""Rights and provenance registry.

Manages content ID fingerprints, license records, and asset provenance for DMCA/Content ID defense.
"""
from __future__ import annotations

import logging
import hashlib
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class RightsRegistry:
    """Central registry for content rights, licenses, and provenance."""

    def __init__(self, store: dict[str, Any] | None = None) -> None:
        self._store = store or {}
        logger.info("RightsRegistry initialized")

    def register_asset(
        self,
        asset_id: str,
        asset_type: str,
        fingerprint: str,
        license_type: str,
        license_source: str,
        owner_channel_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register an asset with its rights and provenance information.

        Args:
            asset_id: Unique asset identifier.
            asset_type: Type of asset (video, audio, image, etc.).
            fingerprint: Perceptual hash or audio fingerprint.
            license_type: Type of license (original, stock, cc, fair_use, etc.).
            license_source: Source of the license (provider, url, contract_id).
            owner_channel_id: Channel that owns or licensed the asset.
            metadata: Additional provenance metadata.

        Returns:
            Registration record.
        """
        record = {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "fingerprint": fingerprint,
            "license_type": license_type,
            "license_source": license_source,
            "owner_channel_id": owner_channel_id,
            "metadata": metadata or {},
            "registered_at": datetime.utcnow().isoformat(),
            "claims": [],
            "disputes": [],
        }
        self._store[asset_id] = record
        logger.info("Registered asset %s with license %s", asset_id, license_type)
        return record

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        """Retrieve a registered asset record."""
        return self._store.get(asset_id)

    def add_claim(
        self,
        asset_id: str,
        claim_type: str,
        claimant: str,
        claim_details: dict[str, Any],
    ) -> dict[str, Any]:
        """Record a Content ID claim or DMCA strike against an asset."""
        asset = self._store.get(asset_id)
        if not asset:
            raise KeyError(f"Asset not found: {asset_id}")
        claim = {
            "claim_id": f"clm_{hashlib.sha256(f'{asset_id}{claimant}{datetime.utcnow()}'.encode()).hexdigest()[:16]}",
            "claim_type": claim_type,
            "claimant": claimant,
            "details": claim_details,
            "status": "open",
            "created_at": datetime.utcnow().isoformat(),
        }
        asset["claims"].append(claim)
        logger.warning("Claim added to %s: %s by %s", asset_id, claim_type, claimant)
        return claim

    def file_dispute(
        self,
        asset_id: str,
        claim_id: str,
        dispute_basis: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        """File a dispute against a claim."""
        asset = self._store.get(asset_id)
        if not asset:
            raise KeyError(f"Asset not found: {asset_id}")
        dispute = {
            "dispute_id": f"dsp_{hashlib.sha256(f'{claim_id}{dispute_basis}'.encode()).hexdigest()[:16]}",
            "claim_id": claim_id,
            "dispute_basis": dispute_basis,
            "evidence": evidence,
            "status": "filed",
            "filed_at": datetime.utcnow().isoformat(),
        }
        asset["disputes"].append(dispute)
        logger.info("Dispute filed for %s: %s", asset_id, dispute_basis)
        return dispute

    def resolve_claim(self, asset_id: str, claim_id: str, resolution: str) -> dict[str, Any]:
        """Resolve a claim with a given outcome."""
        asset = self._store.get(asset_id)
        if not asset:
            raise KeyError(f"Asset not found: {asset_id}")
        for claim in asset["claims"]:
            if claim["claim_id"] == claim_id:
                claim["status"] = resolution
                claim["resolved_at"] = datetime.utcnow().isoformat()
                logger.info("Claim %s resolved: %s", claim_id, resolution)
                return claim
        raise KeyError(f"Claim not found: {claim_id}")

    def compute_fingerprint(self, file_path: str, method: str = "perceptual_hash") -> str:
        """Compute a content fingerprint for an asset file."""
        logger.info("Computing %s fingerprint for %s", method, file_path)
        # Production: use imagehash, chromaprint, or perceptual hashing library
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:32]
