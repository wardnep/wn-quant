import sqlite3

conn = sqlite3.connect('journey.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note TEXT,
    created_at TEXT
)
''')

conn.commit()
conn.close()

print('migration complete')
