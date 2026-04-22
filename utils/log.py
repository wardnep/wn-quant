import sqlite3
from datetime import datetime

def create_log(note) :
    conn = sqlite3.connect('journey.db')
    cursor = conn.cursor()

    cursor.execute('''
    INSERT INTO logs (
        note,
        created_at
    )
    VALUES (?, ?)
    ''', (
        note,
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))

    conn.commit()
    conn.close()

def create_trade(
    symbol,
    side,
    entry,
    sl,
    tp,
    exit_price,
    pnl
):
    conn = sqlite3.connect('journey.db')
    cursor = conn.cursor()

    cursor.execute('''
    INSERT INTO trades (
        symbol,
        side,
        entry,
        sl,
        tp,
        exit,
        pnl,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        symbol,
        side,
        entry,
        sl,
        tp,
        exit_price,
        pnl,
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))

    conn.commit()
    conn.close()