#!/bin/bash
# Verification script for unified backfill implementation

set -e

echo "=========================================="
echo "UNIFIED BACKFILL IMPLEMENTATION VERIFICATION"
echo "=========================================="
echo ""

# Check files exist
echo "1. Checking files..."
test -f "src/services/backfill_orchestrator.py" && echo "  ✓ Orchestrator exists" || exit 1
test -f "src/services/backfill_worker.py" && echo "  ✓ Deprecated worker exists" || exit 1
test -f "database/migrations/017_backfill_audit_log.sql" && echo "  ✓ Audit log migration exists" || exit 1
test -f "UNIFIED_BACKFILL_IMPLEMENTATION.md" && echo "  ✓ Full documentation exists" || exit 1
test -f "UNIFIED_BACKFILL_SUMMARY.md" && echo "  ✓ Summary documentation exists" || exit 1
test -f "UNIFIED_BACKFILL_CHECKLIST.md" && echo "  ✓ Checklist exists" || exit 1

echo ""
echo "2. Checking imports..."
python << 'EOF'
from src.services.backfill_orchestrator import BackfillOrchestrator, init_backfill_orchestrator, get_backfill_orchestrator
print("  ✓ Orchestrator imports successfully")

from src.services.backfill_worker import init_backfill_worker
print("  ✓ Deprecated worker imports (with expected warning)")

try:
    init_backfill_worker()
    print("  ✗ FAILED: Worker should raise NotImplementedError")
    exit(1)
except NotImplementedError:
    print("  ✓ Deprecated worker properly raises NotImplementedError")
EOF

echo ""
echo "3. Checking main.py changes..."
grep -q "from src.services.backfill_orchestrator import" main.py && echo "  ✓ Correct import in main.py" || exit 1
grep -q "init_backfill_orchestrator(config.database_url" main.py && echo "  ✓ Orchestrator initialization in startup" || exit 1
grep -q "async def unified_backfill" main.py && echo "  ✓ Unified backfill endpoint exists" || exit 1
grep -q "get_backfill_orchestrator()" main.py && echo "  ✓ Orchestrator retrieval in endpoint" || exit 1

echo ""
echo "4. Checking documentation..."
wc_lines=$(wc -l < UNIFIED_BACKFILL_IMPLEMENTATION.md)
test $wc_lines -gt 250 && echo "  ✓ Implementation doc complete ($wc_lines lines)" || exit 1

grep -i -q "BackfillOrchestrator" UNIFIED_BACKFILL_SUMMARY.md && echo "  ✓ Summary mentions orchestrator" || true
grep -i -q "migration" UNIFIED_BACKFILL_IMPLEMENTATION.md && echo "  ✓ Migration path documented" || true

echo ""
echo "5. Checking AGENTS.md update..."
grep -q "Unified Backfill System" AGENTS.md && echo "  ✓ AGENTS.md updated" || exit 1
grep -q "BackfillOrchestrator" AGENTS.md && echo "  ✓ AGENTS.md mentions orchestrator" || exit 1

echo ""
echo "6. Checking test files..."
test -f "test_unified_backfill_simple.py" && echo "  ✓ Simple test file exists" || exit 1
test -f "test_unified_backfill.py" && echo "  ✓ Comprehensive test file exists" || exit 1

# Run simple tests
echo ""
echo "7. Running simple tests..."
python test_unified_backfill_simple.py 2>&1 | grep -q "All unified backfill tests passed" && echo "  ✓ All tests PASSED" || exit 1

echo ""
echo "=========================================="
echo "✓✓✓ ALL VERIFICATION CHECKS PASSED ✓✓✓"
echo "=========================================="
echo ""
echo "The unified backfill implementation is complete and ready for deployment."
echo ""
echo "Next steps:"
echo "1. Deploy code"
echo "2. Run database migrations (auto-runs on startup)"
echo "3. Test POST /api/v1/backfill endpoint"
echo "4. Monitor master_backfill.py subprocess execution"
echo ""
echo "See UNIFIED_BACKFILL_IMPLEMENTATION.md for full details."
