import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from db_config import DB_CONFIG
import os
import sys

def create_database():
    """Tạo database nếu chưa tồn tại"""
    # Kết nối tới PostgreSQL server
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Kiểm tra database đã tồn tại chưa
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (DB_CONFIG['database'],))
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(f"CREATE DATABASE {DB_CONFIG['database']}")
            print(f"Database {DB_CONFIG['database']} đã được tạo")
        else:
            print(f"Database {DB_CONFIG['database']} đã tồn tại")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Lỗi khi tạo database: {e}")
        return False

def create_tables():
    """Tạo các bảng cần thiết"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Tạo bảng qa_entries để lưu Q&A
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS qa_entries (
            id SERIAL PRIMARY KEY,
            questions JSONB NOT NULL,
            answer TEXT,
            answer_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Tạo bảng files để lưu thông tin file
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id SERIAL PRIMARY KEY,
            filename TEXT UNIQUE NOT NULL,
            full_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Tạo bảng chunks để lưu chunks của file
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id SERIAL PRIMARY KEY,
            file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
            text TEXT NOT NULL,
            section TEXT,
            original_format TEXT,
            embedding BYTEA,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Tạo bảng sections để lưu sections của file
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sections (
            id SERIAL PRIMARY KEY,
            file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            content TEXT,
            normalized_title TEXT,
            keywords JSONB,
            section_order INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Tạo index để tìm kiếm nhanh
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_filename ON files(filename)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sections_file_id ON sections(file_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_qa_entries_questions ON qa_entries USING GIN(questions)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("Đã tạo các bảng trong database")
        return True
    except Exception as e:
        print(f"Lỗi khi tạo bảng: {e}")
        return False

if __name__ == "__main__":
    if create_database():
        create_tables()
    print("Hoàn tất khởi tạo database")