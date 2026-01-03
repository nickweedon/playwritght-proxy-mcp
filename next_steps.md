# Next Steps - Playwright Proxy MCP

**Last Updated:** 2026-01-03
**Session:** Code Complexity Refactoring - proxy_client.py
**Previous Commit:** `d3bbf1a` - "test: add comprehensive test coverage and fix async mocking"

---

## Current Status ✅

### Test Suite Health
- **Total Tests:** 388 (all passing - 100% pass rate)
- **Recent Additions:** +10 tests for `_build_command` and `_build_env`
- **Source Code Linting:** ✅ No errors (ruff configured properly)
- **Code Complexity:** ✅ All functions Grade C or better

### Recently Completed Work (2026-01-03)

1. **Refactored `_build_command` Function** ✅ COMPLETED
   - **Before:** Grade F, Cyclomatic Complexity 47 (CRITICAL)
   - **After:** Grade A, Cyclomatic Complexity 1 (EXCELLENT)
   - Broke down 144-line monolithic function into 11 focused functions:
     - `_build_command()` - Main orchestrator (CC: 1)
     - `_build_base_command()` - Mode detection (CC: 2)
     - `_build_standard_command()` - Standard npx path (CC: 2)
     - `_build_wsl_windows_command()` - WSL→Windows mode (CC: 2)
     - `_add_config_arguments()` - Argument coordinator (CC: 1)
     - `_add_browser_args()` - Browser configuration (CC: 12)
     - `_add_session_args()` - Session/storage args (CC: 7)
     - `_add_network_args()` - Network/proxy args (CC: 9)
     - `_add_recording_args()` - Recording/output args (CC: 6)
     - `_add_timeout_args()` - Timeout/response args (CC: 4)
     - `_add_stealth_args()` - Stealth/security args (CC: 7)
     - `_add_extension_args()` - Extension support args (CC: 5)

2. **Added Comprehensive Tests**
   - Added 10 new tests covering all edge cases
   - Tests for minimal config, all boolean flags, all string options
   - Tests for false/empty value handling
   - Tests for error cases (npx/cmd.exe not found)
   - Tests for environment variable building
   - **All 388 tests pass** (including 25 proxy_client tests)

3. **Code Quality Metrics**
   - Average complexity for `proxy_client.py`: **A (4.09)** (down from F)
   - Highest complexity function: `_add_browser_args` - Grade C (12)
   - No linting errors in source code
   - Clean, readable, maintainable code structure

---

## Immediate Next Steps (Priority Order)

### 1. **Address High-Complexity Function** ✅ COMPLETED
**Status:** DONE - Successfully refactored!
**Location:** `src/playwright_proxy_mcp/playwright/proxy_client.py:_build_command`
**Before:** Grade F, Cyclomatic Complexity 47
**After:** Grade A, Average Complexity 4.09

**Impact:**
- Eliminated the only Grade F (critical) complexity issue in the codebase
- Reduced bug risk and maintenance burden significantly
- Each function now has a single, clear responsibility
- Code is much easier to test, understand, and modify

**What Was Done:**
1. ✅ Analyzed the function and understood its logic
2. ✅ Wrote 10 comprehensive tests covering all edge cases
3. ✅ Refactored into 11 smaller, focused sub-functions
4. ✅ Verified all 388 tests pass (100% success rate)
5. ✅ Confirmed complexity improvement: Grade F → Grade A

**Results:**
```bash
# Before: Grade F, CC 47 (CRITICAL)
# After:  Grade A, Average CC 4.09 (EXCELLENT)

# All tests passing
uv run pytest -v
# ===== 388 passed in 2.50s =====

# No linting errors
uv run ruff check src/playwright_proxy_mcp --quiet
# (no output = success)
```

---

### 2. **Add Missing Test Coverage** 📊
**Status:** Identified but not implemented

Based on the complexity analysis, these modules need more tests:

| Module | Complexity | Current Tests | Target Tests | Gap |
|--------|-----------|---------------|--------------|-----|
| `logging_config.py` | 8 | 0 | 7 | -7 |
| `proxy_client.py` | 54 | 12 | 43 | -31 |
| `process_manager.py` | 21 | 7 | 17 | -10 |

**Action Items:**
1. Add tests for `logging_config.py` (straightforward utility functions)
2. Expand `test_proxy_client.py` coverage after refactoring `_build_command`
3. Add edge case tests for `test_process_manager.py`

---

### 3. **Test Proportionality Target** 🎯
**Goal:** Achieve 80% test proportionality for modules with complexity ≥ 6

**Current Status:**
- Overall ratio improved from 15.5% to ~25% (estimated)
- Still below 80% target for some modules

**How to Check:**
```bash
# Run the test proportionality analysis
uv run pytest -v  # Ensure all tests pass
uv run radon cc src/playwright_proxy_mcp -a -s  # Get complexity
# Compare with test counts in tests/
```

---

## Key Documentation & Patterns

### Async Mocking Patterns (for future reference)

**Pattern 1: TypedDict Config Access**
```python
# WRONG: cfg.instance_id (TypedDict doesn't support attribute access)
# RIGHT: cfg["instance_id"]
async def mock_create_instance(cfg, bm, mw):
    if cfg["instance_id"] == "0":
        pool.instances["0"] = mock_instance
```

**Pattern 2: Mock Context Manager Yields**
```python
# Context managers yield proxy_client, not the instance itself
instance.proxy_client = Mock()  # Required for lease_instance() yield

async with pool.lease_instance() as leased:
    assert leased == instance.proxy_client  # Not instance!
```

**Pattern 3: Mock Health Checks**
```python
# Pools check health_check_error attribute
mock_instance = Mock()
mock_instance.health_check_error = None  # Healthy
mock_pool.instances = {"0": mock_instance}
```

**Pattern 4: Complete Status Structures**
```python
# get_status() requires complete return structure
mock_pool.get_status = AsyncMock(return_value={
    "name": "DEFAULT",
    "total_instances": 1,
    "healthy_instances": 1,
    "leased_instances": 0,
    "available_instances": 1,
})
```

### Running Tests

```bash
# Full test suite
uv run pytest -v

# Specific module
uv run pytest tests/test_pool_manager.py -v

# With coverage report
uv run pytest --cov=src/playwright_proxy_mcp --cov-report=html

# Skip slow integration tests
uv run pytest -m "not integration" -v
```

### Linting

```bash
# Check all code
uv run ruff check .

# Check only source code (ignoring test warnings)
uv run ruff check src/playwright_proxy_mcp --quiet

# Auto-fix safe issues
uv run ruff check . --fix
```

### Complexity Analysis

```bash
# Install radon if not already installed
uv pip install radon

# Check specific file
uv run radon cc src/playwright_proxy_mcp/playwright/proxy_client.py -a -s

# Check all source files
uv run radon cc src/playwright_proxy_mcp -a -s

# Generate full report
uv run radon cc src/playwright_proxy_mcp -a -s --total-average
```

---

## Known Issues & Gotchas

### 1. Generated ANTLR Files
- Location: `src/aria_snapshot_parser/src/aria_snapshot_parser/generated/`
- These files have 200+ linting warnings (expected)
- Excluded in `pyproject.toml` ruff config
- DO NOT modify these files manually

### 2. Test File Linting
- Test files have some intentional linting warnings (unused imports, variable naming)
- Focus on source code linting: `uv run ruff check src/playwright_proxy_mcp --quiet`

### 3. Async Test Patterns
- Always use `AsyncMock()` for async methods
- Use `Mock()` for sync methods and attributes
- Use `patch.object()` for instance methods
- Use `patch()` for class/module level mocking

---

## Reference Files

### Configuration
- **Ruff Config:** `pyproject.toml` lines 67-80
- **Pytest Config:** `pyproject.toml` lines 82-94
- **Test Command:** `.claude/commands/test.md`

### Key Test Files
- **Pool Manager Tests:** `tests/test_pool_manager.py` (27 tests, good async patterns)
- **JMESPath Tests:** `tests/test_jmespath_extensions.py` (34 tests, comprehensive)
- **Navigation Cache Tests:** `tests/test_navigation_cache.py` (27 tests, TTL patterns)

### High-Complexity Source Files
- **proxy_client.py:** `_build_command` function (line ~100-200, needs refactoring)
- **pool_manager.py:** Generally good, some functions at Grade C/D
- **config.py:** Fixed walrus operators, now clean

---

## Success Metrics

### Completed ✅
- [x] All tests passing (378/378)
- [x] Source code linting clean
- [x] Added comprehensive test coverage for 3 modules
- [x] Documented async mocking patterns
- [x] Git committed and pushed

### Remaining 🎯
- [ ] Refactor `_build_command` (Grade F → Grade A/B)
- [ ] Add tests for `logging_config.py` (0 → 7 tests)
- [ ] Increase overall test proportionality to 80%+
- [ ] Add edge case tests for `proxy_client.py` and `process_manager.py`

---

## How to Resume

When starting a fresh session:

1. **Verify Current State**
   ```bash
   git status
   uv run pytest -v
   uv run ruff check src/playwright_proxy_mcp --quiet
   ```

2. **Check Test Coverage Gaps**
   ```bash
   uv run radon cc src/playwright_proxy_mcp -a -s
   # Compare with test counts in tests/
   ```

3. **Start with Priority 1**
   - Focus on `_build_command` refactoring
   - Read the function thoroughly first
   - Write tests for current behavior before changing anything
   - Refactor incrementally

4. **Reference This Document**
   - Use async mocking patterns from above
   - Follow testing strategy for refactoring
   - Check success metrics progress

---

## Additional Context

### Project Overview
- **Purpose:** MCP proxy server for playwright-mcp with blob storage optimization
- **Version:** 2.0.0 (browser pools architecture)
- **Tech Stack:** Python 3.10+, FastMCP, pytest, ruff
- **Main Documentation:** `CLAUDE.md` in project root

### Recent Architecture Changes
- v2.0.0 introduced browser pools (multiple isolated browser instances)
- Pool manager handles FIFO instance leasing
- Health monitoring and automatic recovery
- See `docs/BROWSER_POOLS_SPEC.md` for details

### Testing Philosophy
- Comprehensive unit tests with mocking for isolated components
- Integration tests for real browser interactions (marked with `@pytest.mark.integration`)
- Test proportionality: aim for tests >= 80% of code complexity
- Prefer explicit mocking over implicit test doubles

---

**Last Session:** Test coverage implementation completed successfully. All tests passing, linting clean, ready for next phase of refactoring high-complexity functions.

**Next Session Goal:** Refactor `_build_command` function to reduce complexity from Grade F (47) to Grade A/B (< 10).
