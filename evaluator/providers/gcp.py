# evaluator/providers/gcp.py
import logging
import os
import time
from typing import Any, Dict, Optional, List, Tuple

from ..utils import fetch_json

# Initialize logger first
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Load API key from environment variable only (no hardcoded fallback)
API_KEY = os.getenv("GCP_BILLING_API_KEY")
BASE_URL = "https://cloudbilling.googleapis.com/v1"
CACHE_TTL = 3600 * 12  # 12 Hours

# Log warning if API key is not set
if not API_KEY:
    logger.warning(
        "GCP_BILLING_API_KEY not found in environment variables. "
        "GCP pricing will use fallback rates only. "
        "Set REALTIME_PRICING=1 and GCP_BILLING_API_KEY to enable live pricing."
    )

# --- FALLBACK RATES (Safety Net) ---
# Used if API fails or Key is missing. Based on us-central1 standard rates.
FALLBACK_RATES = {
    "cloud_run": {
        "vcpu_second": 0.00002400,
        "memory_gib_second": 0.00000250,
        "request_million": 0.40,  # per 1M requests
    },
    "cloud_storage": {
        "gb_month": 0.020,              # Standard Storage
        "class_a_ops_per_1000": 0.005,  # Per 1000 operations
        "class_b_ops_per_1000": 0.0004  # Per 1000 operations
    }
}

# --- FREE TIER LIMITS (Monthly) ---
FREE_TIER = {
    "cloud_run": {
        "vcpu_seconds": 180_000,
        "memory_gib_seconds": 360_000,
        "requests": 2_000_000,
        "networking_egress_gb": 1.0
    },
    "cloud_storage": {
        "gb_months": 5.0,
        "class_a_ops": 5_000,
        "class_b_ops": 50_000,
        "egress_gb": 1.0
    }
}


class GCPPriceFetcher:
    """
    Fetches raw unit prices from the Cloud Billing Catalog API with caching & fallback.
    """
    _cache: Dict[str, Tuple[float, Any]] = {}
    _service_ids: Dict[str, str] = {}

    # --------- helpers for catalog discovery ----------

    @classmethod
    async def _ensure_service_ids(cls) -> None:
        """
        Populate _service_ids with { 'cloud_run': 'services/…', 'cloud_storage': 'services/…' }.
        """
        if cls._service_ids or not API_KEY:
            return

        url = f"{BASE_URL}/services"
        params: Dict[str, Any] = {"key": API_KEY}
        services: List[Dict[str, Any]] = []
        page_token: Optional[str] = None

        while True:
            if page_token:
                params["pageToken"] = page_token
            data = await fetch_json(url, params=params)
            services.extend(data.get("services", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        for svc in services:
            display = svc.get("displayName")
            name = svc.get("name")
            if not name or not display:
                continue
            if display == "Cloud Run":
                cls._service_ids["cloud_run"] = name
            elif display == "Cloud Storage":
                cls._service_ids["cloud_storage"] = name

        logger.debug("Discovered GCP billing services: %r", cls._service_ids)

    @staticmethod
    def _extract_price_from_sku(sku: Dict[str, Any]) -> Optional[float]:
        """
        Given a SKU from ListSkus(), return a representative unit price in USD.
        We pick the lowest tier with a non-zero price.
        """
        pricing_info = sku.get("pricingInfo") or []
        if not pricing_info:
            return None

        expr = pricing_info[0].get("pricingExpression") or {}
        rates = expr.get("tieredRates") or []
        best_price: Optional[float] = None
        best_start: Optional[float] = None

        for rate in rates:
            unit_price = rate.get("unitPrice") or {}
            units = float(unit_price.get("units") or 0)
            nanos = float(unit_price.get("nanos") or 0)
            price = units + nanos / 1e9
            if price <= 0:
                continue

            start = float(rate.get("startUsageAmount") or 0)
            if best_price is None or best_start is None or start < best_start:
                best_price = price
                best_start = start

        return best_price

    # --------- Cloud Run pricing ----------

    @classmethod
    async def _fetch_cloud_run_rates(
        cls, service_name: str, region: str
    ) -> Dict[str, float]:
        """
        Derive Cloud Run CPU, Memory, and Request unit prices from the Catalog API.

        Returns a dict shaped like FALLBACK_RATES["cloud_run"].
        """
        url = f"{BASE_URL}/{service_name}/skus"
        params: Dict[str, Any] = {
            "key": API_KEY,
            "currencyCode": "USD",
            "pageSize": 5000,
        }
        page_token: Optional[str] = None

        cpu_price: Optional[float] = None
        mem_price: Optional[float] = None
        req_price: Optional[float] = None

        while True:
            if page_token:
                params["pageToken"] = page_token
            data = await fetch_json(url, params=params)

            for sku in data.get("skus", []):
                cat = sku.get("category") or {}
                if cat.get("usageType") != "OnDemand":
                    continue

                geo = sku.get("geoTaxonomy") or {}
                regions = geo.get("regions") or sku.get("serviceRegions") or []
                geo_type = geo.get("type", "")

                if regions:
                    if region in regions:
                        pass
                    elif region.startswith("us-") and any(
                        r in ("US", "northamerica") for r in regions
                    ):
                        pass
                    elif geo_type == "GLOBAL":
                        pass
                    else:
                        continue

                desc = (sku.get("description") or "").lower()
                price = cls._extract_price_from_sku(sku)
                if price is None:
                    continue

                if ("cpu" in desc or "v cpu" in desc or "vcpu" in desc) and cpu_price is None:
                    cpu_price = price
                elif ("memory" in desc or "gib" in desc) and mem_price is None:
                    mem_price = price
                elif "request" in desc and req_price is None:
                    req_price = price

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        if cpu_price is None or mem_price is None or req_price is None:
            logger.warning(
                "Could not resolve all Cloud Run prices from API, falling back. "
                "cpu=%r mem=%r req=%r", cpu_price, mem_price, req_price
            )
            return FALLBACK_RATES["cloud_run"].copy()

        fb = FALLBACK_RATES["cloud_run"]

        def _validate(api_val: float, fb_val: float) -> float:
            if api_val is None or api_val <= 0:
                return fb_val
            ratio = api_val / fb_val
            if ratio < 0.1 or ratio > 10:
                return fb_val
            return api_val

        return {
            "vcpu_second": _validate(cpu_price, fb["vcpu_second"]),
            "memory_gib_second": _validate(mem_price, fb["memory_gib_second"]),
            # treat catalog request unit as "per 1M", fall back if weird
            "request_million": _validate(req_price, fb["request_million"]),
        }

    # --------- Public API ----------

    @classmethod
    async def get_rate(cls, service_key: str, region: str) -> Dict[str, float]:
        """
        Get a rate dict for the given logical service key in the given region.

        For now:
          * cloud_run → live Catalog pricing (with fallback)
          * cloud_storage → fallback only
        """
        cache_key = f"{service_key}_{region}"
        now = time.time()

        # 1. Cache
        if cache_key in cls._cache:
            ts, data = cls._cache[cache_key]
            if now - ts < CACHE_TTL:
                return data

        # 2. No API key → immediate fallback
        if not API_KEY:
            logger.warning(
                "No GCP_BILLING_API_KEY set, using fallback for %s", service_key
            )
            data = FALLBACK_RATES.get(service_key, {}).copy()
            cls._cache[cache_key] = (now, data)
            return data

        # 3. Live fetch
        try:
            await cls._ensure_service_ids()
            service_name = cls._service_ids.get(service_key)
            if not service_name:
                raise RuntimeError(f"No service id discovered for {service_key}")

            if service_key == "cloud_run":
                data = await cls._fetch_cloud_run_rates(service_name, region)
            else:
                # TODO: implement live prices for Cloud Storage if needed.
                data = FALLBACK_RATES.get(service_key, {}).copy()

            cls._cache[cache_key] = (now, data)
            return data

        except Exception as e:
            logger.warning("GCP Catalog API unavailable (%s), using fallback rates.", e)
            data = FALLBACK_RATES.get(service_key, {}).copy()
            cls._cache[cache_key] = (now, data)
            return data


class GCPBillEstimator:
    """
    The Calculator Logic. Applies Free Tiers and Usage Formulas.
    """

    @staticmethod
    async def estimate_cloud_run(
        region: str,
        total_requests: int,
        avg_latency_ms: float,
        vcpu_count: float = 1.0,
        memory_gib: float = 0.5,
        instance_count: int = 1,  # currently unused
    ) -> Dict[str, Any]:
        """
        Calculates Cloud Run bill including Free Tier deduction.
        """
        rates = await GCPPriceFetcher.get_rate("cloud_run", region)

        # Cloud Run rounds up to nearest 100ms
        billed_duration_ms = max(100, avg_latency_ms)
        total_duration_sec = (total_requests * billed_duration_ms) / 1000.0

        gross_vcpu_sec = total_duration_sec * vcpu_count
        gross_mem_sec = total_duration_sec * memory_gib

        billable_vcpu = max(0.0, gross_vcpu_sec - FREE_TIER["cloud_run"]["vcpu_seconds"])
        billable_mem = max(0.0, gross_mem_sec - FREE_TIER["cloud_run"]["memory_gib_seconds"])
        billable_reqs = max(0, total_requests - FREE_TIER["cloud_run"]["requests"])

        cost_vcpu = billable_vcpu * rates["vcpu_second"]
        cost_mem = billable_mem * rates["memory_gib_second"]
        cost_reqs = (billable_reqs / 1_000_000) * rates["request_million"]

        total_cost = cost_vcpu + cost_mem + cost_reqs

        return {
            "service": "Cloud Run",
            "usage": {
                "requests": total_requests,
                "gross_vcpu_sec": f"{gross_vcpu_sec:.2f}",
                "gross_mem_sec": f"{gross_mem_sec:.2f}",
            },
            "billable": {
                "vcpu_sec": f"{billable_vcpu:.2f}",
                "mem_sec": f"{billable_mem:.2f}",
                "requests": billable_reqs,
            },
            "cost_breakdown": {
                "compute_cpu": f"${cost_vcpu:.4f}",
                "compute_mem": f"${cost_mem:.4f}",
                "requests": f"${cost_reqs:.4f}",
            },
            "total_estimated_cost": f"${total_cost:.4f}",
        }

    @staticmethod
    async def estimate_cloud_storage(
        region: str,
        storage_gb: float,
        class_a_ops: int,
        class_b_ops: int,
    ) -> Dict[str, Any]:
        """
        Calculates GCS bill including Free Tier (US Regions only usually).
        Currently uses fallback rates only.
        """
        rates = await GCPPriceFetcher.get_rate("cloud_storage", region)

        is_us_region = region.startswith("us-")
        free_storage = FREE_TIER["cloud_storage"]["gb_months"] if is_us_region else 0.0

        billable_storage = max(0.0, storage_gb - free_storage)
        billable_op_a = max(0, class_a_ops - FREE_TIER["cloud_storage"]["class_a_ops"])
        billable_op_b = max(0, class_b_ops - FREE_TIER["cloud_storage"]["class_b_ops"])

        cost_storage = billable_storage * rates["gb_month"]
        cost_op_a = (billable_op_a / 1000.0) * rates["class_a_ops_per_1000"]
        cost_op_b = (billable_op_b / 1000.0) * rates["class_b_ops_per_1000"]

        total_cost = cost_storage + cost_op_a + cost_op_b

        return {
            "service": "Cloud Storage",
            "usage": {
                "storage_gb": storage_gb,
                "ops_total": class_a_ops + class_b_ops,
            },
            "billable": {
                "storage_gb": f"{billable_storage:.2f}",
                "ops_a": billable_op_a,
                "ops_b": billable_op_b,
            },
            "cost_breakdown": {
                "storage": f"${cost_storage:.4f}",
                "operations": f"${(cost_op_a + cost_op_b):.4f}",
            },
            "total_estimated_cost": f"${total_cost:.4f}",
        }


# --- Compatibility wrappers for evaluator/pricing.py ---

async def fetch_cloud_run_rates(region: str):
    """
    Wrapper used by evaluator/pricing.py.

    Returns a dict of Cloud Run rates for the region:
    {
        "vcpu_second": float,
        "memory_gib_second": float,
        "request_million": float,
    }
    """
    return await GCPPriceFetcher.get_rate("cloud_run", region)


async def fetch_gcs_gb_month(region: str) -> float:
    """
    Wrapper used by evaluator/pricing.py.

    Returns the per-GB-month storage price (float) for Cloud Storage.
    """
    rates = await GCPPriceFetcher.get_rate("cloud_storage", region)
    return rates["gb_month"]
