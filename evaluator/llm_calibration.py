"""
LLM-based cost calibration using GPT-4 with comprehensive pricing knowledge.

Replaces traditional ML with LLM reasoning that:
1. Understands cloud pricing models
2. Validates cost estimates
3. Provides detailed explanations
4. Handles edge cases naturally
"""

import os
import json
from typing import Dict, Tuple
from openai import OpenAI

# Initialize OpenAI client
client = None

def get_openai_client():
    """Get or create OpenAI client."""
    global client
    if client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("[LLM] Warning: OPENAI_API_KEY not set, LLM calibration disabled")
            return None
        client = OpenAI(api_key=api_key)
    return client


PRICING_KNOWLEDGE = """
# Cloud Pricing Reference (2024-2026)

## Core Compute Pricing

### AWS
- **Fargate**: $0.04048/vCPU-hour, $0.004445/GB-hour
- **Lambda**: $0.20 per 1M requests + $0.0000166667/GB-second
- **EC2 t3.medium**: ~$30/month (on-demand)

### Azure
- **Container Apps**: $0.000003/vCPU-second, $0.000003/GB-second
- **Functions**: $0.20 per 1M executions + $0.000016/GB-second
- **VMs B2s**: ~$30/month

### GCP
- **Cloud Run**: $0.00002400/vCPU-second, $0.00000250/GB-second
- **Cloud Functions**: $0.40 per 1M invocations + $0.0000025/GB-second

## Storage Pricing

### Object Storage
- **S3 Standard**: $0.023/GB-month
- **Azure Blob**: $0.0184/GB-month
- **GCS Standard**: $0.020/GB-month

### Database Storage
- **RDS/SQL Database/Cloud SQL**: $0.10-0.25/GB-month (varies by tier)
- **Managed databases include compute + storage**

## Infrastructure Components

### Cache/Redis
- **Basic tier (1GB)**: $15-20/month
- **Standard tier (5GB)**: $50-70/month
- **Premium tier (20GB+)**: $200+/month

### CDN
- **CloudFront/Azure CDN/Cloud CDN**:
  - Base: ~$10/month minimum
  - Transfer: $0.085/GB outbound

### Monitoring
- **Basic (CloudWatch/Azure Monitor)**: $5-10/month
- **Enhanced APM**: $15-25/month
- **Full observability**: $50+/month

### Security
- **WAF**: $5-10/month base + $1/million requests
- **DDoS Protection**: Included basic, $30-50/month advanced

## Service Selection Heuristics

### When to use serverless (Lambda/Functions):
- <10 RPS with sporadic traffic
- Event-driven workloads
- Batch/background jobs (<1000/day)
- Cost: $1-50/month typically

### When to use containers (Fargate/Container Apps):
- 10-500 RPS steady traffic
- Scale-to-zero capable
- Web APIs, microservices
- Cost: $20-500/month typically

### When to use VMs/dedicated:
- >500 RPS constant traffic
- Specialized workloads (ML, databases)
- Need for specific OS/kernel
- Cost: $50-5000+/month

## Infrastructure Requirements by Traffic

### Low traffic (<10 RPS):
- Compute: Scale-to-zero serverless
- Storage: Managed database (included)
- Cache: Not needed
- CDN: Not needed
- Monitoring: Basic
- **Typical: $5-50/month**

### Medium traffic (10-100 RPS):
- Compute: Container Apps scale-to-zero OR always-on small instance
- Storage: Dedicated database instance
- Cache: Maybe (if read-heavy)
- CDN: Maybe (if static assets)
- Monitoring: Basic to enhanced
- **Typical: $50-400/month**

### High traffic (100-500 RPS):
- Compute: Always-on containers (2-4 vCPU)
- Storage: Dedicated database with replicas
- Cache: Required (Redis standard)
- CDN: Required
- Monitoring: Enhanced APM
- Security: WAF recommended
- **Typical: $300-2000/month**

### Very high traffic (>500 RPS):
- Compute: Multiple instances, auto-scaling
- Storage: High-performance database tier
- Cache: Redis premium, possibly multi-tier
- CDN: Required with optimization
- Monitoring: Full observability
- Security: WAF + DDoS protection
- **Typical: $2000-10000+/month**

## Common Pricing Mistakes to Avoid

1. **Forgetting infrastructure costs**: Cache, monitoring, security add 30-50% on top
2. **Overestimating scale-to-zero savings**: Only works for truly sporadic traffic
3. **Underestimating storage**: Backups, replicas, logs add up
4. **Ignoring data transfer**: Can be 10-20% of total cost for high traffic
5. **Not accounting for monitoring**: Production needs APM, not just basic metrics

## Realistic Benchmarks

- **Seed startup API (5 RPS)**: $15-40/month
- **Early stage product (50 RPS)**: $80-200/month
- **Growth stage API (200 RPS)**: $280-800/month
- **Series A SaaS (500 RPS)**: $900-2500/month
- **Production multi-tenant (1000+ RPS)**: $2000-8000/month
- **Background jobs (hourly)**: $12-30/month (includes database + monitoring)
- **Compliance workloads**: 1.5-2x base cost (enhanced security/logging)
- **Multi-region deployments**: 1.2-1.3x base cost (data transfer + replication)
"""


def calibrate_cost_with_llm(workload: Dict, base_cost: float, vendor: str, service: str) -> Tuple[float, str]:
    """
    Use LLM to validate and calibrate cost estimate.

    Args:
        workload: Workload specification
        base_cost: Initial cost estimate from calculation
        vendor: Cloud vendor (aws, azure, gcp)
        service: Compute service (fargate, container-apps, etc.)

    Returns:
        (calibrated_cost, explanation)
    """

    llm_client = get_openai_client()
    if not llm_client:
        # Fall back to no calibration if LLM not available
        return base_cost, "LLM not available, using base cost"

    # Build workload summary
    workload_type = workload.get("workload_type", "api")
    rps = workload.get("traffic_rps", 0)
    jobs_per_day = workload.get("jobs_per_day", 0)
    storage_gb = workload.get("storage_gb_hot", 0)
    cpu_vcpu = workload.get("cpu_vcpu", 1)
    mem_gb = workload.get("mem_gb", 2)
    environment = workload.get("environment", "production")

    # Traffic indicator
    if rps > 0:
        traffic_desc = f"{rps} requests/second"
    elif jobs_per_day > 0:
        traffic_desc = f"{jobs_per_day} jobs/day"
    else:
        traffic_desc = "minimal/sporadic"

    prompt = f"""You are a cloud cost expert validating a calculated estimate. Be CONSERVATIVE - only adjust if clearly wrong.

CALCULATED ESTIMATE: ${base_cost:.2f}/month
(This already includes: compute, storage, database, load balancer, and package-specific infrastructure)

WORKLOAD:
- Type: {workload_type}
- Traffic: {traffic_desc}
- Resources: {cpu_vcpu} vCPU, {mem_gb} GB RAM, {storage_gb} GB storage
- Environment: {environment}
- Service: {vendor} {service}

PRICING BENCHMARKS:
{PRICING_KNOWLEDGE}

VALIDATION RULES:
1. Check if ${base_cost:.2f} matches these benchmarks:
   - Low traffic (<10 RPS): $15-50/month
   - Medium traffic (50-100 RPS): $80-250/month
   - High traffic (200-500 RPS): $280-900/month
   - Background jobs: $12-30/month minimum

2. WHEN TO ADJUST:
   - If base cost is <$5 for ANY production workload → adjust UP to $15 minimum
   - If base cost is clearly outside benchmark range (>50% off) → adjust to middle of range
   - If base cost seems reasonable (within 30% of benchmark) → KEEP IT as-is

3. WHEN NOT TO ADJUST:
   - Base cost is already in the reasonable range
   - Base cost already accounts for traffic/complexity
   - You're unsure - err on the side of keeping base cost

4. DO NOT:
   - Add blanket +30% overhead (infrastructure is already included!)
   - Over-correct reasonable estimates
   - Adjust based on "might need" - only adjust for "definitely needs"

Return ONLY valid JSON:
{{
  "calibrated_cost": <number>,
  "reasoning": "<1-2 sentences explaining why you kept or adjusted>",
  "confidence": "<high|medium|low>"
}}
"""

    try:
        response = llm_client.chat.completions.create(
            model="gpt-4o",  # Best quality (o1-preview doesn't support system messages yet)
            messages=[
                {
                    "role": "system",
                    "content": "You are a cloud cost expert specializing in accurate production cost estimation. Return only valid JSON, no markdown formatting. Be aggressive in identifying missing costs."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,  # Low temperature for consistency
            max_tokens=500,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        calibrated_cost = float(result.get("calibrated_cost", base_cost))
        reasoning = result.get("reasoning", "No explanation provided")
        confidence = result.get("confidence", "medium")

        # Log the calibration
        print(f"[LLM] Base: ${base_cost:.2f} -> Calibrated: ${calibrated_cost:.2f} ({confidence} confidence)")
        print(f"[LLM] Reasoning: {reasoning}")

        return calibrated_cost, reasoning

    except Exception as e:
        print(f"[LLM] Error during calibration: {e}")
        # Fall back to base cost on error
        return base_cost, f"Error during LLM calibration: {str(e)}"


def explain_cost_breakdown(workload: Dict, cost_breakdown: Dict, total_cost: float) -> str:
    """
    Generate human-readable explanation of cost breakdown using LLM.

    Args:
        workload: Workload specification
        cost_breakdown: Dictionary of cost components
        total_cost: Total monthly cost

    Returns:
        Human-readable explanation
    """

    llm_client = get_openai_client()
    if not llm_client:
        # Fall back to simple breakdown
        parts = [f"- {k}: ${v:.2f}" for k, v in cost_breakdown.items()]
        return "Cost breakdown:\n" + "\n".join(parts)

    prompt = f"""Explain this cloud cost estimate in simple terms.

WORKLOAD:
- Type: {workload.get('workload_type')}
- Traffic: {workload.get('traffic_rps', 0)} RPS
- Storage: {workload.get('storage_gb_hot', 0)} GB

COST BREAKDOWN:
{json.dumps(cost_breakdown, indent=2)}

TOTAL: ${total_cost:.2f}/month

Provide a brief (2-3 sentence) explanation that:
1. Identifies the main cost drivers
2. Mentions if this is typical for this workload
3. Suggests one optimization if cost seems high

Return plain text (no markdown, no formatting).
"""

    try:
        response = llm_client.chat.completions.create(
            model="gpt-4o-mini",  # Faster for explanations
            messages=[
                {
                    "role": "system",
                    "content": "You are a cloud cost expert explaining costs to developers."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=200
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[LLM] Error generating explanation: {e}")
        parts = [f"- {k}: ${v:.2f}" for k, v in cost_breakdown.items()]
        return "Cost breakdown:\n" + "\n".join(parts)
