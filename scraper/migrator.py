import psycopg2
import os

def migrate(cur: psycopg2.extensions.cursor):
    cur.execute("""CREATE TABLE IF NOT EXISTS scrapermigrations (
    id SERIAL,
    name TEXT,
    created_at TIMESTAMP DEFAULT now()
)""")
    cur.connection.commit()
    migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
    for migration in os.listdir(migrations_dir):
        migration_path = os.path.join(migrations_dir, migration)
        with open(migration_path) as f:
            print('Running migration', migration)
            cur.execute('SELECT * FROM scrapermigrations WHERE name = %s', (migration,))
            if cur.fetchone() is not None:
                continue
            try:
                cur.execute(f.read())
            except Exception as e:
                print(f"Migration {migration} failed: {e}")
            else:
                print(f"Migration {migration} ran successfully")
                cur.execute('INSERT INTO scrapermigrations (name) VALUES (%s)', (migration,))
                cur.connection.commit()

if __name__ == "__main__":
    # check if called with the --dry flag, if so, connect to /tmp with username postgres and password postgres and database postgres
    if os.environ.get('DRY') == 'true':
        conn = psycopg2.connect(host='127.0.0.1', port=5433, user='postgres', password='postgres', dbname='postgres', sslmode="disable")
        migrate(conn.cursor())
