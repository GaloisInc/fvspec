import psycopg2
import os
import migrator

def db():
    con = psycopg2.connect(
        dbname=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASS'],
        host=os.environ['DB_HOST'],
        port=os.environ['DB_PORT']
    )
    cur = con.cursor()
    migrator.migrate(cur)
    return con,cur
