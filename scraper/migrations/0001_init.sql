DO $$ BEGIN
    CREATE TYPE scrapesource AS ENUM ('gh', 'dependents');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS scrapedrepos (
    id SERIAL,
    source scrapesource,
    name TEXT,
    url TEXT,
    license TEXT,
    license_status TEXT,
    stars integer,
    forks integer,
    parsed_at TEXT,
    hash TEXT
);

CREATE TABLE IF NOT EXISTS scrapedtests (
    id SERIAL,
    repo_id integer,
    pbt_name TEXT,
    pbt TEXT,
    dep_names TEXT,
    deps TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS scrapermigrations (
    id SERIAL,
    name TEXT,
    created_at TIMESTAMP DEFAULT now()
);
