-- Step 1: Add columns (nullable, no default)
ALTER TABLE scrapedtests
ADD COLUMN summaryversion smallint,
  ADD COLUMN summaryconfidence smallint;
-- Step 2: Populate all existing rows with 1
UPDATE scrapedtests
SET summaryversion = 1,
  summaryconfidence = 1;
-- Step 4: Set columns to NOT NULL
ALTER TABLE scrapedtests
ALTER COLUMN summaryconfidence
SET NOT NULL;
UPDATE scrapedtests
SET summaryversion = NULL
WHERE summary IS NULL;
