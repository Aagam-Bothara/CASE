# evaluator/stub.py
from typing import Dict, List

def classify_compute(svc: str) -> str:
    s = svc.lower()
    if s in {"lambda", "functions", "cloud-functions"}:
        return "serverless-fn"
    if s in {"cloud-run", "fargate", "container-apps"}:
        return "serverless-cont"
    if s in {"eks", "aks", "gke"}:
        return "k8s"
    if s in {"ec2", "vm", "gce"}:
        return "vm"
    return "other"

def classify_storage(svc: str) -> str:
    s = svc.lower()
    if s in {"rds-aurora", "azure-sql", "cloud-sql"}: return "sql"
    if s in {"dynamodb", "cosmosdb", "bigtable"}: return "nosql"
    if s in {"timestream", "data-explorer", "bigquery"}: return "timeseries/analytics"
    if s in {"redshift", "synapse", "bigquery"}: return "warehouse"
    if s in {"s3", "blob", "gcs"}: return "object"
    if s in {"elasticache-redis", "azure-redis", "memorystore-redis"}: return "cache"
    if s == "none": return "none"
    return "other"

def eval_bundles(workload: Dict, bundles: List[Dict]) -> List[Dict]:
    rps         = max(workload.get("traffic_rps", 0), 0)
    exec_ms     = max(workload.get("avg_exec_ms", 100.0), 1.0)
    p95_target  = float(workload.get("p95_target_ms", 0.0) or 0.0)
    mem_gb      = max(float(workload.get("mem_gb", 0.5)), 0.1)
    variability = workload.get("variability", "steady")
    egress_gb   = float(workload.get("egress_gb_month", 0.0) or 0.0)

    # Policy constraints
    budget_monthly = float(workload.get("budget_monthly", 0.0) or 0.0)
    vendor_exclude = workload.get("vendor_exclude", []) or []
    compliance = workload.get("compliance", "none")
    multi_region = workload.get("multi_region_needed", "no")

    reqs_month = rps * 60 * 60 * 24 * 30
    evals: List[Dict] = []

    for b in bundles:
        ct = classify_compute(b["compute_service"])
        st = classify_storage(b["storage_service"])

        # ========== PERFORMANCE MODELING (Heuristic-v1) ==========
        base = {
            "serverless-fn":   90.0,
            "serverless-cont": 70.0,
            "k8s":             55.0,
            "vm":              70.0
        }.get(ct, 80.0)

        p95 = base + 0.05 * exec_ms
        if variability == "spiky" and ct.startswith("serverless"):
            p95 -= 5.0

        avail = {
            "serverless-fn":   99.98,
            "serverless-cont": 99.95,
            "k8s":             99.90,
            "vm":              99.90
        }.get(ct, 99.90)

        # ========== COST BREAKDOWN ==========
        compute_cost = 0.0
        storage_cost = 0.0
        egress_cost = 0.0
        addon_cost = 0.0
        overhead_cost = 0.0

        # Compute costs
        if ct == "serverless-fn":
            request_cost = (reqs_month / 1_000_000.0) * 0.20
            gbsec = reqs_month * (exec_ms / 1000.0) * mem_gb
            gbsec_cost = gbsec * 0.000016
            compute_cost = request_cost + gbsec_cost
        elif ct == "serverless-cont":
            vcpu = max(float(workload.get("cpu_vcpu", 0.25)), 0.25)
            seconds = reqs_month * (exec_ms / 1000.0)
            compute_cost = seconds * vcpu * 0.000024
        elif ct == "k8s":
            nodes_cost = 2 * 0.12 * 24 * 30
            compute_cost = nodes_cost
        elif ct == "vm":
            vcpu = max(float(workload.get("cpu_vcpu", 2.0)), 1.0)
            compute_cost = vcpu * 0.05 * 24 * 30

        # Storage/DB/Cache costs
        if st == "sql":
            storage_cost = 50.0
        elif st == "nosql":
            storage_cost = 40.0
        elif st in {"warehouse", "timeseries/analytics"}:
            storage_cost = 120.0
        elif st == "object":
            gb = float(workload.get("storage_gb_hot", 0.0) or 0.0)
            storage_cost = gb * 0.023
        elif st == "cache":
            addon_cost = 30.0  # Redis cache baseline

        # Egress costs (if provided)
        if egress_gb > 0:
            egress_cost = egress_gb * 0.09  # ~$0.09/GB typical

        # Overhead/managed service fee (5% of compute+storage)
        base_cost = compute_cost + storage_cost
        overhead_cost = base_cost * 0.05

        total_cost = compute_cost + storage_cost + egress_cost + addon_cost + overhead_cost

        # Policy constraint checks
        policy_violations = []

        # Performance constraint
        if p95_target > 0 and p95 > p95_target:
            policy_violations.append(f"Latency {p95:.1f}ms exceeds target {p95_target:.1f}ms")

        # Budget constraint
        if budget_monthly > 0 and total_cost > budget_monthly:
            policy_violations.append(f"Cost ${total_cost:.2f} exceeds budget ${budget_monthly:.2f}")

        # Vendor exclusion
        if b["vendor"] in vendor_exclude:
            policy_violations.append(f"Vendor {b['vendor']} is excluded by policy")

        # Compliance constraints (basic implementation)
        if compliance == "hipaa" and b["vendor"] == "gcp":
            # Example: GCP not HIPAA compliant in this model (hypothetical)
            pass  # All vendors support HIPAA in reality

        if compliance == "pci-dss" and st == "object":
            # Example: Object storage not PCI-DSS compliant without additional controls
            policy_violations.append("Object storage requires additional PCI-DSS controls")

        # Multi-region constraint
        if multi_region == "yes" and ct in ["serverless-fn", "vm"]:
            # Example: Some services harder to multi-region
            policy_violations.append("Multi-region configuration requires managed orchestration")

        feasible = "yes" if len(policy_violations) == 0 else "no"

        evals.append({
            "vendor": b["vendor"],
            "compute_service": b["compute_service"],
            "storage_service": b["storage_service"],
            "feasible": feasible,
            "p95_ms": round(p95, 2),
            "availability": round(avail, 5),
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
            "reason": "stub-evaluator",
            "perf_model": "heuristic-v1",
            "avail_model": "heuristic-v1"
        })

    return evals