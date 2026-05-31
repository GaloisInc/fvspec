from lib import co, con, cur


lastId = 0
while True:
    # use this for new
    query = "select id, summary from scrapedtests where summary_vector is null and summary is not null and id > %s order by id limit 90"
    # use this for updating
    #query = "select id, summary from scrapedtests where summary_vector is not null and summaryversion = 2 and id > %s order by id limit 90"
    query = query % lastId
    cur.execute(query)
    rows = cur.fetchall()

    if len(rows) == 0:
        break

    embeds = co.embed(texts=[
        row[1] for row in rows
    ],input_type='search_document',model='cohere.embed-english-v3')

    for i, row in enumerate(rows):
        cur.execute("update scrapedtests set summary_vector = %s where id = %s",(embeds.embeddings[i],row[0]))
    con.commit()
    print("Updated 90 rows, last id:", rows[-1][0])
    lastId = rows[-1][0]
