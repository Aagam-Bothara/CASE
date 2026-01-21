# evaluator/app.py
import os

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Literal, Optional
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from orchestrator import CaseEngine
from evaluator import pricing

app = FastAPI(title="CASE Optimizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_engine():
    return CaseEngine("rules.clp")


class Workload(BaseModel):
    # Core workload characteristics
    workload_type: Literal["web", "api", "batch", "stream", "analytics"]
    traffic_rps: int = 0
    variability: Literal["steady", "spiky"] = "steady"

    # Performance requirements
    latency: int = 150  # Target p95 latency in ms
    p95_target_ms: float = 0.0  # Alternative field (0 = no constraint)

    # Compute requirements
    avg_exec_ms: float = 100.0
    mem_gb: float = 0.5
    cpu_vcpu: float = 0.25

    # Statefulness
    statefulness: Literal["stateless", "stateful"] = "stateless"

    # Storage/persistence requirements
    persistence_model: Literal["none", "sql", "nosql", "object", "cache"] = "none"
    storage_gb_hot: float = 0.0
    storage_gb_cold: float = 0.0
    data_size_gb: float = 0.0

    # Data access patterns
    read_qps: float = 0.0
    write_qps: float = 0.0

    # Network
    egress_gb_month: float = 0.0

    # Compliance & SLA
    compliance: Literal["none", "hipaa", "pci-dss", "gdpr", "sox"] = "none"
    sla_tier: Literal["standard", "high", "critical"] = "standard"
    multi_region_needed: Literal["yes", "no"] = "no"

    # Cloud preferences
    region: str = "us-east-1"
    vendor_preference: Literal["none", "aws", "azure", "gcp"] = "none"

    # Policy constraints
    budget_monthly: float = 0.0  # Max monthly cost (0 = no limit)
    vendor_exclude: List[str] = []  # Vendors to exclude (e.g., ["gcp"])


class PlanResponse(BaseModel):
    bundles: List[Dict]
    evals: List[Dict]
    top3: List[Dict]
    winner: Optional[Dict]
    winner_reason: Optional[Dict]
    why: List[str]
    constraints: List[Dict]
    assumptions: Dict


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/plan", response_model=PlanResponse)
async def auto_plan(workload: Workload, engine: CaseEngine = Depends(get_engine)):
    c = engine.candidates(workload.model_dump())
    evals = await pricing.eval_bundles(workload.model_dump(), c["bundles"])
    result = engine.run_with_evals(workload.model_dump(), evals)

    return {
        "bundles": c["bundles"],
        "evals": evals,
        "top3": result["top3"],
        "winner": result["winner"],
        "winner_reason": result["winner_reason"],
        "why": result["why"],
        "constraints": result["constraints"],
        "assumptions": result["assumptions"]
    }


@app.get("/api/pricing/cache")
def get_pricing_cache():
    return {"stats": pricing.cache_stats()}


@app.post("/api/pricing/cache/clear")
def clear_pricing_cache():
    pricing.cache_clear()
    return {"status": "cleared"}


class SimulateRequest(BaseModel):
    baseline: Workload
    overrides: List[Dict]  # List of override dicts like {"traffic_rps": 1600, "label": "2x Traffic"}


class SimulateResponse(BaseModel):
    baseline_result: Dict
    scenarios: List[Dict]


def calculate_deltas(baseline_top3: List[Dict], scenario_top3: List[Dict], scenario_label: str) -> Dict:
    """Calculate deltas between baseline and scenario results"""
    # Build lookup maps by (vendor, compute, storage)
    baseline_map = {}
    for i, plan in enumerate(baseline_top3):
        key = (plan["vendor"], plan["compute_service"], plan["storage_service"])
        baseline_map[key] = {"rank": i + 1, "plan": plan}

    scenario_map = {}
    for i, plan in enumerate(scenario_top3):
        key = (plan["vendor"], plan["compute_service"], plan["storage_service"])
        scenario_map[key] = {"rank": i + 1, "plan": plan}

    # Calculate deltas for each scenario plan
    deltas = []
    for i, plan in enumerate(scenario_top3):
        key = (plan["vendor"], plan["compute_service"], plan["storage_service"])
        baseline_entry = baseline_map.get(key)

        if baseline_entry:
            baseline_plan = baseline_entry["plan"]
            cost_delta = plan["monthly_cost"] - baseline_plan["monthly_cost"]
            cost_delta_pct = (cost_delta / baseline_plan["monthly_cost"] * 100) if baseline_plan["monthly_cost"] > 0 else 0
            rank_delta = baseline_entry["rank"] - (i + 1)  # Positive means improved
            p95_delta = plan["p95_ms"] - baseline_plan["p95_ms"]

            deltas.append({
                "rank": i + 1,
                "vendor": plan["vendor"],
                "compute_service": plan["compute_service"],
                "storage_service": plan["storage_service"],
                "monthly_cost": plan["monthly_cost"],
                "cost_delta": round(cost_delta, 2),
                "cost_delta_pct": round(cost_delta_pct, 2),
                "rank_delta": rank_delta,
                "baseline_rank": baseline_entry["rank"],
                "p95_ms": plan["p95_ms"],
                "p95_delta": round(p95_delta, 2),
                "score": plan["score_breakdown"]["composite"],
                "score_delta": round(plan["score_breakdown"]["composite"] - baseline_plan["score_breakdown"]["composite"], 2),
                "feasible": plan.get("feasible", "yes"),
                "status": "improved" if rank_delta > 0 else "declined" if rank_delta < 0 else "unchanged"
            })
        else:
            # New option not in baseline
            deltas.append({
                "rank": i + 1,
                "vendor": plan["vendor"],
                "compute_service": plan["compute_service"],
                "storage_service": plan["storage_service"],
                "monthly_cost": plan["monthly_cost"],
                "cost_delta": None,
                "cost_delta_pct": None,
                "rank_delta": None,
                "baseline_rank": None,
                "p95_ms": plan["p95_ms"],
                "p95_delta": None,
                "score": plan["score_breakdown"]["composite"],
                "score_delta": None,
                "feasible": plan.get("feasible", "yes"),
                "status": "new"
            })

    return {
        "label": scenario_label,
        "deltas": deltas
    }


@app.post("/api/simulate", response_model=SimulateResponse)
async def simulate(request: SimulateRequest, engine: CaseEngine = Depends(get_engine)):
    """
    What-if simulator: Compare baseline workload against multiple scenarios
    """
    # Run baseline
    baseline_dict = request.baseline.model_dump()
    c_baseline = engine.candidates(baseline_dict)
    evals_baseline = await pricing.eval_bundles(baseline_dict, c_baseline["bundles"])
    result_baseline = engine.run_with_evals(baseline_dict, evals_baseline)

    # Run each scenario
    scenarios = []
    for override in request.overrides:
        # Extract label and merge baseline with overrides (excluding label)
        scenario_label = override.get("label", "Scenario")
        override_without_label = {k: v for k, v in override.items() if k != "label"}
        scenario_dict = {**baseline_dict, **override_without_label}

        c_scenario = engine.candidates(scenario_dict)
        evals_scenario = await pricing.eval_bundles(scenario_dict, c_scenario["bundles"])
        result_scenario = engine.run_with_evals(scenario_dict, evals_scenario)

        # Calculate deltas
        delta_analysis = calculate_deltas(result_baseline["top3"], result_scenario["top3"], scenario_label)

        scenarios.append({
            "label": scenario_label,
            "workload_changes": override_without_label,
            "winner": result_scenario["winner"],
            "top3": result_scenario["top3"],
            "delta_analysis": delta_analysis,
            "constraints": result_scenario["constraints"]
        })

    return {
        "baseline_result": {
            "winner": result_baseline["winner"],
            "top3": result_baseline["top3"],
            "constraints": result_baseline["constraints"],
            "assumptions": result_baseline["assumptions"]
        },
        "scenarios": scenarios
    }
