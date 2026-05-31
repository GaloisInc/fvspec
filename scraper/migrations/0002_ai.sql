-- ALTER TABLE scrapedtests ALTER deps TYPE JSONB USING deps::JSONB;
-- ALTER TABLE scrapedtests ALTER dep_names TYPE JSONB USING dep_names::JSONB;

ALTER TABLE scrapedtests ADD COLUMN IF NOT EXISTS hash text GENERATED ALWAYS AS (
    md5(pbt || deps::text)
) STORED;

CREATE INDEX IF NOT EXISTS scrapedtests_hash_idx ON scrapedtests (hash);

ALTER TABLE scrapedtests ADD COLUMN IF NOT EXISTS summary text;
