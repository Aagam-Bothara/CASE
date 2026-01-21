# evaluator/__init__.py
import os

def _use_live() -> bool:
    return os.getenv("REALTIME_PRICING", "").strip().lower() in ("1","true","yes","y","on")

if _use_live():
    from .pricing import REALTIME, eval_bundles  # live
    SOURCE = "pricing"
else:
    from .stub import eval_bundles              # stub
    REALTIME = False
    SOURCE = "stub"

__all__ = ["REALTIME", "eval_bundles", "SOURCE"]
