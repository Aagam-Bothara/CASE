# evaluator/providers/azure.py
import logging
from typing import Dict, Optional, List, Any, Callable
from urllib.parse import quote

from ..utils import fetch_json, CACHE  # CACHE may be used by fetch_json internally

AZURE_RETAIL_API = "https://prices.azure.com/api/retail/prices"
logger = logging.getLogger(__name__)

# --- FALLBACK RATES (Safety Net) ---
# Approximate PAYG prices (good for estimation, not invoicing).
AZURE_FALLBACK_RATES = {
    "container_apps": {
        # vCPU / GiB per second (consumption plan, after free grant – approximate)
        "vcpu_second": 0.000024,
        "memory_gib_second": 0.000003,
        # Requests price per 1M (approx; used if live fetch fails)
        "request_million": 0.40,
    },
    "blob_storage": {
        # Hot LRS, pay-as-you-go, per GB-month (approx East US / 2024–2025)
        "gb_month": 0.018,
    },
}

# Generic → Azure ARM region mapping
# Lets you pass things like "us-east-1" or "us-central1" and we translate.
AZURE_REGION_MAP: Dict[str, str] = {
    # AWS-style → Azure
    "us-east-1": "eastus",
    "us-east-2": "eastus2",
    "us-west-1": "westus",
    "us-west-2": "westus2",
    "eu-west-1": "westeurope",
    # GCP-style → Azure
    "us-central1": "centralus",
    "europe-west1": "westeurope",
    "europe-west2": "uksouth",
}


def _normalize_azure_region(region: str) -> str:
    """
    Normalize a generic or provider-style region name into an Azure armRegionName.

    Examples:
      "us-east-1"   -> "eastus"
      "us-east-2"   -> "eastus2"
      "us-central1" -> "centralus"
      "eastus"      -> "eastus" (unchanged)
    """
    if not region:
        return region
    key = region.lower()
    mapped = AZURE_REGION_MAP.get(key)
    if mapped:
        return mapped
    # If it already looks like a valid Azure name (no change)
    return region


async def _query(filters: List[str]) -> List[Dict[str, Any]]:
    """
    Query the Azure Retail API with the given $filter list and follow pagination.

    Returns a flat list of Items across all pages.
    """
    flt = " and ".join(filters)
    base_url = f"{AZURE_RETAIL_API}?$filter={quote(flt)}"

    items: List[Dict[str, Any]] = []
    next_link: Optional[str] = base_url

    while next_link:
        data = await fetch_json(next_link)
        page_items = data.get("Items", []) or []
        items.extend(page_items)

        # Azure Retail API uses 'NextPageLink' with an absolute URL
        next_link = data.get("NextPageLink")

    return items


async def search_prices_azure(
    arm_region: Optional[str] = None,
    price_type: str = "Consumption",
    where_item: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> List[Dict[str, Any]]:
    """
    Generic Retail API search helper.

    - filters by priceType (Consumption vs Reservation, etc.)
    - optionally filters by armRegionName
    - optionally applies a custom predicate where_item()
    """
    filters = [f"priceType eq '{price_type}'"]
    if arm_region:
        filters.append(f"armRegionName eq '{arm_region}'")

    try:
        raw_items = await _query(filters)
    except Exception as e:
        logger.warning("Azure Retail API query failed (%s).", e)
        return []

    out: List[Dict[str, Any]] = []
    for it in raw_items:
        if where_item and not where_item(it):
            continue

        unit = (it.get("unitOfMeasure") or "").lower()
        price = float(it.get("retailPrice") or 0.0)

        out.append(
            {
                "provider": "azure",
                "sku": it.get("skuId") or it.get("skuName"),
                "price": price,
                "unit": unit,
            }
        )

    return out


def _validate_price(api_val: Optional[float], fb_val: float, label: str) -> float:
    """
    Guard against missing or clearly-wrong values.
    If api_val is None/<=0 or differs from fallback by >10x, use fallback.
    """
    if api_val is None or api_val <= 0:
        return fb_val
    ratio = api_val / fb_val
    if ratio < 0.1 or ratio > 10:
        logger.warning(
            "Azure price for %s looks suspicious (api=%r, fb=%r), using fallback.",
            label,
            api_val,
            fb_val,
        )
        return fb_val
    return api_val


async def fetch_container_apps_request_price(arm_region: str) -> float:
    """
    Fetch Container Apps request pricing (per 1M requests) for the given region.

    Returns: float (USD per 1M requests), falling back to AZURE_FALLBACK_RATES if needed.
    """
    fb = AZURE_FALLBACK_RATES["container_apps"]["request_million"]
    region = _normalize_azure_region(arm_region)

    items = await search_prices_azure(
        arm_region=region,
        where_item=lambda it: (
            "Container Apps" in (it.get("productName") or "")
            and (
                "request" in (it.get("meterName") or "").lower()
                or "requests" in (it.get("meterName") or "").lower()
                or "request" in (it.get("skuName") or "").lower()
            )
        ),
    )

    # Look for units like "1M requests", "1 M Requests", "1M Request"
    candidate_prices: List[float] = []
    for x in items:
        unit = x["unit"]  # already lowercase
        if "request" in unit and ("1m" in unit or "1 m" in unit or "million" in unit):
            candidate_prices.append(x["price"])

    if not candidate_prices:
        logger.warning(
            "No valid Azure Container Apps request prices found for region %s, using fallback.",
            region,
        )
        return fb

    best = min(candidate_prices)
    return _validate_price(best, fb, "container_apps_request_million")


async def fetch_container_apps_rates(arm_region: str) -> Dict[str, float]:
    """
    Return Container Apps CPU & memory pricing in the given region.

    Output shape:
    {
        "vcpu_second": float,
        "memory_gib_second": float,
        "request_million": float,  # per 1M requests (new, optional for callers)
    }

    Uses Azure Retail API with region normalization, but falls back to
    AZURE_FALLBACK_RATES["container_apps"] if anything looks off.
    """
    fb = AZURE_FALLBACK_RATES["container_apps"]
    region = _normalize_azure_region(arm_region)

    # 1. vCPU - More flexible search with multiple patterns
    cpu_items = await search_prices_azure(
        arm_region=region,
        where_item=lambda it: (
            (
                "Container Apps" in (it.get("productName") or "")
                or "Container App" in (it.get("productName") or "")
                or "Azure Container Apps" in (it.get("productName") or "")
            )
            and (
                "vCPU" in (it.get("meterName") or "")
                or "CPU" in (it.get("meterName") or "")
            )
        ),
    )
    vcpu_price_raw = next(
        (x["price"] for x in cpu_items if "second" in x["unit"]), None
    )

    # Log for debugging
    if vcpu_price_raw is None and cpu_items:
        logger.info(
            "Found %d Container Apps CPU items but no per-second pricing. Sample: %s",
            len(cpu_items),
            cpu_items[0] if cpu_items else "N/A"
        )

    # 2. Memory (GiB-seconds) - More flexible search
    mem_items = await search_prices_azure(
        arm_region=region,
        where_item=lambda it: (
            (
                "Container Apps" in (it.get("productName") or "")
                or "Container App" in (it.get("productName") or "")
                or "Azure Container Apps" in (it.get("productName") or "")
            )
            and "Memory" in (it.get("meterName") or "")
        ),
    )
    mem_price_raw = next(
        (
            x["price"]
            for x in mem_items
            if ("gib" in x["unit"] or "gb" in x["unit"]) and "second" in x["unit"]
        ),
        None,
    )

    # Log for debugging
    if mem_price_raw is None and mem_items:
        logger.info(
            "Found %d Container Apps Memory items but no per-GiB-second pricing. Sample: %s",
            len(mem_items),
            mem_items[0] if mem_items else "N/A"
        )

    # If Container Apps pricing not found, try Azure Functions as a proxy (similar consumption model)
    if vcpu_price_raw is None:
        logger.info("Container Apps vCPU not found, trying Azure Functions as proxy")
        func_cpu_items = await search_prices_azure(
            arm_region=region,
            where_item=lambda it: (
                "Functions" in (it.get("productName") or "")
                and "vCPU" in (it.get("meterName") or "")
            ),
        )
        vcpu_price_raw = next(
            (x["price"] for x in func_cpu_items if "second" in x["unit"]), None
        )

    if mem_price_raw is None:
        logger.info("Container Apps Memory not found, trying Azure Functions as proxy")
        func_mem_items = await search_prices_azure(
            arm_region=region,
            where_item=lambda it: (
                "Functions" in (it.get("productName") or "")
                and "Memory" in (it.get("meterName") or "")
            ),
        )
        mem_price_raw = next(
            (
                x["price"]
                for x in func_mem_items
                if ("gib" in x["unit"] or "gb" in x["unit"]) and "second" in x["unit"]
            ),
            None,
        )

    vcpu_price = _validate_price(vcpu_price_raw, fb["vcpu_second"], "container_apps_vcpu")
    mem_price = _validate_price(mem_price_raw, fb["memory_gib_second"], "container_apps_mem")

    # 3. Requests (per 1M) – best effort; falls back if missing
    try:
        req_price = await fetch_container_apps_request_price(region)
    except Exception as e:
        logger.warning(
            "Failed to fetch Container Apps request price for %s (%s), using fallback.",
            region,
            e,
        )
        req_price = fb["request_million"]

    return {
        "vcpu_second": vcpu_price,
        "memory_gib_second": mem_price,
        "request_million": req_price,
    }


async def fetch_blob_gb_month(arm_region: str) -> float:
    """
    Return per-GB-month price for Hot LRS Azure Blob Storage in the given region.

    Output: float (always non-None, using fallback if needed)
    """
    fb = AZURE_FALLBACK_RATES["blob_storage"]["gb_month"]
    region = _normalize_azure_region(arm_region)

    items = await search_prices_azure(
        arm_region=region,
        where_item=lambda it: (
            "Storage" in (it.get("serviceName") or "")
            and "Blob Storage" in (it.get("productName") or "")
            and (
                "Hot" in (it.get("meterName") or "")
                or "hot" in (it.get("skuName") or "").lower()
            )
            and (
                "LRS" in (it.get("skuName") or "")
                or "Locally Redundant" in (it.get("skuName") or "")
            )
        ),
    )

    valid = [
        x["price"]
        for x in items
        if ("gb" in x["unit"] or "gib" in x["unit"]) and ("month" in x["unit"])
    ]

    if not valid:
        logger.warning(
            "No valid Azure Blob Hot LRS GB-month prices found for region %s, using fallback.",
            region,
        )
        return fb

    best = min(valid)
    return _validate_price(best, fb, "blob_hot_lrs_gb_month")
