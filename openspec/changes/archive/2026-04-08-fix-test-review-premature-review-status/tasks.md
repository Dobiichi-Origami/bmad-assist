## 1. Fix PHASE_TO_STATUS mapping

- [x] 1.1 In `src/bmad_assist/sprint/sync.py`, change `Phase.TEST_REVIEW: "review"` to `Phase.TEST_REVIEW: "in-progress"` in the `PHASE_TO_STATUS` dict (line 145)
- [x] 1.2 Update the comments on lines 142 and 158-160 to reflect that TEST_REVIEW is now a development phase, not a review phase

## 2. Update tests

- [x] 2.1 In `tests/sprint/test_sync.py`, update test `test_test_review_maps_to_review` (line 251-253) to assert `"in-progress"` and rename to `test_test_review_maps_to_in_progress`

## 3. Verification

- [x] 3.1 Run `pytest tests/sprint/test_sync.py` to verify the mapping change passes
- [x] 3.2 Run `pytest tests/core/loop/test_guardian.py` to verify phase ordering is unaffected
- [x] 3.3 Run `pytest tests/core/config/test_loop_config.py` to verify loop config validation still passes
