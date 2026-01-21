# evaluator/pricing.py
import os
import asyncio
from typing import Dict, List, Optional
from .utils import CACHE
from .stub import classify_compute, classify_storage

# Provider helpers
from .providers.azure import fetch_container_apps_rates, fetch_blob_gb_month
from .providers.aws import fetch_fargate_rates, fetch_s3_gb_month
from .providers.gcp import fetch_cloud_run_rates, fetch_gcs_gb_month

REALTIME = os.getenv("REALTIME_PRICING", "false").lower() in ("true", "1", "yes")
ALLOW_FALLBACK = True

def calc_perf_heuristic(compute_type: str, exec_ms: float, variability: str) -> tuple[float, float]:
    """Calculate p95 and availability using heuristic-v1 model (from stub.py)"""
    base = {
        "serverless-fn":   90.0,
        "serverless-cont": 70.0,
        "k8s":             55.0,
        "vm":              70.0
    }.get(compute_type, 80.0)

    p95 = base + 0.05 * exec_ms
    if variability == "spiky" and compute_type.startswith("serverless"):
        p95 -= 5.0

    avail = {
        "serverless-fn":   99.98,
        "serverless-cont": 99.95,
        "k8s":             99.90,
        "vm":              99.90
    }.get(compute_type, 99.90)

    return round(p95, 2), round(avail, 5)

async def get_unit_rates(vendor: str, region: str, compute_service: str, storage_service: str) -> Dict:
    """
    Async fetcher for unit rates.
    """
    if not REALTIME:
        return {}

    vendor = (vendor or "").lower()
    compute_service = (compute_service or "").lower()
    storage_service = (storage_service or "").lower()
    region = region or "us-east-1"
    
    out: Dict[str, float] = {}

    try:
        if vendor == "azure":
            if compute_service == "container-apps":
                rates = await fetch_container_apps_rates(region)
                if rates.get("vcpu_second"): out["vcpu_sec"] = rates["vcpu_second"]
                if rates.get("memory_gib_second"): out["gib_sec"] = rates["memory_gib_second"]
            
            if storage_service in {"blob", "object"}:
                p = await fetch_blob_gb_month(region)
                if p: out["object_gb_month"] = p

        elif vendor == "gcp":
            if compute_service == "cloud-run":
                rates = await fetch_cloud_run_rates(region)
                if rates.get("vcpu_second"): out["vcpu_sec"] = rates["vcpu_second"]
                if rates.get("memory_gib_second"): out["gib_sec"] = rates["memory_gib_second"]
            
            if storage_service in {"gcs", "object"}:
                p = await fetch_gcs_gb_month(region)
                if p: out["object_gb_month"] = p

        elif vendor == "aws":
            # AWS provider (boto3) is sync, but fast enough or returns empty
            if compute_service in {"fargate", "ecs-fargate"}:
                r = fetch_fargate_rates(region)
                if r.get("vcpu_hour"): out["vcpu_sec"] = r["vcpu_hour"] / 3600.0
                if r.get("memory_gb_hour"): out["gib_sec"] = r["memory_gb_hour"] / 3600.0
            
            if storage_service in {"s3", "object"}:
                p = fetch_s3_gb_month(region)
                if p: out["object_gb_month"] = p

    except Exception as e:
        print(f"Pricing fetch error: {e}")
    
    return out

async def eval_bundles(workload: Dict, bundles: List[Dict]) -> List[Dict]:
    """
    Main Async Evaluation Logic: Realtime pricing + Heuristic performance
    """
    if not REALTIME:
        from .stub import eval_bundles as stub_eval
        return stub_eval(workload, bundles)

    # Pre-calculate workload metrics
    rps = float(workload.get("traffic_rps", 0))
    exec_ms = float(workload.get("avg_exec_ms", 100.0))
    mem_gb = float(workload.get("mem_gb", 0.5))
    vcpu = float(workload.get("cpu_vcpu", 0.25))
    region = workload.get("region", "us-east-1")
    variability = workload.get("variability", "steady")
    p95_target = float(workload.get("p95_target_ms", 0.0) or 0.0)
    egress_gb = float(workload.get("egress_gb_month", 0.0) or 0.0)

    # Policy constraints
    budget_monthly = float(workload.get("budget_monthly", 0.0) or 0.0)
    vendor_exclude = workload.get("vendor_exclude", []) or []
    compliance = workload.get("compliance", "none")
    multi_region = workload.get("multi_region_needed", "no")

    reqs_month = rps * 60 * 60 * 24 * 30
    seconds_month = reqs_month * (exec_ms / 1000.0)

    results = []

    # Process bundles concurrently
    for b in bundles:
        vendor = b["vendor"]
        compute = b["compute_service"]
        storage = b["storage_service"]

        ct = classify_compute(compute)
        st = classify_storage(storage)

        # Await the rates for this specific bundle
        rates = await get_unit_rates(vendor, region, compute, storage)

        # ========== COST BREAKDOWN (Realtime + Fallback) ==========
        compute_cost = 0.0
        storage_cost = 0.0
        egress_cost = 0.0
        addon_cost = 0.0
        overhead_cost = 0.0

        # 1. Compute Cost
        if "vcpu_sec" in rates and "gib_sec" in rates:
            compute_cost = seconds_month * (vcpu * rates["vcpu_sec"] + mem_gb * rates["gib_sec"])
        elif ALLOW_FALLBACK:
            # Fallback from stub logic
            if ct == "serverless-fn":
                request_cost = (reqs_month / 1_000_000.0) * 0.20
                gbsec = seconds_month * mem_gb
                compute_cost = request_cost + gbsec * 0.000016
            elif ct == "serverless-cont":
                compute_cost = seconds_month * vcpu * 0.000024
            elif ct == "k8s":
                compute_cost = 2 * 0.12 * 24 * 30
            elif ct == "vm":
                compute_cost = vcpu * 0.05 * 24 * 30

        # 2. Storage Cost
        if "object_gb_month" in rates:
            storage_gb = float(workload.get("storage_gb_hot", 0))
            storage_cost = storage_gb * rates["object_gb_month"]
        elif ALLOW_FALLBACK:
            if st == "sql":
                storage_cost = 50.0
            elif st == "nosql":
                storage_cost = 40.0
            elif st in {"warehouse", "timeseries/analytics"}:
                storage_cost = 120.0
            elif st == "object":
                storage_gb = float(workload.get("storage_gb_hot", 0))
                storage_cost = storage_gb * 0.023
            elif st == "cache":
                addon_cost = 30.0

        # 3. Egress costs
        if egress_gb > 0:
            egress_cost = egress_gb * 0.09

        # 4. Overhead/managed service fee (5%)
        base_cost = compute_cost + storage_cost
        overhead_cost = base_cost * 0.05

        total_cost = compute_cost + storage_cost + egress_cost + addon_cost + overhead_cost

        # ========== PERFORMANCE (Heuristic-v1) ==========
        p95, avail = calc_perf_heuristic(ct, exec_ms, variability)

        # ========== POLICY CONSTRAINTS ==========
        policy_violations = []

        # Performance constraint
        if p95_target > 0 and p95 > p95_target:
            policy_violations.append(f"Latency {p95:.1f}ms exceeds target {p95_target:.1f}ms")

        # Budget constraint
        if budget_monthly > 0 and total_cost > budget_monthly:
            policy_violations.append(f"Cost ${total_cost:.2f} exceeds budget ${budget_monthly:.2f}")

        # Vendor exclusion
        if vendor in vendor_exclude:
            policy_violations.append(f"Vendor {vendor} is excluded by policy")

        # Compliance constraints
        if compliance == "pci-dss" and st == "object":
            policy_violations.append("Object storage requires additional PCI-DSS controls")

        # Multi-region constraint
        if multi_region == "yes" and ct in ["serverless-fn", "vm"]:
            policy_violations.append("Multi-region configuration requires managed orchestration")

        feasible = "yes" if len(policy_violations) == 0 else "no"

        # 3. Add to results
        results.append({
            "vendor": vendor,
            "compute_service": compute,
            "storage_service": storage,
            "monthly_cost": round(total_cost, 2),
            "cost_breakdown": {
                "compute": round(compute_cost, 2),
                "storage": round(storage_cost, 2),
                "egress": round(egress_cost, 2),
                "addons": round(addon_cost, 2),
                "overhead": round(overhead_cost, 2),
                "total": round(total_cost, 2)
            },
            "policy_violations": policy_violations,
            "feasible": feasible,
            "p95_ms": p95,
            "availability": avail,
            "reason": "realtime" if rates else "fallback",
            "perf_model": "heuristic-v1",
            "avail_model": "heuristic-v1"
        })

    return results

def cache_stats():
    return CACHE.stats()

def cache_clear(url=None):
    CACHE.clear()