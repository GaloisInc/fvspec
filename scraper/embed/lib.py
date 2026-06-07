import psycopg2
import cohere
import os
import dotenv

dotenv.load_dotenv('../.env')

def db():
    con = psycopg2.connect(
        dbname=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASS'],
        host=os.environ['DB_HOST'],
        port=os.environ['DB_PORT']
    )
    cur = con.cursor()
    return con,cur

con,cur = db()

co = cohere.BedrockClient(
    aws_region='us-east-1',
    aws_access_key=os.environ['BEDROCK_ACCESS_KEY'],
    aws_secret_key=os.environ['BEDROCK_SECRET_ACCESS_KEY'],
)
