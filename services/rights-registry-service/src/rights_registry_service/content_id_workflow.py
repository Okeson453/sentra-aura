"""Content ID workflow automation.

Automates the post-publish rights lifecycle: claim detection, assessment, dispute filing, and remediation.
"""
from __future__ import annotations

import logging
from typing import Any

from rights_registry_service.registry import RightsRegistry

logger = logging.getLogger(__name__)


class ContentIDWorkflow:
    """Automated workflow for Content ID and DMCA lifecycle management."""

    def __init__(self, registry: RightsRegistry | None = None) -> None:
        self.registry = registry or RightsRegistry()
        logger.info("ContentIDWorkflow initialized")

    def handle_claim_notification(
        self,
        asset_id: str,
        claim_type: str,
        claimant: str,
        claim_details: dict[str, Any],
    ) -> dict[str, Any]:
        """Process an incoming Content ID claim or DMCA notification.

        1. Record the claim in the registry.
        2. Assess severity and auto-dispute eligibility.
        3. If eligible, file an automated dispute.
        4. If strike (not just claim), freeze publishing pipeline.

        Returns:
            Workflow result with actions taken.
        """
        logger.warning("Claim notification for %s: %s from %s", asset_id, claim_type, claimant)

        # Step 1: Record claim
        claim = self.registry.add_claim(asset_id, claim_type, claimant, claim_details)

        # Step 2: Assess
        asset = self.registry.get_asset(asset_id)
        auto_dispute_eligible = False
        freeze_pipeline = False

        if claim_type == "content_id_claim":
            # Check if asset has valid license
            if asset and asset.get("license_type") in ("original", "licensed", "stock"):
                auto_dispute_eligible = True
        elif claim_type == "dmca_strike":
            freeze_pipeline = True
            # Never auto-dispute strikes — always escalate to human
            auto_dispute_eligible = False

        # Step 3: Auto-dispute if eligible
        dispute_result = None
        if auto_dispute_eligible:
            dispute_result = self.registry.file_dispute(
                asset_id=asset_id,
                claim_id=claim["claim_id"],
                dispute_basis=f"Asset registered with license_type={asset['license_type']}",
                evidence={
                    "license_source": asset.get("license_source"),
                    "registered_at": asset.get("registered_at"),
                    "fingerprint": asset.get("fingerprint"),
                },
            )

        return {
            "asset_id": asset_id,
            "claim_id": claim["claim_id"],
            "claim_type": claim_type,
            "auto_dispute_filed": auto_dispute_eligible,
            "dispute_result": dispute_result,
            "freeze_pipeline": freeze_pipeline,
            "escalate_to_human": freeze_pipeline or not auto_dispute_eligible,
        }

    def remediate_claimed_segment(
        self,
        asset_id: str,
        claim_id: str,
        remediation_action: str,
        replacement_asset_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute remediation for a claimed asset segment.

        Actions: mute, replace, trim, or dispute.
        """
        logger.info("Remediating %s: action=%s", asset_id, remediation_action)
        return {
            "asset_id": asset_id,
            "claim_id": claim_id,
            "remediation_action": remediation_action,
            "replacement_asset_id": replacement_asset_id,
            "status": "remediation_queued",
        }
