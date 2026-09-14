"""Proof-of-concept / regression probe: tenant isolation on the Control Plane API.

Run against a checkout to demonstrate that the cross-tenant access paths
found in the audit are closed:

  D1  a caller cannot create a channel owned by a tenant other than its own
  D2  a caller cannot read another tenant's channel
  D3  a caller cannot mutate or delete another tenant's channel, and an
      unfiltered listing returns only the caller's own tenant

Tenant identity is carried in the *verified* JWT, so each principal below is
minted with its own tenant claim.

Exit code 0 == isolation holds; 1 == at least one violation.
"""
from __future__ import annotations

import sys

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from control_plane_api.main import create_app
from control_plane_api.models import Base
from control_plane_api.api.dependencies import get_db, get_db_session
from control_plane_api.config import get_settings
from sentinel_security import create_service_token

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def _override():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app = create_app()
app.dependency_overrides[get_db] = _override
app.dependency_overrides[get_db_session] = _override
client = TestClient(app)

secret = get_settings().jwt_secret


def _hdr(tenant: str | None) -> dict[str, str]:
    tok = create_service_token(
        "probe", ["admin"], secret=secret, ttl_seconds=3600, tenant_id=tenant
    )
    return {"Authorization": f"Bearer {tok}"}

hdr_a = _hdr("tenant-a")
hdr_b = _hdr("tenant-b")

results: list[tuple[str, str, str]] = []


def record(tag: str, ok: bool, detail: str) -> None:
    verdict = "SECURE" if ok else "VIOLATION"
    results.append((tag, verdict, detail))
    print(f"[{verdict}] {tag}\n    {detail}")


# --- control: auth is enforced --------------------------------------------
r = client.get("/api/v1/channels")
record(
    "CONTROL: unauthenticated GET /api/v1/channels",
    r.status_code == 401,
    f"status={r.status_code} (expected 401)",
)

# --- D1: cannot create a channel owned by another tenant -------------------
r = client.post(
    "/api/v1/channels",
    headers=hdr_a,
    json={"name": "A-news", "platform": "youtube", "tenant_id": "tenant-b"},
)
record(
    "D1: 'tenant-a' principal creates a channel as tenant-b",
    r.status_code == 403,
    f"status={r.status_code} (expected 403)",
)

# legitimately create one inside our own tenant
r = client.post(
    "/api/v1/channels",
    headers=hdr_a,
    json={"name": "A-news", "platform": "youtube", "tenant_id": "tenant-a"},
)
if r.status_code != 201:
    print("setup failed:", r.status_code, r.text)
    sys.exit(2)
channel_a = r.json()["id"]

r = client.post(
    "/api/v1/channels",
    headers=hdr_b,
    json={"name": "B-music", "platform": "youtube", "tenant_id": "tenant-b"},
)
channel_b = r.json()["id"]

# --- D2: cross-tenant read -------------------------------------------------
r = client.get(f"/api/v1/channels/{channel_a}", headers=hdr_b)
record(
    "D2: 'tenant-b' reads tenant-a's channel",
    r.status_code == 404,
    f"status={r.status_code} (expected 404)",
)

# --- D3a: listing cannot leak other tenants -------------------------------
r = client.get("/api/v1/channels", headers=hdr_b)
seen = sorted({c.get("tenant_id") for c in r.json().get("items", [])})
record(
    "D3a: unfiltered listing is scoped to the caller's tenant",
    seen == ["tenant-b"],
    f"tenants visible to tenant-b: {seen} (expected ['tenant-b'])",
)

# --- D3b: cross-tenant mutate --------------------------------------------
r = client.patch(
    f"/api/v1/channels/{channel_a}",
    headers=hdr_b,
    json={"name": "HIJACKED"},
)
record(
    "D3b: 'tenant-b' PATCHes tenant-a's channel",
    r.status_code == 404,
    f"status={r.status_code} (expected 404)",
)

# --- D3c: cross-tenant delete --------------------------------------------
r = client.delete(f"/api/v1/channels/{channel_b}", headers=hdr_a)
record(
    "D3c: 'tenant-a' DELETEs tenant-b's channel",
    r.status_code == 404,
    f"status={r.status_code} (expected 404)",
)

# --- D4: legacy header cannot widen scope --------------------------------
widened = dict(hdr_b)
widened["X-Tenant-ID"] = "tenant-a"
r = client.get(f"/api/v1/channels/{channel_a}", headers=widened)
record(
    "D4: X-Tenant-ID header does not widen scope",
    r.status_code == 404,
    f"status={r.status_code} (expected 404)",
)

print("\n" + "=" * 72)
print("SUMMARY")
print("=" * 72)
for tag, verdict, _ in results:
    print(f"  {verdict:10} {tag}")
viol = sum(1 for _, v, _ in results if v == "VIOLATION")
print(f"\n{viol} isolation violation(s); {len(results) - viol} check(s) secure.")
sys.exit(1 if viol else 0)
