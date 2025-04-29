import sqlite3

def init_db():
    conn = sqlite3.connect('contentmaker.db')
    cursor = conn.cursor()

    tables = [
        '''CREATE TABLE IF NOT EXISTS thematic_blocks (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE
        )''',
        
        '''CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY,
            block_id INTEGER,
            username TEXT UNIQUE,
            FOREIGN KEY(block_id) REFERENCES thematic_blocks(id)
        )''',
        
        '''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            block_id INTEGER,
            original_text TEXT,
            rewritten_text TEXT,
            media_type TEXT,
            media_id TEXT,
            status TEXT DEFAULT 'raw',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(block_id) REFERENCES thematic_blocks(id)
        )''',
        
        '''CREATE TABLE IF NOT EXISTS publication_queue (
            id INTEGER PRIMARY KEY,
            message_id INTEGER,
            scheduled_time DATETIME,
            is_published BOOLEAN DEFAULT 0,
            FOREIGN KEY(message_id) REFERENCES messages(id)
        )'''
    ]

    for table in tables:
        cursor.execute(table)
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()