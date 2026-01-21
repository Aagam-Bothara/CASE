# Security Guide - CASE Optimizer

## 🔒 Credential Management

**IMPORTANT:** This project has been updated to remove all hardcoded credentials. All sensitive information must now be provided via environment variables.

### ⚠️ Critical Security Notice

If you have an older version of this codebase with hardcoded credentials:

1. **Immediately revoke any exposed credentials:**
   - AWS: Delete the IAM user or rotate access keys in IAM console
   - GCP: Delete or regenerate the API key in GCP Console

2. **Never commit credentials to version control**
   - The `.env` file is now in `.gitignore`
   - Use `.env.example` as a template only

3. **Follow the principle of least privilege**
   - Create dedicated service accounts with minimal permissions
   - Use read-only access where possible

---

## 🔐 Setting Up Credentials Securely

### Step 1: Copy the Environment Template

```bash
cp .env.example .env
```

### Step 2: Configure Live Pricing (Optional)

Edit `.env` and enable realtime pricing:

```env
REALTIME_PRICING=1
```

### Step 3: Add Provider Credentials (Optional)

#### AWS Configuration

**Required Permissions:** `pricing:GetProducts` (read-only)

**Setup Steps:**

1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam/)
2. Create a new IAM user: `case-optimizer-pricing`
3. Attach the policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "pricing:GetProducts"
         ],
         "Resource": "*"
       }
     ]
   }
   ```
4. Create access keys and add to `.env`:
   ```env
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   ```

**Security Best Practices:**
- Use a dedicated IAM user (not root account)
- Enable MFA on the IAM account
- Rotate keys every 90 days
- Monitor usage with CloudTrail

#### Azure Configuration

**No credentials required!** Azure Retail Pricing API is public and anonymous.

The application will automatically fetch live Azure pricing without any setup.

#### GCP Configuration

**Required API:** Cloud Billing API

**Setup Steps:**

1. Go to [GCP Console > APIs & Credentials](https://console.cloud.google.com/apis/credentials)
2. Enable the **Cloud Billing API**
3. Create an API Key
4. **Restrict the API key:**
   - API restrictions: Select "Cloud Billing API" only
   - Application restrictions:
     - Set HTTP referrer if web-based
     - Set IP address restrictions if possible
5. Add to `.env`:
   ```env
   GCP_BILLING_API_KEY=AIzaSy...
   ```

**Security Best Practices:**
- Restrict API key to Cloud Billing API only
- Set quotas to prevent abuse
- Monitor usage in GCP Console
- Regenerate key if exposed

---

## 🚀 Running with Live Pricing

### Using Environment Variables Directly

```bash
# Linux/Mac
export REALTIME_PRICING=1
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export GCP_BILLING_API_KEY=AIzaSy...

# Windows (PowerShell)
$env:REALTIME_PRICING=1
$env:AWS_ACCESS_KEY_ID="AKIA..."
$env:AWS_SECRET_ACCESS_KEY="..."
$env:GCP_BILLING_API_KEY="AIzaSy..."

# Start the server
uvicorn serve_frontend:app --port 8001
```

### Using .env File (Recommended)

1. Configure `.env` with your credentials
2. The application automatically loads `.env` on startup
3. Start the server:
   ```bash
   uvicorn serve_frontend:app --port 8001
   ```

---

## 🧪 Testing Live Pricing

Run the verification test to check if credentials are working:

```bash
python test_live_pricing_simple.py
```

Expected output:
```
[PASS]  AWS
[PASS]  Azure
[PASS]  GCP
[PASS]  End-to-End

[RESULT] Overall: 4/4 tests passed
```

---

## 🔍 Troubleshooting

### Live Pricing Not Working

**Check 1: Environment Variables**
```python
import os
print("REALTIME_PRICING:", os.getenv("REALTIME_PRICING"))
print("AWS_ACCESS_KEY_ID:", "SET" if os.getenv("AWS_ACCESS_KEY_ID") else "NOT SET")
print("GCP_BILLING_API_KEY:", "SET" if os.getenv("GCP_BILLING_API_KEY") else "NOT SET")
```

**Check 2: API Permissions**
- AWS: Verify IAM user has `pricing:GetProducts` permission
- GCP: Verify Cloud Billing API is enabled and API key is valid

**Check 3: Fallback Behavior**
If credentials are missing or invalid, the system automatically falls back to stub pricing. This is by design and not an error.

Look for these log messages:
- `"AWS credentials not found in environment variables"` → Add AWS credentials
- `"GCP_BILLING_API_KEY not found"` → Add GCP API key
- `"using fallback rates"` → Credentials invalid or API unavailable

### Cost Estimates Seem Wrong

Live pricing reflects current pay-as-you-go rates and may differ from:
- Reserved instances / savings plans
- Enterprise discounts
- Free tier deductions (partially implemented for GCP)
- Regional variations

Always verify with official cloud pricing calculators for production budgeting.

---

## 📊 Pricing Data Sources

| Provider | Source | Authentication |
|----------|--------|----------------|
| AWS | [AWS Price List API](https://aws.amazon.com/pricing/) | IAM credentials |
| Azure | [Azure Retail Pricing API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) | None (public) |
| GCP | [Cloud Billing Catalog API](https://cloud.google.com/billing/v1/how-tos/catalog-api) | API Key |

---

## 🛡️ Production Deployment Security

### Environment Variables in Production

**Docker:**
```dockerfile
ENV REALTIME_PRICING=1
ENV AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
ENV AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
ENV GCP_BILLING_API_KEY=${GCP_BILLING_API_KEY}
```

**Kubernetes:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: case-optimizer-secrets
type: Opaque
stringData:
  aws-access-key-id: AKIA...
  aws-secret-access-key: ...
  gcp-billing-api-key: AIzaSy...
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: case-optimizer
        env:
        - name: REALTIME_PRICING
          value: "1"
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: case-optimizer-secrets
              key: aws-access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: case-optimizer-secrets
              key: aws-secret-access-key
        - name: GCP_BILLING_API_KEY
          valueFrom:
            secretKeyRef:
              name: case-optimizer-secrets
              key: gcp-billing-api-key
```

**Cloud Platform Secrets:**
- AWS: Use AWS Secrets Manager or Systems Manager Parameter Store
- Azure: Use Azure Key Vault
- GCP: Use Secret Manager

### Credential Rotation

Implement automatic credential rotation:

1. **AWS:** Use IAM credential rotation policies
2. **GCP:** Regenerate API keys quarterly
3. **Application:** Restart service after rotation

---

## 📝 Security Checklist

- [ ] `.env` file is in `.gitignore`
- [ ] No hardcoded credentials in source code
- [ ] IAM users have minimal required permissions
- [ ] API keys are restricted (IP/HTTP referrer/API scope)
- [ ] MFA enabled on cloud accounts
- [ ] Credentials rotated regularly (90 days)
- [ ] Monitoring/logging enabled for API access
- [ ] `.env.example` documented for team members
- [ ] Production secrets use platform secret managers
- [ ] Test with `test_live_pricing_simple.py` passes

---

## 🆘 Support

If you discover a security vulnerability, please email the maintainers privately rather than opening a public issue.

For configuration questions, check the logs for detailed error messages indicating which credentials are missing.
