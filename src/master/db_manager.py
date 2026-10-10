import sqlite3
import os

# Veritabanı dosyasını projenin ana dizinine state.db olarak kaydeder
DB_PATH = os.path.join(os.path.dirname(__file__), '../../state.db')

def get_connection():
    # Asenkron çalışan ajanların aynı bağlantıyı kullanmasına izin verir
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  
    
    # Kilitlenmeleri (Database is locked hatasını) önlemek için WAL modunu aktif eder
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Görevler Tablosu (Task Decomposition sonrası görevler buraya düşecek)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            required_capability TEXT,
            assigned_agent TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Ajan Durumları Tablosu (Hangi ajan boşta, hangisi çalışıyor)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agents (
            name TEXT PRIMARY KEY,
            status TEXT DEFAULT 'IDLE',
            current_task_id INTEGER,
            FOREIGN KEY (current_task_id) REFERENCES tasks (id)
        )
    ''')

    conn.commit()
    conn.close()
    print("SQLite veritabanı (state.db) başarıyla başlatıldı.")

if __name__ == "__main__":
    init_db()