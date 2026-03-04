import sqlite3

conn = sqlite3.connect('documents.db')
cur = conn.cursor()
cur.execute('SELECT id, filename FROM documents')
rows = cur.fetchall()

print("All documents:")
for r in rows:
    print(f"  {r[0]}: {repr(r[1])}")
