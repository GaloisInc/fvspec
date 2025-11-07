# CI Dataset (pbts_ci.db)

This is a randomly sampled subset of `pbts_full.db` used for nightly CI benchmarks.

## Location

`.github/pbts_ci.db` (committed to repository)

## Statistics

- **64 PBTs** (property-based tests, each with ≤32 associated functions)
- **46 repos** (source repositories)
- **5,669 functions** (only those referenced by the selected PBTs)
- **573 pbt_functions relationships**
- **Size**: 5.9MB (optimized for Git storage)

Note: PBTs are sampled conditional on having ≤32 associated functions to keep the database size manageable while still including the actual function implementations.

## Usage

This dataset is used by the nightly GitHub Actions workflow to run cost-effective regression testing with claude-haiku-4-5-20251001.

## Regeneration

If you need to create a new random sample:

```bash
cd benchmark/data
rm ../../.github/pbts_ci.db
sqlite3 ../../.github/pbts_ci.db <<'EOF'
ATTACH DATABASE 'pbts_full.db' AS full;

CREATE TABLE repos (
    id INTEGER PRIMARY KEY,
    source TEXT, name TEXT, url TEXT, license TEXT,
    license_status TEXT, stars INTEGER, forks INTEGER,
    parsed_at TEXT, hash TEXT
);

CREATE TABLE pbts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER, name TEXT, code TEXT,
    source_file TEXT, start_line INTEGER, end_line INTEGER,
    original_id INTEGER, dep_names TEXT, deps TEXT,
    source TEXT, summary TEXT, hash TEXT, summary_vector TEXT,
    mode TEXT, summaryversion INTEGER, summaryconfidence REAL,
    FOREIGN KEY (repo_id) REFERENCES repos(id)
);

-- Select 64 random PBTs that have ≤32 associated functions
WITH pbt_func_counts AS (
    SELECT pbt_id, COUNT(*) as func_count
    FROM full.pbt_functions
    GROUP BY pbt_id
    HAVING func_count <= 32
),
random_pbts AS (
    SELECT p.* FROM full.pbts p
    JOIN pbt_func_counts pfc ON p.id = pfc.pbt_id
    ORDER BY RANDOM()
    LIMIT 64
)
INSERT INTO pbts SELECT * FROM random_pbts;

INSERT INTO repos
SELECT DISTINCT r.* FROM full.repos r
WHERE r.id IN (SELECT repo_id FROM pbts);

INSERT INTO pbt_functions
SELECT * FROM full.pbt_functions
WHERE pbt_id IN (SELECT id FROM pbts);

INSERT INTO functions
SELECT DISTINCT f.* FROM full.functions f
JOIN full.pbt_functions pf ON pf.function_name = f.name
WHERE pf.pbt_id IN (SELECT id FROM pbts)
  AND f.repo_id IN (SELECT repo_id FROM pbts);

DETACH DATABASE full;
VACUUM;
EOF
```

**Warning**: Regenerating will change which samples are tested, affecting comparability of historical results.
