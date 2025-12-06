import psycopg
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5433"),
    dbname=os.getenv("DB_NAME", "traffic_violations_db"),
    user=os.getenv("DB_USER", "myuser"),
    password=os.getenv("DB_PASSWORD", "mypassword")
)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM violations")
count = cur.fetchone()[0]
print(f"Total violations: {count:,}")

cur.close()
conn.close()