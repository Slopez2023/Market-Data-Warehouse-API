"""
DEPRECATED: Use src.services.backfill_orchestrator instead.

This module is deprecated. All backfills should use the BackfillOrchestrator
which wraps master_backfill.py to ensure consistent validation, gap detection,
and retry logic.

Migration:
- Old: from src.services.backfill_worker import init_backfill_worker
- New: from src.services.backfill_orchestrator import init_backfill_orchestrator

Both CLI (master_backfill.py) and API (/api/v1/backfill) now use the same
orchestrator, ensuring no divergence in backfill logic.
"""

import warnings

warnings.warn(
    "backfill_worker is deprecated. Use backfill_orchestrator instead.",
    DeprecationWarning,
    stacklevel=2
)

# Placeholder - kept for compatibility only
def init_backfill_worker(*args, **kwargs):
    raise NotImplementedError(
        "backfill_worker is deprecated. Use BackfillOrchestrator from "
        "src.services.backfill_orchestrator instead."
    )

def enqueue_backfill_job(*args, **kwargs):
    raise NotImplementedError(
        "backfill_worker is deprecated. Use BackfillOrchestrator from "
        "src.services.backfill_orchestrator instead."
    )
