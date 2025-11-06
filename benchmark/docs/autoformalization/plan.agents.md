# Autoformalization Issues - RESOLVED

## ✅ RESOLVED: Specs NOT being added to `Impl.lean`
**Status:** Not a bug - working correctly
- Investigation confirmed Impl.lean contains only implementations (zero sorry)
- Spec.lean contains specifications (with sorry)
- Files are correctly separated by orchestration.py

## ✅ FIXED: Only one function being autoformalized
**Status:** Critical bug - FIXED in commit bc48317
- Root cause: Missing dependency processing loop in orchestration.py
- Fix: Added Phase 1b to iterate through all dependencies
- Impact: Samples now process ALL functions (FUT + deps), not just FUT
- See AUTOFORMALIZATION_FIX.md for full details

## ✅ CLARIFIED: num_deps semantics
**Status:** Renamed to `num_fns_impl` for clarity
- Old: `num_deps` (ambiguous - did it include FUT?)
- New: `num_fns_impl` (explicit - includes FUT + all dependencies)
- Calculation: `len(payloads_from_datapoint(...))`

All issues documented in ../AUTOFORMALIZATION_FIX.md 
