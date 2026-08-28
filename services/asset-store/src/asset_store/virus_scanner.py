"""Virus scanning for SentraAura Asset Store.

Supports ClamAV integration, byte-signature detection, and async scanning.
Matches Backend Spec §13.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    clean: bool
    threat: str | None = None
    scanner: str = ""
    signature: str = ""
    details: dict[str, Any] | None = None


class VirusScanner:
    """Abstract virus scanner interface."""

    async def scan(self, data: bytes, filename: str = "") -> ScanResult:
        raise NotImplementedError


class ClamAVScanner(VirusScanner):
    """ClamAV-based virus scanner using clamd async socket."""

    def __init__(self, host: str = "localhost", port: int = 3310, timeout: float = 30.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    async def scan(self, data: bytes, filename: str = "") -> ScanResult:
        try:
            import clamd
            cd = clamd.ClamdAsyncNetworkSocket(self.host, self.port)
            result = await cd.scan_stream(data)
            if result and "stream" in result:
                status, signature = result["stream"]
                if status == "FOUND":
                    return ScanResult(clean=False, threat=signature, scanner="clamav", signature=signature)
            return ScanResult(clean=True, scanner="clamav")
        except ImportError:
            logger.warning("clamd not installed, falling back to signature scanner")
            return await SignatureScanner().scan(data, filename)
        except Exception as exc:
            logger.error(f"ClamAV scan failed: {exc}")
            return ScanResult(clean=False, threat="SCAN_ERROR", scanner="clamav", details={"error": str(exc)})


class SignatureScanner(VirusScanner):
    """Lightweight byte-signature scanner for common malware patterns."""

    # Known malicious signatures (hex patterns)
    SIGNATURES = {
        "eicar_test": b"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*",
        "pdf_exploit_js": b"/JS",
    }

    async def scan(self, data: bytes, filename: str = "") -> ScanResult:
        for name, signature in self.SIGNATURES.items():
            if signature in data:
                return ScanResult(clean=False, threat=name, scanner="signature", signature=name)
        # Check for suspicious patterns
        if filename.lower().endswith((".exe", ".dll", ".bat", ".cmd", ".sh")) and b"MZ" in data[:2]:
            return ScanResult(clean=False, threat="executable_in_disguise", scanner="signature")
        return ScanResult(clean=True, scanner="signature")


class AsyncScanQueue:
    """Queue for async virus scanning with result callbacks."""

    def __init__(self, scanner: VirusScanner, max_concurrent: int = 5) -> None:
        self.scanner = scanner
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.results: dict[str, ScanResult] = {}

    async def scan_batch(self, items: list[tuple[str, bytes, str]]) -> dict[str, ScanResult]:
        """Scan a batch of items concurrently."""
        tasks = [self._scan_one(asset_id, data, filename) for asset_id, data, filename in items]
        await asyncio.gather(*tasks, return_exceptions=True)
        return self.results

    async def _scan_one(self, asset_id: str, data: bytes, filename: str) -> None:
        async with self.semaphore:
            result = await self.scanner.scan(data, filename)
            self.results[asset_id] = result
