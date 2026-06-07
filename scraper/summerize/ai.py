import openai
import os
from dotenv import load_dotenv
from pathlib import Path
from psycopg2.pool import ThreadedConnectionPool
import concurrent.futures
from tqdm import tqdm

load_dotenv()

pool = ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    dbname=os.environ['DB_NAME'],
    user=os.environ['DB_USER'],
    password=os.environ['DB_PASS'],
    host=os.environ['DB_HOST'],
    port=os.environ['DB_PORT']
)

with open(Path(__file__).parent / './prompt-ts.txt', 'r') as file:
    prompt = file.read()

client = openai.Client(
    api_key=os.environ['OPENAI_API_KEY'],
)

q = """
SELECT
  a.hash,
  a.pbt,
  a.source,
  a.deps,
  a.id,
  r.name AS repo_name,
  a.summary AS summary
FROM scrapedtests a
JOIN scrapedrepos r ON a.repo_id = r.id
WHERE a.summaryversion IS NULL AND a.mode = 'fast-check'
ORDER BY a.id
OFFSET %s LIMIT %s
"""

def fetch_batch(offset, limit=100):
    con = pool.getconn()
    try:
        cur = con.cursor()
        cur.execute(q, (offset, limit))
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        pool.putconn(con)

def filter_processed(rows):
    if not rows:
        return []
    hashes = [r[0] for r in rows]
    con = pool.getconn()
    try:
        cur = con.cursor()
        cur.execute("""
            SELECT hash
            FROM scrapedtests
            WHERE hash = ANY(%s) AND summaryversion IS NOT NULL
        """, (hashes,))
        processed_hashes = {h for (h,) in cur.fetchall()}
        cur.close()
    finally:
        pool.putconn(con)

    print(f"Filtered {len(rows)} rows, {len(processed_hashes)} already processed.")
    return [r for r in rows if r[0] not in processed_hashes]

def process_row(row):
    con = pool.getconn()
    try:
        cur = con.cursor()
        hash, ptb, source, deps, id, name, summary = row

        t = f"# file: {source}\nrepo: {name}\n\n"
        for dep in deps:
            t += dep + "\n\n"
        t += ptb

        estimated_tokens = (len(t.split()) * 1.3) + (len(prompt.split()) * 1.3) + 100
        if estimated_tokens > 30000:
            print(f"Estimated tokens: {estimated_tokens}, {id}")
            return

        c = client.responses.create(
            instructions=prompt,
            input=t,
            model="gpt-4o",
        )

        print(summary)
        print('\n' + c.output_text + '\n------')

        confidence = 1
        if "[I AM UNSURE]" in c.output_text:
            confidence = 0.5

        cur.execute(
            "UPDATE scrapedtests SET summary = %s, summaryversion = 1, summaryconfidence = %s WHERE id = %s",
            (c.output_text, confidence, id)
        )
        con.commit()
        cur.close()
    except Exception as e:
        print(f"Error processing row {id}: {e}")
    finally:
        pool.putconn(con)

BATCH_SIZE = 100
offset = 0

while True:
    batch = fetch_batch(offset, BATCH_SIZE)
    if not batch:
        break

    batch = filter_processed(batch)
    if not batch:
        offset += BATCH_SIZE
        continue

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        list(tqdm(executor.map(process_row, batch), total=len(batch)))

    offset += BATCH_SIZE
