from typing import Dict, List, Any
from enum import Enum
import clips

class CaseEngine:
    def __init__(self, rules_path: str = "rules.clp"):
        self.rules_path = rules_path

    def _safe_assert(self, env: clips.Environment, template_name: str, data: Dict[str, Any]):
        """
        Safely inserts a dictionary into a CLIPS template.
        """
        try:
            template = env.find_template(template_name)
        except clips.ClipsError:
            print(f"Warning: Template '{template_name}' not found in CLIPS.")
            return

        if template is None:
            print(f"Warning: Template '{template_name}' not found in CLIPS.")
            return

        # --- figure out the slot names in a robust way ---
        slot_names = set()
        try:
            slot_names = set(template.slots.keys())
        except AttributeError:
            try:
                slot_names = set(name for name, _ in template.slots)
            except Exception:
                try:
                    slot_names = set(s.name for s in template.slots)
                except Exception:
                    slot_names = set(data.keys())

        cleaned: Dict[str, Any] = {}

        for k, v in data.items():
            if k not in slot_names:
                continue
            if v is None:
                continue

            # Handle Enums
            if isinstance(v, Enum):
                v = v.value

            # Special case: candidate_eval.feasible -> yes/no symbol
            if template_name == "candidate_eval" and k == "feasible":
                if isinstance(v, bool):
                    cleaned[k] = clips.Symbol("yes" if v else "no")
                    continue
                s = str(v).strip().lower()
                if s in ("yes", "true", "1"):
                    cleaned[k] = clips.Symbol("yes")
                elif s in ("no", "false", "0"):
                    cleaned[k] = clips.Symbol("no")
                else:
                    cleaned[k] = clips.Symbol(s)
                continue

            # Normal fields:
            if isinstance(v, (int, float)):
                cleaned[k] = v
            else:
                cleaned[k] = clips.Symbol(str(v))

        # --- assert the fact ---
        if hasattr(template, "assert_fact"):
            return template.assert_fact(**cleaned)

        fact = template.new_fact()
        for key, val in cleaned.items():
            fact[key] = val
        fact.assertit()
        return fact

    def _facts(self, env: clips.Environment, template_name: str):
        """Yields all facts matching a specific template name."""
        for f in env.facts():
            if f.template.name == template_name:
                yield f

    def _bundle_pairs_same_vendor(self, env: clips.Environment) -> List[Dict]:
        """
        Creates bundles by matching Compute and Storage candidates from the SAME vendor.
        Includes a FAILSAFE to ensure we don't return blank results if storage is missing.
        """
        computes = [f for f in self._facts(env, "candidate") if f["role"] == "compute"]
        storages = [f for f in self._facts(env, "candidate") if f["role"] == "storage"]

        # --- FAILSAFE START ---
        # If CLIPS didn't find any storage (or user selected None), create dummy entries
        # so the loop below doesn't return 0 results.
        if not storages:
            storages = [
                {"vendor": "aws", "service": "none", "notes": "No storage"},
                {"vendor": "azure", "service": "none", "notes": "No storage"},
                {"vendor": "gcp", "service": "none", "notes": "No storage"}
            ]
        # --- FAILSAFE END ---

        bundles: List[Dict[str, Any]] = []
        for c in computes:
            for s in storages:
                # 1. Vendor must match (AWS compute needs AWS storage)
                # 2. OR if storage is "none", it works with anything
                c_vendor = str(c["vendor"])
                s_vendor = str(s["vendor"]) if "vendor" in s else "none"
                s_service = str(s["service"]) if "service" in s else "none"
                s_notes = str(s["notes"]) if "notes" in s else ""
                
                # Normalize dummy dicts vs CLIPS facts
                if isinstance(s, dict):
                    s_vendor = s["vendor"]
                    s_service = s["service"]
                    s_notes = s["notes"]

                if c_vendor == s_vendor or s_service == "none":
                    bundles.append({
                        "vendor": c_vendor,
                        "compute_service": str(c["service"]),
                        "storage_service": s_service,
                        "notes": f"{str(c['notes'])} + {s_notes}",
                    })
        return bundles

    def candidates(self, workload: Dict):
        """
        Phase 1: Determine valid architectural candidates (Bundles).
        """
        env = clips.Environment()
        try:
            env.load(self.rules_path)
        except clips.ClipsError as e:
            print(f"CLIPS Syntax Error: {e}")
            raise

        env.reset()

        # Assert workload into CLIPS
        self._safe_assert(env, "workload", workload)

        # Run constraint + pattern + mapping rules
        env.run()

        compute = [{
            "vendor": str(f["vendor"]),
            "service": str(f["service"]),
            "notes": str(f["notes"]),
        } for f in self._facts(env, "candidate") if f["role"] == "compute"]

        storage = [{
            "vendor": str(f["vendor"]),
            "service": str(f["service"]),
            "notes": str(f["notes"]),
        } for f in self._facts(env, "candidate") if f["role"] == "storage"]

        bundles = self._bundle_pairs_same_vendor(env)
        whys = [str(w["msg"]) for w in self._facts(env, "why")]

        return {
            "compute": compute,
            "storage": storage,
            "bundles": bundles,
            "why": whys,
        }

    def _calculate_score_breakdown(self, eval_dict: Dict, vendor_pref: str, max_cost: float, max_p95: float) -> Dict:
        """Calculate normalized scores for an evaluation."""
        cost = eval_dict.get("monthly_cost", 0.0)
        p95 = eval_dict.get("p95_ms", 0.0)
        vendor = eval_dict.get("vendor", "")

        # Cost score: inverse normalized (lower is better, scaled 0-100)
        cost_score = round(100 * (1 - (cost / max_cost)) if max_cost > 0 else 100, 2)

        # Performance score: inverse normalized (lower latency is better, scaled 0-100)
        perf_score = round(100 * (1 - (p95 / max_p95)) if max_p95 > 0 else 100, 2)

        # Preference score: binary 100 or 0
        pref_score = 100 if (vendor_pref != "none" and vendor == vendor_pref) else 0

        # Composite score: weighted average (Cost: 50%, Perf: 30%, Pref: 20%)
        composite = round(cost_score * 0.5 + perf_score * 0.3 + pref_score * 0.2, 2)

        return {
            "composite": composite,
            "cost_score": cost_score,
            "perf_score": perf_score,
            "preference_score": pref_score
        }

    def run_with_evals(self, workload: Dict, evals: List[Dict]):
        """
        Phase 2: Assert evaluated results (Cost/P95/etc.) and pick top 3 winners.
        """
        env = clips.Environment()
        env.load(self.rules_path)
        env.reset()

        # 1. Re-assert workload (context for preference rules)
        self._safe_assert(env, "workload", workload)

        # 2. Assert evaluations as candidate_eval facts
        for e in evals:
            self._safe_assert(env, "candidate_eval", e)

        # 3. Run final recommendation rules
        env.run()

        # Get vendor preference
        vendor_pref = workload.get("vendor_preference", "none")

        # Calculate max values for normalization
        feasible_evals = [e for e in evals if e.get("feasible") == "yes"]
        max_cost = max([e.get("monthly_cost", 0.0) for e in feasible_evals], default=1.0)
        max_p95 = max([e.get("p95_ms", 0.0) for e in feasible_evals], default=1.0)

        # Get top 3 using CLIPS function
        top3_facts = []
        try:
            top3_result = env.eval("(top3-feasible-evals-with-pref " + vendor_pref + ")")
            # Extract facts from multifield
            for i, item in enumerate(top3_result):
                if hasattr(item, '__getitem__'):  # It's a fact
                    top3_facts.append(item)
        except Exception as e:
            print(f"Warning: Could not get top3 from CLIPS: {e}")
            # Fallback: sort feasible evals manually
            scored_evals = []
            for e in feasible_evals:
                scores = self._calculate_score_breakdown(e, vendor_pref, max_cost, max_p95)
                scored_evals.append((e, scores["composite"]))
            scored_evals.sort(key=lambda x: x[1], reverse=True)
            top3_facts = [e[0] for e in scored_evals[:3]]

        # Build top3 list with score breakdowns
        top3 = []
        for fact_or_dict in top3_facts:
            if hasattr(fact_or_dict, '__getitem__'):
                # It's a CLIPS fact - need to find the original eval dict to get cost_breakdown
                eval_data = None
                for e in evals:
                    if (str(e.get("vendor")) == str(fact_or_dict["vendor"]) and
                        str(e.get("compute_service")) == str(fact_or_dict["compute_service"]) and
                        str(e.get("storage_service")) == str(fact_or_dict["storage_service"])):
                        eval_data = e
                        break

                if not eval_data:
                    # Fallback if not found
                    eval_data = {
                        "vendor": str(fact_or_dict["vendor"]),
                        "compute_service": str(fact_or_dict["compute_service"]),
                        "storage_service": str(fact_or_dict["storage_service"]),
                        "monthly_cost": float(fact_or_dict["monthly_cost"]),
                        "p95_ms": float(fact_or_dict["p95_ms"]),
                        "availability": float(fact_or_dict["availability"]),
                        "feasible": str(fact_or_dict["feasible"]),
                    }
            else:
                # It's already a dict
                eval_data = fact_or_dict

            score_breakdown = self._calculate_score_breakdown(eval_data, vendor_pref, max_cost, max_p95)

            top3.append({
                "vendor": eval_data["vendor"],
                "compute_service": eval_data["compute_service"],
                "storage_service": eval_data["storage_service"],
                "monthly_cost": eval_data["monthly_cost"],
                "p95_ms": eval_data["p95_ms"],
                "availability": eval_data.get("availability", 99.9),
                "cost_breakdown": eval_data.get("cost_breakdown", {}),
                "perf_model": eval_data.get("perf_model", "unknown"),
                "avail_model": eval_data.get("avail_model", "unknown"),
                "score_breakdown": score_breakdown
            })

        # Get winner (first in top3)
        winner = top3[0] if top3 else None
        winner_reason = None
        if winner:
            sb = winner["score_breakdown"]
            winner_reason = {
                "summary": f"Best overall score ({sb['composite']}/100)",
                "cost_analysis": f"Cost score: {sb['cost_score']}/100 (${winner['monthly_cost']:.2f}/month)",
                "performance_analysis": f"Performance score: {sb['perf_score']}/100 ({winner['p95_ms']:.1f}ms p95)",
                "preference_match": sb['preference_score'] > 0,
                "composite_score": sb['composite']
            }

        # Extract constraints from CLIPS
        constraints = []
        for f in self._facts(env, "constraint"):
            constraints.append({
                "type": str(f["type"]),
                "reason": str(f["reason"])
            })

        # Get reasoning
        whys = [str(w["msg"]) for w in self._facts(env, "why")]

        # Build assumptions
        assumptions = {
            "pricing_model": "stub-evaluator" if not evals else evals[0].get("reason", "unknown"),
            "region": workload.get("region", "us-east-1"),
            "sla_tier": workload.get("sla_tier", "standard"),
            "compliance": workload.get("compliance", "none")
        }

        return {
            "top3": top3,
            "winner": winner,
            "winner_reason": winner_reason,
            "constraints": constraints,
            "assumptions": assumptions,
            "why": whys
        }