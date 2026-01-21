# CASE Optimizer

**Cloud Architecture Selection Engine** - An intelligent platform for comparing and selecting optimal cloud architectures across AWS, Azure, and GCP.

<div align="center">

![CASE Optimizer](https://img.shields.io/badge/Cloud-Multi--Platform-blue)
![Pricing](https://img.shields.io/badge/Pricing-Real--time-green)
![License](https://img.shields.io/badge/license-MIT-blue)

</div>

---

## 🚀 Overview

CASE Optimizer is a decision support tool that helps developers and architects choose the best cloud platform and services for their workload. It evaluates AWS, Azure, and GCP based on:

- **Real-time Pricing** from official cloud APIs
- **Performance Modeling** (latency, availability, throughput)
- **Policy Constraints** (budget, compliance, vendor preferences)
- **CLIPS Rules Engine** for architectural pattern matching
- **Terraform Generation** for infrastructure as code

Unlike traditional cloud calculators, CASE Optimizer:
- ✅ Fetches live pricing data (not estimates)
- ✅ Considers performance and SLA requirements
- ✅ Validates policy constraints (HIPAA, PCI-DSS, budget)
- ✅ Generates ready-to-deploy Terraform configurations
- ✅ Provides side-by-side comparisons with detailed breakdowns

---

## 📊 Features

### 🎯 Smart Recommendations
- **Multi-Cloud Comparison**: AWS, Azure, and GCP evaluated simultaneously
- **Ranked Results**: Bundles scored and sorted by cost-performance ratio
- **Constraint Validation**: Automatic checks for budget, latency, compliance
- **Interactive UI**: Modern React interface with expandable cost breakdowns

### 💰 Live Pricing Integration
- **AWS**: Price List API with boto3 (requires IAM credentials)
- **Azure**: Retail Pricing API (public, no auth required)
- **GCP**: Cloud Billing Catalog API (requires API key)
- **Fallback Mode**: Stub pricing when credentials unavailable

### 🏗️ Terraform Generation
- **Infrastructure as Code**: Generate Terraform configurations from recommendations
- **Multi-Provider**: Supports AWS, Azure, GCP provider syntax
- **Resource Types**: Compute, storage, networking, IAM
- **Outputs**: Cost estimates, endpoints, resource IDs

### 🔒 Security & Compliance
- **Environment Variables**: No hardcoded credentials
- **Gitignore Protection**: `.env` files never committed
- **Compliance Checks**: HIPAA, PCI-DSS, SOC2 validation
- **Vendor Exclusions**: Policy-based provider filtering

---

## 🛠️ Tech Stack

### Backend
- **FastAPI**: High-performance async Python web framework
- **Python 3.10+**: Modern async/await syntax
- **CLIPS**: Expert system for rule-based reasoning
- **Pydantic**: Data validation and type checking

### Frontend
- **React 18**: Modern component-based UI
- **Vite**: Fast build tooling and hot module replacement
- **CSS3**: Custom animations, gradients, responsive design

### Cloud APIs
- **AWS Pricing API**: boto3 client
- **Azure Retail API**: REST with pagination
- **GCP Billing API**: REST with caching

---

## 📦 Installation

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** (for frontend)
- **Git**

### 1. Clone the Repository
```bash
git clone https://github.com/Aagam-Bothara/CASE.git
cd CASE
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

### 4. Configure Environment Variables (Optional)
```bash
cp .env.example .env
```

Edit `.env` to enable live pricing:
```env
# Enable live pricing (1 = enabled, 0 = disabled)
REALTIME_PRICING=1

# AWS Credentials (Optional)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# GCP API Key (Optional)
GCP_BILLING_API_KEY=AIzaSy...

# Server Configuration
PORT=8001
ENV=development
LOG_LEVEL=INFO
```

**Note**: Azure pricing requires no credentials. AWS and GCP are optional - the system uses fallback pricing if credentials are missing.

---

## 🚀 Quick Start

### 1. Start the Backend
```bash
uvicorn serve_frontend:app --reload --port 8001
```

The API will be available at `http://localhost:8001`

### 2. Start the Frontend (in a new terminal)
```bash
cd frontend
npm run dev
```

The UI will open at `http://localhost:5173`

### 3. Test Live Pricing (Optional)
```bash
python test_live_pricing_simple.py
```

Expected output:
```
[PASS]  AWS      - vCPU: $0.00001124/sec
[PASS]  Azure    - vCPU: $0.00000300/sec
[PASS]  GCP      - vCPU: $0.00001800/sec
[PASS]  End-to-End - All 3 bundles using REALTIME pricing

[SUCCESS] All live pricing tests passed!
```

---

## 💡 Usage

### Web Interface

1. **Open the UI**: Navigate to `http://localhost:5173`
2. **Fill Workload Form**:
   - Traffic (requests/sec)
   - Execution time (ms)
   - Memory (GB)
   - Storage requirements
   - Performance targets (P95 latency)
   - Policy constraints (budget, compliance)

3. **Generate Plan**: Click "Generate Plan" to evaluate all bundles
4. **View Results**: See ranked recommendations with:
   - 🏆 Winner badge for best option
   - 💰 Monthly cost with breakdown
   - 📊 Performance metrics (P95, availability)
   - 🎯 Policy compliance status
   - 📋 Terraform code preview

5. **Export Terraform**: Click "View Terraform" to see IaC configuration

### API Endpoints

#### Health Check
```bash
curl http://localhost:8001/health
```

Response:
```json
{"status": "healthy"}
```

#### Generate Recommendations
```bash
curl -X POST http://localhost:8001/api/plan \
  -H "Content-Type: application/json" \
  -d '{
    "traffic_rps": 100,
    "avg_exec_ms": 200,
    "mem_gb": 2,
    "storage_gb_hot": 50,
    "p95_target_ms": 300,
    "budget_monthly": 500
  }'
```

Response:
```json
{
  "bundles": [
    {
      "vendor": "azure",
      "compute_service": "container-apps",
      "storage_service": "blob",
      "feasible": "yes",
      "monthly_cost": 245.59,
      "p95_ms": 89.0,
      "availability": 99.95,
      "reason": "realtime",
      "cost_breakdown": {...}
    },
    ...
  ]
}
```

---

## 🔐 Live Pricing Setup

### Azure (No Setup Required)
Azure Retail Pricing API is public and requires no credentials. CASE automatically fetches live pricing for:
- Container Apps (vCPU, memory)
- Blob Storage (Hot LRS)

### AWS (Optional)
Requires IAM credentials with `pricing:GetProducts` permission.

**Setup Steps:**
1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam/)
2. Create a new IAM user: `case-optimizer-pricing`
3. Attach this policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["pricing:GetProducts"],
       "Resource": "*"
     }]
   }
   ```
4. Create access keys and add to `.env`:
   ```env
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   ```

### GCP (Optional)
Requires an API key with Cloud Billing API access.

**Setup Steps:**
1. Go to [GCP Console > APIs & Credentials](https://console.cloud.google.com/apis/credentials)
2. Enable **Cloud Billing API**
3. Create an API Key
4. Restrict the key to Cloud Billing API only
5. Add to `.env`:
   ```env
   GCP_BILLING_API_KEY=AIzaSy...
   ```

### Verify Live Pricing
Run the test suite:
```bash
python test_live_pricing_simple.py
```

Check the UI - look for the **pricing badge**:
- `realtime` = Live pricing ✅
- `fallback` = Using estimates
- `stub-evaluator` = Using stub pricing (REALTIME_PRICING=0)

---

## 📁 Project Structure

```
CASE/
├── evaluator/
│   ├── app.py              # FastAPI application
│   ├── pricing.py          # Live pricing logic
│   ├── stub.py             # Fallback evaluator
│   ├── providers/
│   │   ├── aws.py          # AWS Pricing API
│   │   ├── azure.py        # Azure Retail API
│   │   └── gcp.py          # GCP Billing API
│   └── utils.py            # Caching, HTTP helpers
├── frontend/
│   ├── src/
│   │   ├── App.jsx         # Main React app
│   │   ├── components/
│   │   │   ├── WorkloadForm.jsx
│   │   │   ├── Results.jsx
│   │   │   └── Simulator.jsx
│   │   ├── utils/
│   │   │   └── terraform.js  # Terraform generation
│   │   ├── api.js          # API client
│   │   └── styles.css      # Modern UI styles
│   ├── index.html
│   └── vite.config.js
├── orchestrator.py         # CLIPS rules engine wrapper
├── rules.clp               # CLIPS rule definitions
├── serve_frontend.py       # Serves static frontend
├── requirements.txt        # Python dependencies
├── package.json            # Node.js dependencies
├── .env.example            # Environment template
├── .gitignore              # Git exclusions
├── README.md               # This file
├── SECURITY.md             # Security guidelines
├── SETUP_LIVE_PRICING.md   # Detailed pricing setup
└── test_live_pricing_simple.py  # Automated tests
```

---

## 🧪 Testing

### Unit Tests
```bash
# Test live pricing
python test_live_pricing_simple.py

# Test Terraform generation
open test_terraform_generator.html
```

### Manual Testing
1. Start backend and frontend
2. Submit a workload with:
   - Traffic: 100 RPS
   - Execution: 200ms
   - Memory: 2GB
   - Budget: $500/month
3. Verify:
   - All 3 cloud providers evaluated
   - Costs are realistic (Azure ~$200-300, AWS ~$600-700, GCP ~$1000-1200)
   - Winner badge appears on lowest cost option
   - Terraform code generates correctly
   - Pricing badge shows "realtime" (if REALTIME_PRICING=1)

---

## 🔍 Troubleshooting

### "STUB-EVALUATOR" Showing in UI

**Cause**: `REALTIME_PRICING` environment variable not set or not detected.

**Fix**:
```bash
# Check if environment variable is loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('REALTIME:', os.getenv('REALTIME_PRICING'))"

# Should output: REALTIME: 1

# If not, ensure .env exists and contains:
echo "REALTIME_PRICING=1" > .env

# Restart the backend server
# Kill existing server (Ctrl+C)
uvicorn serve_frontend:app --reload --port 8001

# Refresh browser (Ctrl+Shift+R to clear cache)
```

### AWS "boto3 not installed"
```bash
pip install boto3
```

### GCP "API key invalid"
1. Verify Cloud Billing API is enabled in GCP Console
2. Check API key restrictions aren't blocking requests
3. Regenerate the API key if needed

### Azure Rate Limiting (429 Errors)
Azure Retail API has rate limits (~15 requests/sec). The application automatically retries with exponential backoff. Wait a few seconds and try again.

### Frontend Not Loading
```bash
# Ensure frontend is built
cd frontend
npm run build
cd ..

# Restart backend (serves static files)
uvicorn serve_frontend:app --reload --port 8001
```

---

## 🛡️ Security

### Credential Management
- ✅ All credentials loaded from environment variables
- ✅ No hardcoded API keys or secrets
- ✅ `.env` file in `.gitignore`
- ✅ `.env.example` as non-sensitive template

### Best Practices
- Use dedicated service accounts with minimal permissions
- Enable MFA on cloud accounts
- Rotate credentials every 90 days
- Monitor API usage in cloud consoles
- Use platform secret managers in production (AWS Secrets Manager, Azure Key Vault, GCP Secret Manager)

See [SECURITY.md](SECURITY.md) for complete guidelines.

---

## 📚 Documentation

- **[SECURITY.md](SECURITY.md)**: Complete security guide, credential setup, production deployment
- **[SETUP_LIVE_PRICING.md](SETUP_LIVE_PRICING.md)**: Quick start for enabling live pricing
- **[CHANGELOG_SECURITY.md](CHANGELOG_SECURITY.md)**: Security update history

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m "Add my feature"`
4. Push to branch: `git push origin feature/my-feature`
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guide for Python
- Use ESLint/Prettier for JavaScript
- Add tests for new features
- Update documentation

---

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Aagam Bothara**

- GitHub: [@Aagam-Bothara](https://github.com/Aagam-Bothara)
- Repository: [CASE](https://github.com/Aagam-Bothara/CASE)

---

## 🙏 Acknowledgments

- **AWS, Azure, GCP**: For providing public pricing APIs
- **CLIPS**: Expert system shell for rule-based reasoning
- **FastAPI**: High-performance Python web framework
- **React**: Component-based UI library
- **Vite**: Next-generation frontend tooling

---

## 📈 Roadmap

### v1.1 (Upcoming)
- [ ] Support for Kubernetes workloads (EKS, AKS, GKE)
- [ ] Database pricing (RDS, Azure SQL, Cloud SQL)
- [ ] Multi-region deployment modeling
- [ ] Reserved instances / savings plans
- [ ] Carbon footprint estimation

### v1.2 (Future)
- [ ] Cost optimization recommendations
- [ ] Slack/Discord notifications
- [ ] API rate limiting and authentication
- [ ] User accounts and saved plans
- [ ] Export to PDF/Excel

---

## 🐛 Known Issues

1. **AWS Pricing API Latency**: First call can take 5-10 seconds (uses pagination)
2. **Azure Rate Limits**: Aggressive requests may hit 429 errors (auto-retry implemented)
3. **GCP Free Tier**: Not fully implemented (may show higher costs for low-traffic workloads)

---

## ❓ FAQ

**Q: Do I need cloud credentials to use CASE?**
A: No! Azure pricing works without credentials. AWS and GCP are optional - the system uses fallback pricing if credentials are missing.

**Q: Are the prices accurate?**
A: Live pricing reflects current pay-as-you-go rates. It doesn't include reserved instances, enterprise discounts, or free tier deductions. Always verify with official cloud calculators for production budgeting.

**Q: Can I deploy the generated Terraform?**
A: Yes, but review and customize it first. The generated code is a starting point and may need adjustments for your specific requirements (networking, IAM, monitoring, etc.).

**Q: How often is pricing data updated?**
A: Live pricing is fetched on every request. Results are cached for 12 hours to reduce API calls.

**Q: Does CASE store my workload data?**
A: No, all evaluations are stateless. No data is persisted to disk or databases.

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Aagam-Bothara/CASE/issues)
- **Setup Help**: See [SETUP_LIVE_PRICING.md](SETUP_LIVE_PRICING.md)
- **Security**: See [SECURITY.md](SECURITY.md)

---

<div align="center">

**Built with ❤️ for cloud architects and developers**

[⭐ Star this repo](https://github.com/Aagam-Bothara/CASE) | [🐛 Report Bug](https://github.com/Aagam-Bothara/CASE/issues) | [✨ Request Feature](https://github.com/Aagam-Bothara/CASE/issues)

</div>
