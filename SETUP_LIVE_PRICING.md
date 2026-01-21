# Live Pricing Setup - Quick Start Guide

## 🎯 Overview

CASE Optimizer supports **live pricing** from AWS, Azure, and GCP APIs. When enabled, it fetches real-time pay-as-you-go rates instead of using fallback estimates.

## ⚡ Quick Setup (3 Steps)

### 1. Copy Environment Template

```bash
cp .env.example .env
```

### 2. Enable Live Pricing

Edit `.env`:
```env
REALTIME_PRICING=1
```

### 3. Add Credentials (Optional)

#### AWS (Optional)
Create an IAM user with `pricing:GetProducts` permission:
```env
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

#### Azure (No Setup Required)
Azure pricing API is public - no credentials needed! ✅

#### GCP (Optional)
Create an API key with Cloud Billing API access:
```env
GCP_BILLING_API_KEY=AIzaSy...
```

## 🚀 Start the Server

```bash
# Start backend
uvicorn serve_frontend:app --port 8001 --reload

# Start frontend (in another terminal)
cd frontend
npm run dev
```

## ✅ Verify Live Pricing

```bash
python test_live_pricing_simple.py
```

Expected output:
```
[PASS]  AWS
[PASS]  Azure
[PASS]  GCP
[PASS]  End-to-End

[SUCCESS] All live pricing tests passed!
```

## 📊 How to Tell if Live Pricing is Active

### In the UI
Look for the **pricing badge** in the "All Evaluations" table:
- `realtime` badge = Live pricing ✅
- `fallback` badge = Using estimates
- `stub-evaluator` badge = Using stub estimates

### In Test Results
When you run a plan, the evaluation results will show:
```
[LIVE]       AZURE    | container-apps   | $  245.59/mo
```

## 🔄 Fallback Behavior

**By Design:** If credentials are missing or API calls fail, the system automatically falls back to stub pricing. This ensures the application always works, even without credentials.

You'll see these warnings in logs:
```
AWS credentials not found in environment variables - using fallback rates
GCP_BILLING_API_KEY not found - using fallback rates
```

## 💡 Provider Comparison

| Provider | Setup Required | Authentication | Public API |
|----------|----------------|----------------|------------|
| **Azure** | ✅ None | ✅ None | ✅ Yes |
| **GCP** | API Key | API Key only | ✅ Yes |
| **AWS** | IAM User | Access Key + Secret | ❌ No |

**Recommendation:** Start with Azure (no setup) and GCP (easy API key), then add AWS if needed.

## 🛠️ Troubleshooting

### "Using fallback rates" Warning

**Cause:** Credentials not found or REALTIME_PRICING not enabled

**Fix:**
```bash
# Check if environment variables are loaded
python -c "import os; print('REALTIME:', os.getenv('REALTIME_PRICING'))"

# Verify credentials are set
python -c "import os; print('AWS:', 'SET' if os.getenv('AWS_ACCESS_KEY_ID') else 'NOT SET')"
```

### AWS "boto3 not installed"

**Fix:**
```bash
pip install boto3
```

### GCP "API key invalid"

**Fix:**
1. Verify Cloud Billing API is enabled in GCP Console
2. Check API key restrictions aren't blocking requests
3. Regenerate the API key if needed

### Azure Rate Limiting (429 Errors)

**Cause:** Azure Retail API has rate limits (~15 requests/sec)

**Fix:** The application automatically retries with exponential backoff. Just wait a few seconds.

## 📚 Detailed Documentation

For complete security guidelines, credential setup, and production deployment:
- See [SECURITY.md](./SECURITY.md) for full documentation
- See [.env.example](./.env.example) for configuration template

## 🎉 Example Results

With live pricing enabled, you'll see real costs:

```
Top 3 Recommendations:
🥇 #1  AZURE    | container-apps  | blob           | $  245.59/mo  | Score: 85.2
🥈 #2  AWS      | fargate         | s3             | $  653.88/mo  | Score: 72.1
🥉 #3  GCP      | cloud-run       | gcs            | $1,051.20/mo  | Score: 68.5

[LIVE] All 3 bundles using realtime pricing ✓
```

vs fallback estimates:

```
[FALLBACK] AWS      | fargate         | s3             | $  180.50/mo
[FALLBACK] AZURE    | container-apps  | blob           | $  120.75/mo
[FALLBACK] GCP      | cloud-run       | gcs            | $   95.40/mo
```

Live pricing provides more accurate, up-to-date costs for better decision-making!

---

**Need Help?** Check the logs for detailed error messages or run `python test_live_pricing_simple.py` to diagnose issues.
