"""
Architecture Packages - Coherent infrastructure patterns

Each package represents a complete, real-world architecture that a competent
engineer would actually build. We don't pick services à la carte - we evaluate
complete, validated architectural patterns.

This solves the fundamental problem: CASE was trying to learn "when to add queue?"
from 50 examples. Instead, we use engineering judgment to define valid patterns,
then let scoring pick the best fit.
"""
from typing import Dict, List

# ========================================================================
# ARCHITECTURE PACKAGE DEFINITIONS
# ========================================================================
# Each package is a coherent set of services that work together
# Think: AWS Well-Architected reference architectures, but codified
# ========================================================================

ARCHITECTURE_PACKAGES = {
    "minimal": {
        "name": "Minimal (Compute + Database)",
        "description": "Baseline compute and database only - no additional infrastructure",
        "includes": {
            "compute": True,
            "database": True,
            "load_balancer": False,
            "queue": False,
            "object_storage": False,
            "api_gateway": False,
            "cache": False,
            "cdn": False,
            "enhanced_monitoring": False,
            "security_services": False,
        },
        "valid_for": lambda w: True,  # Always valid (baseline fallback)
        "score_boost": 0.0,  # Simplest = no boost (cost matters most)
    },

    "simple_jobs": {
        "name": "Simple Background Jobs (Compute + Database + Queue)",
        "description": "Lightweight job processing with queue but minimal infrastructure",
        "includes": {
            "compute": True,
            "database": True,
            "load_balancer": False,
            "queue": True,
            "object_storage": False,  # No object storage - just queue processing
            "api_gateway": False,
            "cache": False,
            "cdn": False,
            "enhanced_monitoring": False,  # Minimal package - LLM will add if needed
            "security_services": False,
        },
        "valid_for": lambda w: (
            w.get("workload_type") in ["background", "batch"] and
            w.get("jobs_per_day", 0) > 0 and
            w.get("storage_gb_hot", 0) <= 10  # Low storage = queue-only processing
        ),
        "score_boost": 3.0,  # Small boost - queue is appropriate but simple
    },

    "web_api": {
        "name": "Web API (Compute + Database + LB + API Gateway)",
        "description": "Standard production API with load balancing and API gateway",
        "includes": {
            "compute": True,
            "database": True,
            "load_balancer": True,
            "queue": False,
            "object_storage": False,
            "api_gateway": True,
            "cache": False,
            "cdn": False,
            "enhanced_monitoring": False,
            "security_services": False,
        },
        "valid_for": lambda w: w.get("workload_type") in ["api", "web"],
        "score_boost": 2.0,  # Small boost - proper API pattern but adds cost
    },

    "async_jobs": {
        "name": "Async Jobs (Compute + Database + Queue + Object Storage + Monitoring)",
        "description": "Background job processing with queue, storage and monitoring",
        "includes": {
            "compute": True,
            "database": True,
            "load_balancer": False,
            "queue": True,
            "object_storage": True,
            "api_gateway": False,
            "cache": False,
            "cdn": False,
            "enhanced_monitoring": False,  # Let LLM decide case-by-case
            "security_services": False,
        },
        "valid_for": lambda w: (
            w.get("workload_type") in ["background", "batch"] and
            w.get("jobs_per_day", 0) > 100 and  # Meaningful job volume
            (w.get("storage_gb_hot", 0) > 10 or  # Has storage to process
             w.get("jobs_per_day", 0) > 10000)  # OR very high job volume
        ),
        "score_boost": 4.0,  # Moderate boost - right pattern but has infrastructure cost
    },

    "web_cdn": {
        "name": "Web + CDN (Compute + Database + LB + CDN + Object Storage)",
        "description": "Web application with CDN for static content delivery",
        "includes": {
            "compute": True,
            "database": True,
            "load_balancer": True,
            "queue": False,
            "object_storage": True,
            "api_gateway": False,
            "cache": False,
            "cdn": True,
            "enhanced_monitoring": False,
            "security_services": False,
        },
        "valid_for": lambda w: w.get("workload_type") == "web",
        "score_boost": 3.0,  # Small boost - CDN valuable but costs money
    },

    "production_api": {
        "name": "Production API (Compute + Database + LB + API Gateway + Cache + Monitoring)",
        "description": "High-traffic production API with caching and enhanced monitoring",
        "includes": {
            "compute": True,
            "database": True,
            "load_balancer": True,
            "queue": False,
            "object_storage": False,
            "api_gateway": True,
            "cache": True,
            "cdn": False,
            "enhanced_monitoring": True,
            "security_services": False,
        },
        "valid_for": lambda w: (
            w.get("workload_type") == "api" and
            w.get("traffic_rps", 0) >= 50 and  # Higher threshold for full production stack
            w.get("environment", "production") == "production"
        ),
        "score_boost": 5.0,  # Moderate boost - complete infrastructure justified for production
    },

    "data_pipeline": {
        "name": "Data Pipeline (Compute + Database + Queue + Object Storage + Monitoring)",
        "description": "ETL/batch data processing with queue, storage, and monitoring",
        "includes": {
            "compute": True,
            "database": True,
            "load_balancer": False,
            "queue": True,
            "object_storage": True,
            "api_gateway": False,
            "cache": False,
            "cdn": False,
            "enhanced_monitoring": True,
            "security_services": False,
        },
        "valid_for": lambda w: (
            w.get("workload_type") in ["batch", "background"] and
            w.get("storage_gb_hot", 0) > 500 and  # Significant storage requirement
            (w.get("jobs_per_day", 0) > 10 or  # Regular processing
             w.get("storage_gb_hot", 0) > 5000)  # OR massive dataset
        ),
        "score_boost": 6.0,  # Higher boost - data infrastructure clearly needed
    },

    "streaming_api": {
        "name": "Streaming API (Compute + Database + LB + Queue + Cache)",
        "description": "Real-time streaming with queue buffering and caching",
        "includes": {
            "compute": True,
            "database": True,
            "load_balancer": True,
            "queue": True,
            "object_storage": False,
            "api_gateway": False,
            "cache": True,
            "cdn": False,
            "enhanced_monitoring": False,
            "security_services": False,
        },
        "valid_for": lambda w: (
            w.get("workload_type") == "streaming" or
            (w.get("workload_type") == "websocket")
        ),
        "score_boost": 5.0,  # Moderate boost - streaming needs this architecture
    },

    "production_web": {
        "name": "Production Web (Full Stack)",
        "description": "Complete production web app with CDN, API Gateway, monitoring, security",
        "includes": {
            "compute": True,
            "database": True,
            "load_balancer": True,
            "queue": False,
            "object_storage": True,
            "api_gateway": True,
            "cache": True,
            "cdn": True,
            "enhanced_monitoring": True,
            "security_services": True,
        },
        "valid_for": lambda w: (
            w.get("workload_type") == "web" and
            w.get("traffic_rps", 0) >= 100  # High traffic justifies full stack
        ),
        "score_boost": 8.0,  # Higher boost - but only for truly high-traffic web apps
    },
}


def get_valid_packages(workload: Dict) -> List[str]:
    """
    Filter architecture packages to only those valid for this workload.

    Uses simple, obvious rules that no sane engineer would disagree with:
    - Background jobs? Need queue
    - Web workload? Can use CDN
    - High traffic API? Need caching

    Returns list of package keys that are valid for this workload.
    """
    valid = []

    for package_key, package_def in ARCHITECTURE_PACKAGES.items():
        validator = package_def["valid_for"]
        if validator(workload):
            valid.append(package_key)

    return valid


def get_package_infrastructure(package_key: str) -> Dict[str, bool]:
    """
    Get the infrastructure components included in a package.

    Returns dict like:
    {
        "compute": True,
        "database": True,
        "queue": True,
        "object_storage": False,
        ...
    }
    """
    if package_key not in ARCHITECTURE_PACKAGES:
        raise ValueError(f"Unknown package: {package_key}")

    return ARCHITECTURE_PACKAGES[package_key]["includes"].copy()


def get_package_score_boost(package_key: str) -> float:
    """
    Get the score boost for choosing this package.

    More complete/appropriate architectures get higher boosts:
    - minimal: 0 (baseline)
    - web_api: 5
    - production_api: 12
    - production_web: 20

    This biases selection toward complete, production-grade architectures
    when they're valid for the workload.
    """
    if package_key not in ARCHITECTURE_PACKAGES:
        return 0.0

    return ARCHITECTURE_PACKAGES[package_key]["score_boost"]


def get_package_description(package_key: str) -> str:
    """Get human-readable description of what this package includes."""
    if package_key not in ARCHITECTURE_PACKAGES:
        return "Unknown package"

    pkg = ARCHITECTURE_PACKAGES[package_key]
    return f"{pkg['name']}: {pkg['description']}"


def explain_package_filtering(workload: Dict) -> None:
    """Debug helper - print which packages are valid and why."""
    print("\n" + "="*80)
    print("ARCHITECTURE PACKAGE FILTERING")
    print("="*80)

    workload_type = workload.get("workload_type", "unknown")
    rps = workload.get("traffic_rps", 0)
    jobs = workload.get("jobs_per_day", 0)
    storage = workload.get("storage_gb_hot", 0)

    print(f"\nWorkload characteristics:")
    print(f"  Type: {workload_type}")
    print(f"  Traffic: {rps} RPS")
    print(f"  Jobs: {jobs}/day")
    print(f"  Storage: {storage}GB")

    valid = get_valid_packages(workload)

    print(f"\nValid packages ({len(valid)}):")
    for pkg_key in valid:
        pkg = ARCHITECTURE_PACKAGES[pkg_key]
        print(f"  - {pkg['name']}")
        print(f"    Boost: +{pkg['score_boost']}")

    print(f"\nInvalid packages:")
    for pkg_key, pkg in ARCHITECTURE_PACKAGES.items():
        if pkg_key not in valid:
            print(f"  - {pkg['name']}")

    print("="*80)
