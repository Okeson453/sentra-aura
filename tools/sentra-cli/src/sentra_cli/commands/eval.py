"""Agent evaluation and benchmarking commands."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(help="Agent evaluation and benchmarking")


@app.command("run")
def run_eval(
    agent_name: str = typer.Argument(..., help="Agent to evaluate"),
    dataset: str = typer.Option(..., "--dataset", help="Evaluation dataset path (JSONL)"),
    output: str = typer.Option("eval_results.json", "--output", help="Output file path"),
    iterations: int = typer.Option(1, "--iterations", help="Number of iterations per sample"),
    timeout: int = typer.Option(300, "--timeout", help="Per-sample timeout in seconds"),
) -> None:
    """Run offline evaluation for an agent against a dataset.

    Loads a JSONL dataset where each line is {"input": ..., "expected": ...},
    invokes the agent for each sample, and writes structured results.
    """
    dataset_path = Path(dataset)
    if not dataset_path.exists():
        typer.echo(f"Error: dataset not found: {dataset}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Loading dataset: {dataset}")
    samples: list[dict[str, Any]] = []
    with open(dataset_path) as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    typer.echo(f"Loaded {len(samples)} samples for agent '{agent_name}'")
    typer.echo(f"Running {iterations} iteration(s) per sample, timeout={timeout}s")

    results: list[dict[str, Any]] = []
    passed = 0
    failed = 0

    for idx, sample in enumerate(samples):
        typer.echo(f"  [{idx+1}/{len(samples)}] Evaluating...", nl=False)
        # Placeholder: in production, this calls the agent-runtime service
        result = {
            "sample_id": idx,
            "input": sample.get("input"),
            "expected": sample.get("expected"),
            "actual": "mock-actual-output",
            "match": False,
            "latency_ms": 150,
            "tokens_used": 250,
            "cost_usd": 0.002,
        }
        if result["match"]:
            passed += 1
        else:
            failed += 1
        results.append(result)
        typer.echo(" done")

    summary = {
        "agent": agent_name,
        "dataset": dataset,
        "total_samples": len(samples),
        "iterations": iterations,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / len(samples), 4) if samples else 0.0,
        "results": results,
    }

    with open(output, "w") as f:
        json.dump(summary, f, indent=2)

    typer.echo(f"Evaluation complete. Pass rate: {summary['pass_rate']:.2%}")
    typer.echo(f"Results written to: {output}")


@app.command("benchmark")
def benchmark(
    agent_name: str = typer.Argument(..., help="Agent to benchmark"),
    iterations: int = typer.Option(10, "--iterations", help="Number of iterations"),
    concurrency: int = typer.Option(1, "--concurrency", help="Concurrent requests"),
) -> None:
    """Benchmark agent performance: latency, throughput, token usage, cost."""
    typer.echo(f"Benchmarking agent '{agent_name}'")
    typer.echo(f"Iterations: {iterations}, Concurrency: {concurrency}")

    latencies: list[float] = []
    tokens: list[int] = []
    costs: list[float] = []

    for i in range(iterations):
        # Placeholder: real implementation calls agent-runtime
        latencies.append(120.0 + i * 5)
        tokens.append(200 + i * 10)
        costs.append(0.0015 + i * 0.0001)

    avg_latency = sum(latencies) / len(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
    avg_tokens = sum(tokens) / len(tokens)
    total_cost = sum(costs)

    typer.echo("--- Benchmark Results ---")
    typer.echo(f"Avg latency: {avg_latency:.1f}ms")
    typer.echo(f"P95 latency: {p95_latency:.1f}ms")
    typer.echo(f"Avg tokens: {avg_tokens:.0f}")
    typer.echo(f"Total cost: ${total_cost:.4f}")
    typer.echo("-------------------------")


@app.command("compare")
def compare_evals(
    baseline: str = typer.Argument(..., help="Baseline eval result JSON"),
    candidate: str = typer.Argument(..., help="Candidate eval result JSON"),
) -> None:
    """Compare two evaluation runs and report deltas."""
    baseline_path = Path(baseline)
    candidate_path = Path(candidate)

    if not baseline_path.exists():
        typer.echo(f"Error: baseline not found: {baseline}", err=True)
        raise typer.Exit(1)
    if not candidate_path.exists():
        typer.echo(f"Error: candidate not found: {candidate}", err=True)
        raise typer.Exit(1)

    with open(baseline_path) as f:
        base = json.load(f)
    with open(candidate_path) as f:
        cand = json.load(f)

    base_rate = base.get("pass_rate", 0.0)
    cand_rate = cand.get("pass_rate", 0.0)
    delta = cand_rate - base_rate

    typer.echo("--- Evaluation Comparison ---")
    typer.echo(f"Baseline:  {base_rate:.2%} ({base.get('passed')}/{base.get('total_samples')})")
    typer.echo(f"Candidate: {cand_rate:.2%} ({cand.get('passed')}/{cand.get('total_samples')})")
    typer.echo(f"Delta:     {delta:+.2%}")
    if delta > 0:
        typer.echo("Result: IMPROVEMENT")
    elif delta < 0:
        typer.echo("Result: REGRESSION")
    else:
        typer.echo("Result: NO CHANGE")
    typer.echo("-----------------------------")
