-- Step 1: Create the enum type
DO $$ BEGIN IF NOT EXISTS (
  SELECT 1
  FROM pg_type
  WHERE typname = 'scrapedtestmodes'
) THEN CREATE TYPE "ScrapedTestModes" AS ENUM ('hypothesis', 'fast-check');
END IF;
END $$;
-- Step 2: Add the 'mode' column to the 'scrapedtests' table
ALTER TABLE scrapedtests
ADD COLUMN IF NOT EXISTS mode "ScrapedTestModes";
-- Step 3: Default value for existing rows
UPDATE scrapedtests
SET mode = 'hypothesis'
WHERE mode IS NULL;
-- Step 4: Add a NOT NULL constraint to the 'mode' column
ALTER TABLE scrapedtests
ALTER COLUMN mode
SET NOT NULL;
