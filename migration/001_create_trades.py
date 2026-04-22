import sqlite3

conn = sqlite3.connect('journey.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    posiion TEXT,
    entry REAL,
    sl REAL,
    tp REAL,
    exit REAL,
    pnl REAL,
    created_at TEXT
)
''')

conn.commit()
conn.close()

print('migration complete')
