import json
import os
import psycopg2
from psycopg2.extras import Json
from db_config import DB_CONFIG

def import_qa_data():
    # Kết nối đến PostgreSQL
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Đọc dữ liệu từ file JSON
    try:
        qa_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'embedding', 'qaData.json')
        with open(qa_file, 'r', encoding='utf-8') as f:
            qa_data = json.load(f)
        print(f"Đã đọc {len(qa_data)} mục từ qaData.json")
    except FileNotFoundError:
        print("Không tìm thấy file qaData.json")
        return
    
    # Tạo bảng nếu chưa tồn tại
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
    
    # Xóa dữ liệu cũ (tùy chọn)
    cursor.execute("TRUNCATE TABLE qa_entries RESTART IDENTITY")
    
    # Import dữ liệu
    for item in qa_data:
        questions = Json(item['questions'])
        answer = item.get('answer', None)
        answer_file = item.get('answer_file', None)
        
        cursor.execute(
            "INSERT INTO qa_entries (questions, answer, answer_file) VALUES (%s, %s, %s)",
            (questions, answer, answer_file)
        )
    
    conn.commit()
    print(f"Đã import {len(qa_data)} mục vào PostgreSQL")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    import_qa_data()