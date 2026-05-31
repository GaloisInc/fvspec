from lib import co, con, cur
from pgvector.psycopg2 import register_vector
import numpy as np

while True:
    query = input("Enter your search: ")
    print("================================\n\n")

    embeds = co.embed(texts=[query],input_type='search_query',model='cohere.embed-english-v3')

    register_vector(con)

    cur.execute("""
                select id, summary
                from scrapedtests
                where summary_vector is not null
                order by summary_vector <-> %(embedding)s limit 10""",({"embedding": np.array(embeds.embeddings[0])}))

    rows = cur.fetchall()

    for row in rows:
        print(f"{row[0]}: {row[1]}\n\n")
