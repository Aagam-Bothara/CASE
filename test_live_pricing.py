#!/usr/bin/env python3
"""
Test script to verify live pricing functionality works correctly.
"""
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
    print("🔵 Testing AWS Pricing API")
    print("="*60)

    try:
        # Test Fargate pricing
        print("\n📊 Fetching AWS Fargate rates for us-east-1...")
        fargate_rates = fetch_fargate_rates("us-east-1")
        print(f"  ✓ vCPU/second: ${fargate_rates.get('vcpu_second', 0):.8f}")
        print(f"  ✓ Memory GB/second: ${fargate_rates.get('memory_gb_second', 0):.8f}")

        # Test S3 pricing
        print("\n📊 Fetching AWS S3 rates for us-east-1...")
        s3_rate = fetch_s3_gb_month("us-east-1")
        print(f"  ✓ Storage GB/month: ${s3_rate:.4f}")

        return True
    except Exception as e:
        print(f"  ✗ AWS pricing failed: {e}")
        return False


async def test_azure_pricing():
    """Test Azure pricing fetchers"""
    print("\n" + "="*60)
    print("🔷 Testing Azure Pricing API")
    print("="*60)

    try:
        # Test Container Apps pricing
        print("\n📊 Fetching Azure Container Apps rates for eastus...")
        container_rates = await fetch_container_apps_rates("eastus")
        print(f"  ✓ vCPU/second: ${container_rates.get('vcpu_second', 0):.8f}")
        print(f"  ✓ Memory GiB/second: ${container_rates.get('memory_gib_second', 0):.8f}")
        print(f"  ✓ Requests/million: ${container_rates.get('request_million', 0):.4f}")

        # Test Blob Storage pricing
        print("\n📊 Fetching Azure Blob Storage rates for eastus...")
        blob_rate = await fetch_blob_gb_month("eastus")
        print(f"  ✓ Hot LRS GB/month: ${blob_rate:.4f}")

        return True
    except Exception as e:
        print(f"  ✗ Azure pricing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_gcp_pricing():
    """Test GCP pricing fetchers"""
    print("\n" + "="*60)
    print("🟢 Testing GCP Pricing API")
    print("="*60)

    try:
        # Test Cloud Run pricing
        print("\n📊 Fetching GCP Cloud Run rates for us-central1...")
        run_rates = await fetch_cloud_run_rates("us-central1")
        print(f"  ✓ vCPU/second: ${run_rates.get('vcpu_second', 0):.8f}")
        print(f"  ✓ Memory GiB/second: ${run_rates.get('memory_gib_second', 0):.8f}")
        print(f"  ✓ Requests/million: ${run_rates.get('request_million', 0):.4f}")

        # Test GCS pricing
        print("\n📊 Fetching GCP Cloud Storage rates for us-central1...")
        gcs_rate = await fetch_gcs_gb_month("us-central1")
        print(f"  ✓ Standard Storage GB/month: ${gcs_rate:.4f}")

        return True
    except Exception as e:
        print(f"  ✗ GCP pricing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_end_to_end():
    """Test end-to-end pricing in evaluator"""
    print("\n" + "="*60)
    print("🔄 Testing End-to-End Pricing Integration")
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

        print("\n📊 Evaluating 3 cloud bundles with live pricing...")
        results = await eval_bundles(workload, bundles)

        print(f"\n✓ Evaluated {len(results)} bundles:")
        for r in results:
            reason = r.get('reason', 'unknown')
            cost = r.get('monthly_cost', 0)
            vendor = r.get('vendor', 'unknown')
            compute = r.get('compute_service', 'unknown')

            status_icon = "🟢" if reason == "realtime" else "🟡"
            print(f"  {status_icon} {vendor.upper():8} | {compute:16} | ${cost:8.2f}/mo | {reason}")

        # Check if any used realtime pricing
        realtime_count = sum(1 for r in results if r.get('reason') == 'realtime')
        fallback_count = sum(1 for r in results if r.get('reason') == 'fallback')

        print(f"\n📈 Summary:")
        print(f"  • Realtime pricing: {realtime_count}/{len(results)}")
        print(f"  • Fallback pricing: {fallback_count}/{len(results)}")

        return realtime_count > 0

    except Exception as e:
        print(f"  ✗ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "="*70)
    print("🚀 CASE Optimizer - Live Pricing Verification Test")
    print("="*70)
    print(f"\n⚙️  REALTIME_PRICING = {os.getenv('REALTIME_PRICING', 'false')}")

    results = {
        "AWS": await test_aws_pricing(),
        "Azure": await test_azure_pricing(),
        "GCP": await test_gcp_pricing(),
        "End-to-End": await test_end_to_end()
    }

    print("\n" + "="*70)
    print("📊 Test Results Summary")
    print("="*70)

    for provider, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {provider}")

    total_passed = sum(results.values())
    total_tests = len(results)

    print(f"\n🎯 Overall: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\n🎉 All live pricing tests passed!")
        print("\n💡 Tip: The UI will show 'realtime' badge when live pricing is used.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        print("    Fallback pricing will be used for failed providers.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
