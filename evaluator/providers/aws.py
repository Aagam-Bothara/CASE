# evaluator/providers/aws.py
import json
import logging
from typing import Dict, Optional

# Try importing boto3
try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

logger = logging.getLogger("case.optimizer.aws")

# Map generic region → AWS Pricing API "location" string
REGION_MAP = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "EU (Ireland)",
}

# --- FALLBACK RATES (Safety Net) ---
# Approx public PAYG rates; safe for estimates (not invoices).
AWS_FALLBACK_RATES = {
    "fargate": {
        # Fargate Linux/x86 (approx late 2024/2025)
        # Source: per vCPU-hour & GB-hour → we store per-second.
        "vcpu_second": 0.04048 / 3600.0,       # ~$0.04048 per vCPU-hour
        "memory_gb_second": 0.004445 / 3600.0  # ~$0.004445 per GB-hour
    },
    "s3": {
        # S3 Standard storage + requests (first 50 TB / month)
        "gb_month": 0.023,
        "put_1k": 0.005,    # PUT/COPY/POST/LIST per 1k requests
        "get_1k": 0.0004,   # GET/SELECT per 1k requests
    },
}


def get_pricing_client():
    """
    Create a boto3 Pricing client using environment variables.

    Required environment variables:
    - AWS_ACCESS_KEY_ID: Your AWS access key
    - AWS_SECRET_ACCESS_KEY: Your AWS secret key

    SECURITY: These credentials should be from an IAM user with minimal
    permissions (pricing:GetProducts read-only access).

    Returns None if credentials are missing or boto3 is not installed,
    triggering fallback to stub pricing.
    """
    if not HAS_BOTO3:
        logger.info("boto3 not installed; AWS pricing will use fallback rates.")
        return None

    # Load credentials from environment variables
    import os
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

    # Check if credentials are provided
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        logger.info(
            "AWS credentials not found in environment variables "
            "(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY). "
            "AWS pricing will use fallback rates only. "
            "Set REALTIME_PRICING=1 and provide credentials to enable live pricing."
        )
        return None

    try:
        client = boto3.client(
            "pricing",
            region_name="us-east-1",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        return client
    except Exception as e:
        logger.warning(f"Failed to create boto3 pricing client: {e}")
        return None


def _validate_price(api_val: Optional[float], fb_val: float, label: str) -> float:
    """
    Guard against missing or clearly-wrong values by falling back.

    If api_val is None/<=0 or differs from fallback by >10x, use fallback.
    """
    if api_val is None or api_val <= 0:
        return fb_val
    ratio = api_val / fb_val
    if ratio < 0.1 or ratio > 10:
        logger.warning(
            "AWS price for %s looks suspicious (api=%r, fb=%r); using fallback.",
            label,
            api_val,
            fb_val,
        )
        return fb_val
    return api_val


def fetch_fargate_rates(region: str) -> Dict[str, float]:
    """
    Fetch AWS Fargate CPU & memory prices for the given region.

    Returns:
    {
        "vcpu_second": float,
        "memory_gb_second": float,
    }

    If AWS Pricing API fails or is unavailable, returns fallback.
    """
    fb = AWS_FALLBACK_RATES["fargate"]
    client = get_pricing_client()
    if not client:
        return fb.copy()

    loc = REGION_MAP.get(region, "US East (N. Virginia)")

    vcpu_hour_price: Optional[float] = None
    mem_gb_hour_price: Optional[float] = None

    try:
        next_token: Optional[str] = None

        while True:
            kwargs = dict(
                ServiceCode="AmazonECS",
                Filters=[
                    {"Type": "TERM_MATCH", "Field": "location", "Value": loc},
                    {"Type": "TERM_MATCH", "Field": "termType", "Value": "OnDemand"},
                ],
                MaxResults=100,
            )
            if next_token:
                kwargs["NextToken"] = next_token

            resp = client.get_products(**kwargs)

            for price_str in resp.get("PriceList", []):
                try:
                    product = json.loads(price_str)
                except Exception:
                    continue

                terms = product.get("terms", {}).get("OnDemand", {})
                for term in terms.values():
                    dims = term.get("priceDimensions", {})
                    for dim in dims.values():
                        desc = (dim.get("description") or "").lower()
                        unit = (dim.get("unit") or "").lower()
                        usd = dim.get("pricePerUnit", {}).get("USD")

                        if not usd:
                            continue
                        try:
                            price = float(usd)
                        except Exception:
                            continue

                        # Fargate vCPU hours
                        if "fargate" in desc and "vcpu" in desc and unit == "hrs":
                            if vcpu_hour_price is None or price < vcpu_hour_price:
                                vcpu_hour_price = price

                        # Fargate GB hours (memory)
                        if "fargate" in desc and "gb" in desc and unit == "hrs":
                            if mem_gb_hour_price is None or price < mem_gb_hour_price:
                                mem_gb_hour_price = price

            next_token = resp.get("NextToken")
            if not next_token:
                break

    except Exception as e:
        logger.warning(
            "AWS Pricing get_products failed for Fargate (%s); using fallback.", e
        )
        return fb.copy()

    if vcpu_hour_price is None or mem_gb_hour_price is None:
        logger.warning(
            "Could not resolve both Fargate vCPU/memory prices for %s; using fallback.",
            region,
        )
        return fb.copy()

    # Convert from per-hour to per-second
    vcpu_second = _validate_price(
        vcpu_hour_price / 3600.0, fb["vcpu_second"], "fargate_vcpu"
    )
    mem_second = _validate_price(
        mem_gb_hour_price / 3600.0, fb["memory_gb_second"], "fargate_memory"
    )

    return {
        "vcpu_second": vcpu_second,
        "memory_gb_second": mem_second,
    }


def fetch_s3_gb_month(region: str) -> float:
    """
    Fetch AWS S3 Standard GB-month price for the given region.

    Returns: float (GB-month price). Falls back if API fails.
    """
    fb = AWS_FALLBACK_RATES["s3"]["gb_month"]
    client = get_pricing_client()
    if not client:
        return fb

    loc = REGION_MAP.get(region, "US East (N. Virginia)")

    best_price: Optional[float] = None

    try:
        next_token: Optional[float] = None

        while True:
            kwargs = dict(
                ServiceCode="AmazonS3",
                Filters=[
                    {"Type": "TERM_MATCH", "Field": "location", "Value": loc},
                    {"Type": "TERM_MATCH", "Field": "termType", "Value": "OnDemand"},
                ],
                MaxResults=100,
            )
            if next_token:
                kwargs["NextToken"] = next_token

            resp = client.get_products(**kwargs)

            for price_str in resp.get("PriceList", []):
                try:
                    product = json.loads(price_str)
                except Exception:
                    continue

                # Filter to S3 Standard storage SKUs
                prod_attrs = product.get("product", {}).get("attributes", {})
                storage_class = (prod_attrs.get("storageClass") or "").lower()
                if "standard" not in storage_class:
                    continue

                terms = product.get("terms", {}).get("OnDemand", {})
                for term in terms.values():
                    dims = term.get("priceDimensions", {})
                    for dim in dims.values():
                        unit = (dim.get("unit") or "").lower()
                        usd = dim.get("pricePerUnit", {}).get("USD")
                        if not usd:
                            continue
                        if "gb-mo" not in unit and "gb-month" not in unit:
                            continue

                        try:
                            price = float(usd)
                        except Exception:
                            continue

                        if best_price is None or price < best_price:
                            best_price = price

            next_token = resp.get("NextToken")
            if not next_token:
                break

    except Exception as e:
        logger.warning(
            "AWS Pricing get_products failed for S3 storage (%s); using fallback.", e
        )
        return fb

    if best_price is None:
        logger.warning(
            "No valid S3 Standard GB-month price found for %s; using fallback.", region
        )
        return fb

    return _validate_price(best_price, fb, "s3_standard_gb_month")


def fetch_s3_request_prices(region: str) -> Dict[str, float]:
    """
    Fetch AWS S3 Standard request pricing for the given region.

    Returns:
    {
        "put_1k": float,   # PUT/COPY/POST/LIST per 1k requests
        "get_1k": float,   # GET per 1k requests
    }

    Falls back if API fails.
    """
    fb_put = AWS_FALLBACK_RATES["s3"]["put_1k"]
    fb_get = AWS_FALLBACK_RATES["s3"]["get_1k"]

    client = get_pricing_client()
    if not client:
        return {"put_1k": fb_put, "get_1k": fb_get}

    loc = REGION_MAP.get(region, "US East (N. Virginia)")

    put_price: Optional[float] = None
    get_price: Optional[float] = None

    try:
        next_token: Optional[float] = None

        while True:
            kwargs = dict(
                ServiceCode="AmazonS3",
                Filters=[
                    {"Type": "TERM_MATCH", "Field": "location", "Value": loc},
                    {"Type": "TERM_MATCH", "Field": "termType", "Value": "OnDemand"},
                ],
                MaxResults=100,
            )
            if next_token:
                kwargs["NextToken"] = next_token

            resp = client.get_products(**kwargs)

            for price_str in resp.get("PriceList", []):
                try:
                    product = json.loads(price_str)
                except Exception:
                    continue

                prod_attrs = product.get("product", {}).get("attributes", {})
                if (prod_attrs.get("productFamily") or "").lower() != "requests":
                    continue

                terms = product.get("terms", {}).get("OnDemand", {})
                for term in terms.values():
                    dims = term.get("priceDimensions", {})
                    for dim in dims.values():
                        desc = (dim.get("description") or "").lower()
                        unit = (dim.get("unit") or "").lower()
                        usd = dim.get("pricePerUnit", {}).get("USD")
                        if not usd:
                            continue
                        if "requests" not in unit:
                            continue

                        try:
                            price = float(usd)
                        except Exception:
                            continue

                        # PUT/COPY/POST/LIST bucket
                        if (
                            "put" in desc
                            or "post" in desc
                            or "copy" in desc
                            or "list" in desc
                        ):
                            if put_price is None or price < put_price:
                                put_price = price

                        # GET bucket
                        elif "get" in desc:
                            if get_price is None or price < get_price:
                                get_price = price

            next_token = resp.get("NextToken")
            if not next_token:
                break

    except Exception as e:
        logger.warning(
            "AWS Pricing get_products failed for S3 requests (%s); using fallback.", e
        )
        return {"put_1k": fb_put, "get_1k": fb_get}

    put_final = _validate_price(put_price, fb_put, "s3_put_1k")
    get_final = _validate_price(get_price, fb_get, "s3_get_1k")

    return {"put_1k": put_final, "get_1k": get_final}
