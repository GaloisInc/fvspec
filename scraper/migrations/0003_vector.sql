CREATE EXTENSION IF NOT EXISTS vector;

-- https://catalog.workshops.aws/pgvector/en-US/1-introduction/d-postgresql-pgvector-extension

ALTER TABLE scrapedtests ADD COLUMN IF NOT EXISTS summary_vector vector(1024);
