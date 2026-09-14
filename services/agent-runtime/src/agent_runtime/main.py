"""FastAPI application for the Agent Runtime.

The runtime is a deployable service that hosts all 30 specialized agents. This
module provides the production HTTP surface the orchestrator dispatches to:

* ``POST /v1/execute``       - execute one agent task (Orchestrator activities)
* ``POST /v1/draft-script``  - scripting-agent convenience path
* ``POST /api/v1/invoke``    - the committed OpenAPI contract operation
* ``GET  /v1/invoke/{id}``   - invocation status
* ``POST /v1/invoke/{id}/cancel`` - cancel an invocation
* ``GET  /api/v1/agents``    - agent catalog
* ``GET  /health`` / ``GET /ready``

Behaviour that matters for production correctness:

* An unknown ``agent_type`` is a **400**, never a silent success.
* An agent failure propagates as a non-2xx so Temporal retries engage; the
  runtime never converts a dependency failure into a reported success.
* Publishing / community-engagement agents require a granted human approval;
  the runtime enforces that gate rather than trusting the caller.
* Every invocation is checkpointed to durable storage when a DSN is configured.
* ``/ready`` fails when a required dependency (catalog, durable store) is broken.
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from agent_contracts.budget import CostBudget
from agent_contracts.envelope import AgentMessage
from sentinel_exceptions import AuthenticationError
from sentinel_security import authenticate_request

from agent_runtime import catalog
from agent_runtime.approval_gate import ApprovalGate, ApprovalScope
from agent_runtime.checkpoint_store import CheckpointStore
from agent_runtime.config import AgentRuntimeConfig, config as default_config
from agent_runtime.envelope import AgentMessageEnvelope

logger = logging.getLogger(__name__)

AGENT_INVOCATIONS = Counter(
    "agent_runtime_invocations_total",
    "Agent invocations by agent type and outcome",
    ["agent_type", "outcome"],
)
AGENT_DURATION = Histogram(
    "agent_runtime_invocation_seconds",
    "Agent invocation wall-clock duration",
    ["agent_type"],
)


class Settings(AgentRuntimeConfig):
    """Runtime settings, extended with the durable-state DSN.

    ``jwt_secret`` flows in from the environment (JWT_SECRET) so the HTTP
    surface can validate service tokens issued by other SentraAura services.
    """

    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    require_auth: bool = True
    database_url: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_payload(task_type: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Merge the task type into the agent payload.

    Agents read ``task_type`` from the payload (the scripting agent guards on it),
    so the runtime guarantees it is present for every dispatch path.
    """
    payload = dict(inputs or {})
    payload.setdefault("task_type", task_type)
    return payload


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the agent-runtime application."""
    settings = settings or Settings()

    agents: dict[str, Any] = {}
    catalog_errors: dict[str, str] = {}
    approval_gate = ApprovalGate()
    store = CheckpointStore(settings.database_url)
    invocations: dict[str, dict[str, Any]] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal agents, catalog_errors
        logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
        logger.info(
            "agent-runtime starting environment=%s gateway=%s",
            settings.environment,
            settings.provider_gateway_url,
        )
        agents, catalog_errors = catalog.instantiate_all(
            provider_gateway_url=settings.provider_gateway_url,
            timeout_seconds=settings.default_agent_timeout_seconds,
            approval_gate=approval_gate,
        )
        logger.info("agent-runtime ready with %d/%d agents", len(agents), len(catalog.AGENT_ENTRIES))
        try:
            yield
        finally:
            await store.close()

    app = FastAPI(
        title="SentraAura Agent Runtime",
        description="Agent invocation, execution policy enforcement, tool permission checks",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ---------------------------------------------------------------- security
    async def require_auth(authorization: str | None = Header(default=None)) -> Any:
        """Validate the caller's service JWT when auth is enabled."""
        if not settings.require_auth or not settings.jwt_secret:
            return None
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        token = authorization.split(" ", 1)[1].strip()
        try:
            return authenticate_request(
                token,
                jwt_secret=settings.jwt_secret,
                jwt_algorithms=[settings.jwt_algorithm],
            )
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    # ------------------------------------------------------------ observability
    @app.get("/health")
    async def health() -> dict[str, Any]:
        agent_checks = {
            agent_type: {
                "status": "pass" if agent_type not in catalog_errors else "fail",
                **({"detail": catalog_errors[agent_type]} if agent_type in catalog_errors else {}),
            }
            for agent_type in catalog.agent_types()
        }
        degraded = bool(catalog_errors)
        return {
            "status": "degraded" if degraded else "healthy",
            "timestamp": _now_iso(),
            "version": app.version,
            "checks": {
                "catalog": {
                    "status": "degraded" if degraded else "pass",
                    "agents_total": len(catalog.AGENT_ENTRIES),
                    "agents_loaded": len(agents),
                },
                "durable_state": {"status": "pass" if store.enabled else "warn"},
                "agents": agent_checks,
            },
        }

    @app.get("/ready")
    async def ready() -> JSONResponse:
        checks: dict[str, Any] = {}
        ok = True

        if not agents:
            checks["agents"] = {"status": "fail", "detail": "no agents initialised"}
            ok = False
        else:
            checks["agents"] = {"status": "pass", "loaded": len(agents)}

        # A broken catalog is a readiness failure, not a silent degradation:
        # the orchestrator dispatches by agent_type and would otherwise 500.
        failed = {k: v for k, v in catalog_errors.items()}
        if failed:
            checks["catalog_errors"] = {"status": "fail", "detail": failed}
            ok = False

        if store.enabled:
            try:
                await store.ensure_ready()
                checks["durable_state"] = {"status": "pass"}
            except Exception as exc:  # noqa: BLE001
                checks["durable_state"] = {"status": "fail", "detail": str(exc)}
                ok = False

        localhost_gateway = settings.provider_gateway_url.startswith("http://localhost") or settings.provider_gateway_url.startswith(
            "http://127.0.0.1"
        )
        checks["provider_gateway"] = {
            "status": "warn" if localhost_gateway else "pass",
            "url": settings.provider_gateway_url,
        }

        return JSONResponse(
            status_code=200 if ok else 503,
            content={"status": "ready" if ok else "not_ready", "timestamp": _now_iso(), "checks": checks},
        )

    @app.get("/metrics")
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

    # ------------------------------------------------------- invocation helpers
    async def _dispatch(
        agent_type: str,
        task_type: str,
        inputs: dict[str, Any],
        *,
        channel_id: str | None = None,
        tenant_id: str | None = None,
        trace_id: str | None = None,
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        """Resolve, execute, checkpoint and report one agent invocation."""
        if agent_type not in agents:
            known = ", ".join(catalog.agent_types())
            detail = catalog_errors.get(agent_type, "not initialised in this runtime")
            raise HTTPException(
                status_code=400,
                detail=f"unknown or unavailable agent_type {agent_type!r}: {detail}. Supported: {known}",
            )

        invocation_id = uuid.uuid4().hex
        trace_id = trace_id or uuid.uuid4().hex
        record: dict[str, Any] = {
            "invocation_id": invocation_id,
            "status": "running",
            "agent_type": agent_type,
            "task_type": task_type,
            "started_at": _now_iso(),
        }
        invocations[invocation_id] = record

        # Documented human-approval gate for externally visible agents.
        if agent_type in catalog.PUBLISH_APPROVAL_AGENTS:
            if approval_id and approval_gate.get(approval_id) is not None:
                record["approval_id"] = approval_id
            else:
                scope = ApprovalScope(
                    agent_id=agent_type,
                    tool_name="publish",
                    action="execute",
                    scope_key=f"{channel_id or 'global'}",
                )
                if not approval_gate.has_grant(scope):
                    record["status"] = "rejected"
                    AGENT_INVOCATIONS.labels(agent_type=agent_type, outcome="approval_required").inc()
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            f"agent {agent_type} requires a granted human approval "
                            "(Architecture 11/19) for publish scope"
                        ),
                    )

        message = AgentMessage(
            agent_type=agent_type,
            task_type=task_type,
            payload=_task_payload(task_type, inputs),
            trace_id=trace_id,
            channel_id=channel_id,
            tenant_id=tenant_id,
            deadline=datetime.now(timezone.utc)
            + timedelta(seconds=settings.default_agent_timeout_seconds),
            budget=CostBudget(total_budget_usd=settings.default_budget_usd),
        )
        envelope = AgentMessageEnvelope(message=message)

        started = time.perf_counter()
        try:
            result = await agents[agent_type].run(envelope)
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            elapsed = time.perf_counter() - started
            AGENT_DURATION.labels(agent_type=agent_type).observe(elapsed)
            AGENT_INVOCATIONS.labels(agent_type=agent_type, outcome="failed").inc()
            record.update(
                {
                    "status": "failed",
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                    "completed_at": _now_iso(),
                    "duration_seconds": round(elapsed, 4),
                }
            )
            await _checkpoint(
                agent_type, phase="failed", cost=envelope.cost_accumulated_usd,
                tokens=0, payload={"task_type": task_type, "error": str(exc)},
            )
            logger.exception("agent %s failed task %s", agent_type, task_type)
            raise HTTPException(status_code=502, detail=f"agent {agent_type} failed: {exc}") from exc

        elapsed = time.perf_counter() - started
        AGENT_DURATION.labels(agent_type=agent_type).observe(elapsed)
        AGENT_INVOCATIONS.labels(agent_type=agent_type, outcome="completed").inc()
        outputs = result if isinstance(result, dict) else {"result": result}
        record.update(
            {
                "status": "completed",
                "outputs": outputs,
                "completed_at": _now_iso(),
                "duration_seconds": round(elapsed, 4),
            }
        )
        await _checkpoint(
            agent_type,
            phase="completed",
            cost=envelope.cost_accumulated_usd,
            tokens=int(getattr(envelope.message.budget, "spent_usd", 0) or 0),
            payload={"task_type": task_type, "invocation_id": invocation_id},
        )
        return {
            "invocation_id": invocation_id,
            "status": "completed",
            "agent_type": agent_type,
            "task_type": task_type,
            "outputs": outputs,
            "duration_seconds": round(elapsed, 4),
            "cost_accrued_usd": float(envelope.cost_accumulated_usd),
        }

    async def _checkpoint(
        agent_type: str, *, phase: str, cost: float, tokens: int, payload: dict[str, Any]
    ) -> None:
        """Persist a durable checkpoint; never fail the request over telemetry."""
        if not store.enabled:
            return
        try:
            await store.save(
                agent_id=agent_type,
                phase=phase,
                cost_accrued_usd=cost,
                tokens_consumed=tokens,
                payload=payload,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("checkpoint write failed for %s: %s", agent_type, exc)

    # ------------------------------------------------------------------- routes
    @app.post("/v1/execute")
    async def execute_task(body: dict[str, Any], _auth: Any = Depends(require_auth)) -> dict[str, Any]:
        """Execute one agent task. Contract consumed by orchestrator activities."""
        agent_type = body.get("agent_type")
        task_type = body.get("task_type")
        if not agent_type or not task_type:
            raise HTTPException(status_code=400, detail="agent_type and task_type are required")
        return await _dispatch(
            str(agent_type),
            str(task_type),
            dict(body.get("inputs") or {}),
            channel_id=body.get("channel_id"),
            tenant_id=body.get("tenant_id"),
            trace_id=body.get("trace_id"),
            approval_id=body.get("approval_id"),
        )

    @app.post("/v1/draft-script")
    async def draft_script(body: dict[str, Any], _auth: Any = Depends(require_auth)) -> dict[str, Any]:
        """Draft a script via the scripting agent. Consumed by the orchestrator."""
        research = dict(body.get("research") or {})
        topic = body.get("topic") or research.get("topic") or ""
        inputs = {
            "topic": topic,
            "video_title": body.get("video_title") or topic,
            "channel_name": body.get("channel_name") or "",
            "audience_profile": body.get("audience_profile") or "",
            "research": research,
            "research_bundle": research,
            "task_type": "draft_script",
        }
        result = await _dispatch(
            "scripting_agent",
            "draft_script",
            inputs,
            channel_id=body.get("channel_id"),
            tenant_id=body.get("tenant_id"),
            trace_id=body.get("trace_id"),
        )
        outputs = result.get("outputs") or {}
        content = outputs.get("content") or outputs.get("script") or outputs.get("body") or ""
        if not content and outputs:
            content = str(outputs)
        return {
            "script_id": outputs.get("script_id") or outputs.get("id") or result["invocation_id"],
            "title": outputs.get("title") or topic,
            "content": content,
            "sections": outputs.get("sections") or [],
            "invocation_id": result["invocation_id"],
            "status": "completed",
        }

    @app.post("/api/v1/invoke", status_code=202)
    async def invoke(body: dict[str, Any], _auth: Any = Depends(require_auth)) -> dict[str, Any]:
        """Committed OpenAPI operation: /invoke (contracts/openapi/agent-runtime.yaml)."""
        message = body.get("message") if isinstance(body.get("message"), dict) else body
        agent_type = message.get("agent_type")
        task_type = message.get("task_type") or "run"
        if not agent_type:
            raise HTTPException(status_code=400, detail="agent_type is required")
        result = await _dispatch(
            str(agent_type),
            str(task_type),
            dict(message.get("payload") or {}),
            channel_id=message.get("channel_id"),
            tenant_id=message.get("tenant_id"),
            trace_id=message.get("trace_id"),
            approval_id=message.get("approval_id"),
        )
        result["status"] = "completed"
        return result

    @app.get("/api/v1/invoke/{invocation_id}")
    async def invocation_status(invocation_id: str, _auth: Any = Depends(require_auth)) -> dict[str, Any]:
        record = invocations.get(invocation_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"unknown invocation {invocation_id}")
        return record

    @app.post("/api/v1/invoke/{invocation_id}/cancel")
    async def cancel_invocation(invocation_id: str, _auth: Any = Depends(require_auth)) -> dict[str, Any]:
        record = invocations.get(invocation_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"unknown invocation {invocation_id}")
        if record["status"] in {"completed", "failed"}:
            raise HTTPException(
                status_code=409,
                detail=f"invocation {invocation_id} already {record['status']}",
            )
        record["status"] = "cancelled"
        record["cancelled_at"] = _now_iso()
        return record

    @app.get("/api/v1/agents")
    async def list_agents(_auth: Any = Depends(require_auth)) -> list[dict[str, Any]]:
        return [
            {
                "agent_type": entry.agent_type,
                "version": "1.0.0",
                "status": "active" if entry.agent_type in agents else "unavailable",
                "description": f"{entry.domain} domain agent",
                "domains": [entry.domain],
            }
            for entry in catalog.AGENT_ENTRIES
        ]

    @app.get("/api/v1/agents/{agent_type}/permissions")
    async def agent_permissions(agent_type: str, _auth: Any = Depends(require_auth)) -> dict[str, Any]:
        if agent_type not in agents:
            raise HTTPException(status_code=404, detail=f"unknown agent_type {agent_type!r}")
        agent = agents[agent_type]
        return {
            "agent_type": agent_type,
            "allowed_tools": sorted(getattr(agent, "_tools", {}).keys()),
            "max_cost_per_invocation": settings.default_budget_usd,
            "requires_human_approval": agent_type in catalog.PUBLISH_APPROVAL_AGENTS,
            "autonomy_level": getattr(agent, "autonomy_level", "L2"),
        }

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "trace_id": request.headers.get("x-trace-id", ""),
            },
        )

    return app


app = create_app()
