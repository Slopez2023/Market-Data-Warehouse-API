# Documentation Organization Plan

**Status**: Ready for Implementation  
**Target Structure**: Professional enterprise-grade documentation  
**Target Date**: November 10, 2025

---

## Current State Analysis

### Problems
1. **Root directory clutter**: 26 MD files in root (PHASE_*, SESSION_*, INDEX.md, etc.)
2. **Scattered documentation**: Some docs in `/docs/`, some in root
3. **Mixed concerns**: Development notes, phase tracking, and user guides mixed together
4. **Archive folder**: 40+ archived files taking up space and creating confusion
5. **No clear navigation**: Multiple INDEX files with unclear purpose

### Files to Organize

**Root Level** (26 files):
- Phase completion files: PHASE_1_COMPLETE.md through PHASE_6_5_COMPLETE.md
- Phase management: PHASE_6_PLAN.md, PHASE_6_PROGRESS.md, PHASE_6_CHECKLIST.md
- Session summaries: SESSION_SUMMARY_*.md
- Index files: INDEX.md, PHASE_6_INDEX.md, OBSERVABILITY_INDEX.md
- Quick references: PHASE_6_QUICK_REFERENCE.md, PERFORMANCE_QUICK_REFERENCE.md, OBSERVABILITY_QUICKSTART.md
- Guides: SETUP_GUIDE.md, OBSERVABILITY.md
- Status: DEVELOPMENT_STATUS.md, ARCHITECTURE_REVIEW.md, REVIEW_COMPLETE.md, PHASE_6_SUMMARY.md

**Docs Folder** (6 files):
- README.md, API_ENDPOINTS.md, INSTALLATION.md, OPERATIONS.md, QUICK_REFERENCE.md, ARCHIVED_DOCS.md

---

## Proposed Structure

```
/
├── README.md                          [Entry point - moved from docs/]
├── QUICKSTART.md                      [NEW - 5-min getting started]
├── 
├── docs/
│   ├── README.md                      [Navigation hub]
│   │
│   ├── getting-started/
│   │   ├── INSTALLATION.md            [Setup instructions]
│   │   ├── SETUP_GUIDE.md             [Initial configuration]
│   │   └── QUICKSTART.md              [5-minute quick start]
│   │
│   ├── api/
│   │   ├── README.md                  [API overview]
│   │   ├── ENDPOINTS.md               [All endpoints reference]
│   │   ├── AUTHENTICATION.md          [API key management guide]
│   │   ├── SYMBOLS.md                 [Symbol management guide]
│   │   └── CRYPTO.md                  [Crypto symbols guide]
│   │
│   ├── operations/
│   │   ├── README.md                  [Operations overview]
│   │   ├── DEPLOYMENT.md              [Deployment guide]
│   │   ├── MONITORING.md              [Observability guide]
│   │   ├── PERFORMANCE.md             [Performance tuning]
│   │   └── TROUBLESHOOTING.md         [Common issues]
│   │
│   ├── development/
│   │   ├── README.md                  [Dev overview]
│   │   ├── ARCHITECTURE.md            [System architecture]
│   │   ├── CONTRIBUTING.md            [Contributing guidelines]
│   │   └── TESTING.md                 [Testing guide]
│   │
│   └── reference/
│       ├── QUICK_REFERENCE.md         [Command cheat sheet]
│       ├── GLOSSARY.md                [Term definitions]
│       └── FAQ.md                     [Frequently asked questions]
│
├── .phases/                            [NEW - Phase tracking folder]
│   ├── README.md                       [Phase overview]
│   ├── PHASE_1_COMPLETE.md             [Phase 1 summary]
│   ├── PHASE_2_COMPLETE.md             [Phase 2 summary]
│   ├── ...
│   ├── PHASE_6_PROGRESS.md             [Phase 6 current status]
│   └── DEVELOPMENT_STATUS.md           [Overall status]
│
└── .sessions/                          [NEW - Session notes folder]
    ├── SESSION_SUMMARY_NOV_10.md       [Session 1]
    └── SESSION_SUMMARY_PHASE_6_5.md    [Session 2]
```

---

## File Mapping & Actions

### Move to `/docs/getting-started/`
- `SETUP_GUIDE.md` → exists
- `INSTALLATION.md` → exists

### Move to `/docs/api/`
- Create `AUTHENTICATION.md` (API_KEY_MANAGEMENT.md content)
- Create `SYMBOLS.md` (Symbol management guide)
- Create `CRYPTO.md` (Crypto symbols guide)
- `API_ENDPOINTS.md` → `ENDPOINTS.md`

### Move to `/docs/operations/`
- Create `DEPLOYMENT.md` (DEPLOYMENT_WITH_AUTH.md content)
- `OBSERVABILITY.md` → `MONITORING.md`
- `OBSERVABILITY_QUICKSTART.md` → merge into MONITORING.md
- `PERFORMANCE_QUICK_REFERENCE.md` → `PERFORMANCE.md`
- Create `TROUBLESHOOTING.md`

### Move to `/docs/reference/`
- Create `QUICK_REFERENCE.md` (PHASE_6_QUICK_REFERENCE.md content + cheat sheets)
- Create `FAQ.md`
- Create `GLOSSARY.md`

### Move to `/.phases/`
- All `PHASE_*_COMPLETE.md` files
- `PHASE_6_PROGRESS.md`
- `PHASE_6_SUMMARY.md`
- `DEVELOPMENT_STATUS.md`
- `PHASE_6_CHECKLIST.md`

### Move to `/.sessions/`
- `SESSION_SUMMARY_*.md` files

### Create New
- `/README.md` (project entry point)
- `/QUICKSTART.md` (5-minute quick start at root)
- `/docs/README.md` (documentation hub)
- `/docs/getting-started/QUICKSTART.md`
- `/docs/api/README.md`
- `/docs/operations/README.md`
- `/docs/operations/TROUBLESHOOTING.md`
- `/docs/development/README.md`
- `/docs/development/ARCHITECTURE.md` (ARCHITECTURE_REVIEW.md content)
- `/docs/development/CONTRIBUTING.md`
- `/docs/development/TESTING.md`
- `/docs/reference/GLOSSARY.md`
- `/docs/reference/FAQ.md`
- `/.phases/README.md`
- `/.sessions/README.md`

### Delete/Archive
- `/docs/ARCHIVED_DOCS.md` (no longer needed)
- `REVIEW_COMPLETE.md` (move to .phases if needed)
- `PHASE_6_INDEX.md` (consolidated into new structure)
- `OBSERVABILITY_INDEX.md` (consolidated)
- `INDEX.md` (consolidated into docs/README.md)

---

## Implementation Strategy

### Phase 1: Create New Directory Structure
1. Create `/docs/getting-started/`, `/docs/api/`, `/docs/operations/`, `/docs/development/`, `/docs/reference/`
2. Create `/.phases/` and `/.sessions/`
3. Verify all directories created successfully

### Phase 2: Create Navigation & Hub Files
1. Create root `/README.md` with project overview and main navigation
2. Create `/QUICKSTART.md` for 5-minute onboarding
3. Create `/docs/README.md` with documentation map
4. Create subsection README.md files for each category

### Phase 3: Move & Consolidate Existing Content
1. Move PHASE_* files to `/.phases/`
2. Move SESSION_* files to `/.sessions/`
3. Move and rename documentation files to new locations
4. Consolidate overlapping content (e.g., multiple observability docs)

### Phase 4: Create New Documentation
1. Create `AUTHENTICATION.md` for Phase 6.6
2. Create `SYMBOLS.md` for Phase 6.6
3. Create `CRYPTO.md` for Phase 6.6
4. Create `DEPLOYMENT.md` for Phase 6.6
5. Create `TROUBLESHOOTING.md` with common issues
6. Create `CONTRIBUTING.md` for developers
7. Create `TESTING.md` for test guidelines
8. Create `GLOSSARY.md` with terms
9. Create `FAQ.md` with common questions

### Phase 5: Update Links & Cross-References
1. Update all internal links in documentation
2. Update INDEX files with new structure
3. Add breadcrumb navigation to all docs
4. Add "See Also" sections where relevant

### Phase 6: Cleanup & Archive
1. Move old files to `.archive/`
2. Update `.gitignore` if needed
3. Verify no broken links
4. Final cleanup

---

## Benefits

✅ **Clear Navigation**: Structured hierarchy makes finding docs easy  
✅ **Professional Appearance**: Organized structure signals quality  
✅ **Separation of Concerns**: Development docs separate from user guides  
✅ **Scalability**: Easy to add new sections as project grows  
✅ **Discoverability**: README files in each section guide users  
✅ **Version History**: Phases tracked separately for reference  

---

## Estimated Time

- Phase 1 (Create directories): 5 minutes
- Phase 2 (Navigation files): 20 minutes
- Phase 3 (Move files): 10 minutes
- Phase 4 (New content): 90 minutes (Phase 6.6 implementation)
- Phase 5 (Link updates): 20 minutes
- Phase 6 (Cleanup): 10 minutes

**Total**: ~2.5 hours

---

**Status**: Ready for implementation approval
