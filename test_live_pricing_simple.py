#!/usr/bin/env python3
"""Test script to verify live pricing functionality works correctly."""
import asyncio
import os
import sys

# Set realtime pricing before importing
os.environ["REALTIME_PRICING"] = "1"

from evaluator.providers.aws import fetch_fargate_rates, fetch_s3_gb_month
from evaluator.providers.azure import fetch_container_apps_rates, fetch_blob_gb_month
from evaluator.providers.gcp import fetch_cloud_run_rates, fetch_gcs_gb_month


async def test_aws_pricing():
    """Test AWS pricing fetchers"""
    print("\n" + "="*60)
    print("[AWS] Testing AWS Pricing API")
    print("="*60)

    try:
        print("\n[INFO] Fetching AWS Fargate rates for us-east-1...")
        fargate_rates = fetch_fargate_rates("us-east-1")
        print(f"  [OK] vCPU/second: ${fargate_rates.get('vcpu_second', 0):.8f}")
        print(f"  [OK] Memory GB/second: ${fargate_rates.get('memory_gb_second', 0):.8f}")

        print("\n[INFO] Fetching AWS S3 rates for us-east-1...")
        s3_rate = fetch_s3_gb_month("us-east-1")
        print(f"  [OK] Storage GB/month: ${s3_rate:.4f}")

        return True
    except Exception as e:
        print(f"  [FAIL] AWS pricing failed: {e}")
        return False


async def test_azure_pricing():
    """Test Azure pricing fetchers"""
    print("\n" + "="*60)
    print("[AZURE] Testing Azure Pricing API")
    print("="*60)

    try:
        print("\n[INFO] Fetching Azure Container Apps rates for eastus...")
        container_rates = await fetch_container_apps_rates("eastus")
        print(f"  [OK] vCPU/second: ${container_rates.get('vcpu_second', 0):.8f}")
        print(f"  [OK] Memory GiB/second: ${container_rates.get('memory_gib_second', 0):.8f}")
        print(f"  [OK] Requests/million: ${container_rates.get('request_million', 0):.4f}")

        print("\n[INFO] Fetching Azure Blob Storage rates for eastus...")
        blob_rate = await fetch_blob_gb_month("eastus")
        print(f"  [OK] Hot LRS GB/month: ${blob_rate:.4f}")

        return True
    except Exception as e:
        print(f"  [FAIL] Azure pricing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_gcp_pricing():
    """Test GCP pricing fetchers"""
    print("\n" + "="*60)
    print("[GCP] Testing GCP Pricing API")
    print("="*60)

    try:
        print("\n[INFO] Fetching GCP Cloud Run rates for us-central1...")
        run_rates = await fetch_cloud_run_rates("us-central1")
        print(f"  [OK] vCPU/second: ${run_rates.get('vcpu_second', 0):.8f}")
        print(f"  [OK] Memory GiB/second: ${run_rates.get('memory_gib_second', 0):.8f}")
        print(f"  [OK] Requests/million: ${run_rates.get('request_million', 0):.4f}")

        print("\n[INFO] Fetching GCP Cloud Storage rates for us-central1...")
        gcs_rate = await fetch_gcs_gb_month("us-central1")
        print(f"  [OK] Standard Storage GB/month: ${gcs_rate:.4f}")

        return True
    except Exception as e:
        print(f"  [FAIL] GCP pricing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_end_to_end():
    """Test end-to-end pricing in evaluator"""
    print("\n" + "="*60)
    print("[E2E] Testing End-to-End Pricing Integration")
    print("="*60)

    try:
        from evaluator.pricing import eval_bundles

        workload = {
            "traffic_rps": 100,
            "avg_exec_ms": 200,
            "mem_gb": 1.0,
            "cpu_vcpu": 0.5,
            "region": "us-east-1",
            "variability": "steady",
            "storage_gb_hot": 10,
            "egress_gb_month": 5,
            "budget_monthly": 0,
            "vendor_exclude": []
        }

        bundles = [
            {"vendor": "aws", "compute_service": "fargate", "storage_service": "s3"},
            {"vendor": "azure", "compute_service": "container-apps", "storage_service": "blob"},
            {"vendor": "gcp", "compute_service": "cloud-run", "storage_service": "gcs"}
        ]

        print("\n[INFO] Evaluating 3 cloud bundles with live pricing...")
        results = await eval_bundles(workload, bundles)

        print(f"\n[OK] Evaluated {len(results)} bundles:")
        for r in results:
            reason = r.get('reason', 'unknown')
            cost = r.get('monthly_cost', 0)
            vendor = r.get('vendor', 'unknown')
            compute = r.get('compute_service', 'unknown')

            status = "[LIVE]" if reason == "realtime" else "[FALLBACK]"
            print(f"  {status:12} {vendor.upper():8} | {compute:16} | ${cost:8.2f}/mo")

        realtime_count = sum(1 for r in results if r.get('reason') == 'realtime')
        fallback_count = sum(1 for r in results if r.get('reason') == 'fallback')

        print(f"\n[SUMMARY]")
        print(f"  Realtime pricing: {realtime_count}/{len(results)}")
        print(f"  Fallback pricing: {fallback_count}/{len(results)}")

        return realtime_count > 0

    except Exception as e:
        print(f"  [FAIL] End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "="*70)
    print("CASE Optimizer - Live Pricing Verification Test")
    print("="*70)
    print(f"\nREALTIME_PRICING = {os.getenv('REALTIME_PRICING', 'false')}")

    results = {
        "AWS": await test_aws_pricing(),
        "Azure": await test_azure_pricing(),
        "GCP": await test_gcp_pricing(),
        "End-to-End": await test_end_to_end()
    }

    print("\n" + "="*70)
    print("Test Results Summary")
    print("="*70)

    for provider, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}  {provider}")

    total_passed = sum(results.values())
    total_tests = len(results)

    print(f"\n[RESULT] Overall: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\n[SUCCESS] All live pricing tests passed!")
        print("\n[TIP] The UI will show 'realtime' badge when live pricing is used.")
        sys.exit(0)
    else:
        print("\n[WARNING] Some tests failed. Check the output above for details.")
        print("          Fallback pricing will be used for failed providers.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
