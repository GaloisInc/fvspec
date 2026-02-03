# postproduction todo

1. [ ] recover faithfulness and interestingness. in the grader.
    a. check first if `qa.json` has them and it was just an issue of the `merge` script dropping them.
2. [x] mark `fut_autoform` for the ones that actually implemented the functions under test and didn't stub them out as sorry (maybe in `merge/extra_metadata.py`?)
    - Implemented in `prune.py` by transforming `impl_autoform_success` from bool to 0/0.5/1 scale:
      - 1.0: impl_autoform_success=True AND no sorry (fully implemented)
      - 0.5: impl_autoform_success=True BUT has sorry (structured but stubbed)
      - 0.0: impl_autoform_success=False (failed to generate valid structure)
3. [x] Put `realpbt` in the names of all `realpbt`-derived fields, like `repo_id`=>`realpbt_repo_id` (do this inside `prune.py`)
    - Implemented in `prune.py` FIELD_RENAMES with 17 fields from the Datapoint model:
      - Core: id, name, code, repo_id, source_file, start_line, end_line
      - Metadata: original_id, dep_names, deps, source, summary, hash
      - ML: summary_vector, summaryversion, summaryconfidence
      - Testing: mode
    - All fields now prefixed with `realpbt_` (e.g., `id` → `realpbt_id`)

4. [ ] make sure you've deleted like most of those columns.
