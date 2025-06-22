import torch
from sentence_transformers import SentenceTransformer, util
import fitz
from docx import Document
import pandas as pd
from flask import Flask, request, jsonify, session
from flask import send_from_directory
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import sys
import os
import json
import unicodedata
import uuid
from datetime import datetime, timedelta
import re
import threading

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this'
CORS(app, supports_credentials=True)

# Lazy loading cho model để tăng tốc startup
model = None
qa_embeddings = torch.tensor([])
qa_corpus = []

def load_model():
    """Lazy load sentence transformer model"""
    global model
    if model is None:
        print("🔄 Đang tải AI model...")
        model = SentenceTransformer("all-MiniLM-L6-v2")
        print("✅ Đã tải AI model thành công!")
    return model

# Thêm đường dẫn server vào sys.path để import db_config
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'server'))

try:
    from db_config import DB_CONFIG
    print("✅ Đã load DB config thành công")
except ImportError as e:
    print(f"❌ Lỗi import DB config: {e}")
    DB_CONFIG = {
        'host': 'localhost',
        'database': 'AI_Chatbot',
        'user': 'postgres',
        'password': 'hoangduy2k4',
        'port': 5432
    }

def get_db_connection():
    """Tạo kết nối đến PostgreSQL database với error handling"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"❌ Lỗi kết nối database: {e}")
        return None

def get_or_create_session_id():
    """Lấy hoặc tạo session ID mới"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def format_text_response(text):
    """Format text để hiển thị đẹp hơn với line breaks"""
    if not text:
        return text
    
    # Thay thế các ký tự xuống dòng đặc biệt
    text = text.replace('\\r\\n', '\n').replace('\\n', '\n').replace('\r\n', '\n')
    
    # Thêm xuống dòng sau dấu chấm nếu câu quá dài
    sentences = text.split('. ')
    formatted_sentences = []
    
    for i, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if sentence:
            # Thêm dấu chấm lại nếu không phải câu cuối
            if i < len(sentences) - 1 and not sentence.endswith('.'):
                sentence += '.'
            
            # Xuống dòng sau mỗi câu dài hơn 100 ký tự
            if len(sentence) > 100:
                sentence += '\n'
            
            formatted_sentences.append(sentence)
    
    result = ' '.join(formatted_sentences)
    
    # Thêm xuống dòng trước các bullet points
    result = re.sub(r'([.!?])\s*([•\-\*])', r'\1\n\2', result)
    
    # Thêm xuống dòng trước các tiêu đề (chữ in hoa)
    result = re.sub(r'([.!?])\s*([A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ]{3,})', r'\1\n\n\2', result)
    
    # Thêm xuống dòng trước thông tin liên hệ
    result = re.sub(r'([.!?])\s*(📞|☎️|📧|🌐|Địa chỉ|Email|Website|Điện thoại)', r'\1\n\n\2', result)
    
    return result

def format_file_content(content, filename):
    """Format nội dung file để hiển thị gọn gàng và đẹp"""
    if not content:
        return create_file_content_html("File trống hoặc không đọc được.", filename)
    
    # Làm sạch content
    content = content.strip()
    
    # Tách thành các sections dựa trên "---" hoặc "Trang"
    formatted_content = ""
    
    if "--- Trang" in content:
        pages = content.split("--- Trang")
        for i, page in enumerate(pages):
            if page.strip():
                if i > 0:
                    formatted_content += f'<div class="page-separator">📄 Trang {i}</div>'
                formatted_content += format_text_for_file(page.strip())
    else:
        # Format text thông thường
        formatted_content = format_text_for_file(content)
    
    return create_file_content_html(formatted_content, filename)

def format_text_for_file(text):
    """Format text cho file content - gọn gàng hơn"""
    if not text:
        return text
    
    # Thay thế các ký tự xuống dòng đặc biệt
    text = text.replace('\\r\\n', '\n').replace('\\n', '\n').replace('\r\n', '\n')
    
    # Làm sạch text - loại bỏ khoảng trắng thừa
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Ghép lại với xuống dòng đơn
    result = '\n'.join(lines)
    
    # Thêm xuống dòng trước các bullet points
    result = re.sub(r'([.!?])\s*([•\-\*])', r'\1\n\2', result)
    
    # Thêm xuống dòng trước các tiêu đề quan trọng
    result = re.sub(r'([.!?])\s*([A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ\s]{10,})', r'\1\n\n\2', result)
    
    return result

def create_file_content_html(content, filename):
    """Tạo HTML structure cho file content"""
    return f'''<div class="file-content-wrapper">
    <div class="file-content-header">
        <span class="file-icon">📄</span>
        <span>Nội dung: {filename}</span>
    </div>
    <div class="file-content-body" style="padding-top: 0; margin-top: 0;">{content}</div>
    <div class="file-content-footer">Trích từ file: {filename}</div>
</div>'''

def create_file_attachment_html(filename):
    """Tạo HTML cho file attachment siêu gọn gàng - chữ to hơn, khoảng cách gần hơn"""
    return f'''<div style="display: flex; flex-direction: column; align-items: flex-start;">
    <div style="display: flex; align-items: center; gap: 4px;">
        <span style="font-size: 20px; color: #6c757d;">📄</span>
        <span style="font-weight: bold; font-size: 14px; color: #495057;">Tệp đính kèm</span>
    </div>
    <a href="http://localhost:5000/files/{filename}" target="_blank" style="color: #7a1ea1; text-decoration: none; font-size: 15px; font-weight: 500; word-break: break-all; line-height: 1.1; margin-top: -2px;" title="{filename}">
        {filename}
    </a>
</div>'''

def save_conversation(session_id, user_message, bot_response, file_referenced=None, response_type='text'):
    """Lưu cuộc trò chuyện vào database"""
    conn = get_db_connection()
    if not conn:
        return False
        
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO conversations (session_id, user_message, bot_response, file_referenced, response_type)
            VALUES (%s, %s, %s, %s, %s)
        """, (session_id, user_message, bot_response, file_referenced, response_type))
        conn.commit()
        return True
    except Exception as e:
        print(f"Lỗi khi lưu conversation: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_conversation_history(session_id, limit=10):
    """Lấy lịch sử cuộc trò chuyện"""
    conn = get_db_connection()
    if not conn:
        return []
        
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
            SELECT user_message, bot_response, file_referenced, response_type, created_at
            FROM conversations 
            WHERE session_id = %s 
            ORDER BY created_at DESC 
            LIMIT %s
        """, (session_id, limit))
        rows = cursor.fetchall()
        return list(reversed(rows))
    except Exception as e:
        print(f"Lỗi khi lấy conversation history: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_last_referenced_file(session_id):
    """Lấy file được tham chiếu gần nhất trong cuộc trò chuyện"""
    conn = get_db_connection()
    if not conn:
        return None
        
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT file_referenced 
            FROM conversations 
            WHERE session_id = %s AND file_referenced IS NOT NULL 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (session_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"Lỗi khi lấy last referenced file: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_file_content(filename):
    """Lấy nội dung file từ file system"""
    upload_folder = os.path.join(os.path.dirname(__file__), "uploads")
    file_path = os.path.join(upload_folder, filename)
    ext = os.path.splitext(filename)[1].lower()
    
    try:
        if ext == ".pdf":
            doc = fitz.open(file_path)
            text = ""
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                text += f"\n--- Trang {page_num + 1} ---\n{page_text}"
            return text
        elif ext == ".docx":
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
            return text
        elif ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            return text
        else:
            return "Không hỗ trợ định dạng file này"
    except Exception as e:
        return f"Lỗi khi đọc file: {str(e)}"

def load_qa():
    """Load Q&A từ database với error handling"""
    conn = get_db_connection()
    if not conn:
        print("❌ Không thể kết nối database để load Q&A")
        return []
        
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT id, questions, answer, answer_file FROM qa_entries ORDER BY id")
        rows = cursor.fetchall()
        qa_data = []
        for row in rows:
            questions = row['questions']
            if isinstance(questions, str):
                try:
                    questions = json.loads(questions)
                except Exception:
                    questions = [questions]
            qa_data.append({
                'id': row['id'],
                'questions': questions,
                'answer': row['answer'],
                'answer_file': row['answer_file']
            })
        print(f"✅ Đã load {len(qa_data)} Q&A entries")
        return qa_data
    except Exception as e:
        print(f"❌ Lỗi load Q&A: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def update_qa_embeddings():
    """Cập nhật embeddings với lazy loading"""
    global qa_embeddings, qa_corpus
    try:
        qa_list = load_qa()
        qa_corpus = [q for qa in qa_list for q in qa["questions"]]
        if qa_corpus:
            # Lazy load model khi cần
            model = load_model()
            qa_embeddings = model.encode(qa_corpus, convert_to_tensor=True)
            print(f"✅ Đã tạo embeddings cho {len(qa_corpus)} câu hỏi")
        else:
            qa_embeddings = torch.tensor([])
            print("⚠️ Không có dữ liệu để tạo embeddings")
    except Exception as e:
        print(f"❌ Lỗi tạo embeddings: {e}")
        qa_embeddings = torch.tensor([])

def normalize_text(text):
    """Chuẩn hóa text"""
    text = unicodedata.normalize('NFD', text)
    text = ''.join([c for c in text if unicodedata.category(c) != 'Mn'])
    return text.lower().strip()

def clear_conversation_history(session_id):
    """Xóa lịch sử cuộc trò chuyện"""
    conn = get_db_connection()
    if not conn:
        return False
        
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM conversations WHERE session_id = %s", (session_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Lỗi khi xóa conversation history: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

# API Routes
@app.route("/api/qa", methods=["GET"])
def api_get_qa():
    data = load_qa()
    return jsonify(data)

@app.route("/qa-list", methods=["GET"])
def qa_list():
    data = load_qa()
    return jsonify(data)

@app.route("/qa-add", methods=["POST"])
def qa_add():
    questions = request.form.getlist("questions[]")
    if not questions or (len(questions) == 1 and not questions[0].strip()):
        return jsonify({"message": "Câu hỏi không được để trống!"}), 400
    if isinstance(questions, str):
        questions = [questions]
    answer = request.form.get("answer", "")
    file = request.files.get("file")
    answer_file = None

    if file:
        upload_folder = os.path.join(os.path.dirname(__file__), "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        file.save(os.path.join(upload_folder, file.filename))
        answer_file = file.filename

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Lỗi kết nối database"}), 500
        
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO qa_entries (questions, answer, answer_file) VALUES (%s, %s, %s)",
            (json.dumps(questions, ensure_ascii=False), answer, answer_file)
        )
        conn.commit()
        # Async update embeddings để không block request
        threading.Thread(target=update_qa_embeddings).start()
        return jsonify({"message": "success"})
    except Exception as e:
        print(f"Lỗi thêm Q&A: {e}")
        return jsonify({"message": "Lỗi thêm Q&A"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/qa-update/<int:index>", methods=["POST"])
def qa_update(index):
    questions = request.form.getlist("questions[]")
    if not questions or (len(questions) == 1 and not questions[0].strip()):
        return jsonify({"message": "Câu hỏi không được để trống!"}), 400
    if isinstance(questions, str):
        questions = [questions]
    answer = request.form.get("answer", "")
    file = request.files.get("file")
    answer_file = None

    if file:
        upload_folder = os.path.join(os.path.dirname(__file__), "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        file.save(os.path.join(upload_folder, file.filename))
        answer_file = file.filename

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Lỗi kết nối database"}), 500
        
    cursor = conn.cursor()
    try:
        if answer_file:
            cursor.execute(
                "UPDATE qa_entries SET questions=%s, answer=%s, answer_file=%s WHERE id=%s",
                (json.dumps(questions, ensure_ascii=False), answer, answer_file, index+1)
            )
        else:
            cursor.execute(
                "UPDATE qa_entries SET questions=%s, answer=%s WHERE id=%s",
                (json.dumps(questions, ensure_ascii=False), answer, index+1)
            )
        conn.commit()
        threading.Thread(target=update_qa_embeddings).start()
        return jsonify({"message": "success"})
    except Exception as e:
        print(f"Lỗi cập nhật Q&A: {e}")
        return jsonify({"message": "Lỗi cập nhật Q&A"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/qa-delete/<int:index>", methods=["DELETE"])
def qa_delete(index):
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Lỗi kết nối database"}), 500
        
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM qa_entries WHERE id=%s", (index+1,))
        conn.commit()
        threading.Thread(target=update_qa_embeddings).start()
        return jsonify({"message": "deleted"})
    except Exception as e:
        print(f"Lỗi xóa Q&A: {e}")
        return jsonify({"message": "Lỗi xóa Q&A"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/files/<filename>")
def serve_file(filename):
    upload_folder = os.path.join(os.path.dirname(__file__), "uploads")
    return send_from_directory(upload_folder, filename, as_attachment=True)

@app.route("/conversation-history")
def get_conversation_history_api():
    """API để lấy lịch sử cuộc trò chuyện"""
    session_id = get_or_create_session_id()
    history = get_conversation_history(session_id)
    return jsonify({"session_id": session_id, "history": history})

@app.route("/clear-chat", methods=["POST"])
def clear_chat():
    """API để xóa lịch sử chat"""
    session_id = get_or_create_session_id()
    success = clear_conversation_history(session_id)
    if success:
        return jsonify({"message": "success"})
    else:
        return jsonify({"message": "error"}), 500

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("question") or data.get("message") or ""
    session_id = get_or_create_session_id()
    
    question_norm = normalize_text(question)
    qa_list = load_qa()
    
    print(f"DEBUG: Session ID: {session_id}")
    print(f"DEBUG: Câu hỏi: {question}")
    
    # Kiểm tra xem người dùng có hỏi về nội dung file không
    content_keywords = ["nội dung", "bên trong", "trong file", "chi tiết", "đọc file", "xem file", "file có gì"]
    is_asking_content = any(keyword in question_norm for keyword in content_keywords)
    
    if is_asking_content:
        last_file = get_last_referenced_file(session_id)
        if last_file:
            print(f"DEBUG: Trả về nội dung file: {last_file}")
            file_content = get_file_content(last_file)
            formatted_response = format_file_content(file_content, last_file)
            
            save_conversation(session_id, question, formatted_response, last_file, 'file_content')
            return jsonify({"answer": formatted_response})
        else:
            response = "❌ Bạn chưa hỏi về file nào cả. Hãy hỏi về một file trước, sau đó tôi sẽ có thể cho bạn xem nội dung bên trong."
            save_conversation(session_id, question, response, None, 'text')
            return jsonify({"answer": response})
    
    # Xử lý Q&A bình thường
    # So khớp tuyệt đối trước
    for qa in qa_list:
        for q in qa["questions"]:
            q_norm = normalize_text(q)
            if question_norm == q_norm:
                if qa.get("answer_file"):
                    file_html = create_file_attachment_html(qa["answer_file"])
                    save_conversation(session_id, question, "File được tham chiếu", qa["answer_file"], 'file')
                    return jsonify({"answer": file_html})
                else:
                    response = format_text_response(qa.get("answer", "Không có câu trả lời"))
                    save_conversation(session_id, question, response, None, 'text')
                    return jsonify({"answer": response})

    # So khớp gần đúng
    if len(question_norm) > 4:
        for qa in qa_list:
            for q in qa["questions"]:
                q_norm = normalize_text(q)
                if question_norm in q_norm or q_norm in question_norm:
                    if qa.get("answer_file"):
                        file_html = create_file_attachment_html(qa["answer_file"])
                        save_conversation(session_id, question, "File được tham chiếu", qa["answer_file"], 'file')
                        return jsonify({"answer": file_html})
                    else:
                        response = format_text_response(qa.get("answer", "Không có câu trả lời"))
                        save_conversation(session_id, question, response, None, 'text')
                        return jsonify({"answer": response})

    # Nếu vẫn không tìm thấy, dùng embedding
    if len(qa_embeddings) > 0:
        try:
            model = load_model()  # Lazy load model
            query_vec = model.encode([question], convert_to_tensor=True)
            cos = util.cos_sim(query_vec, qa_embeddings)[0]
            idx = torch.argmax(cos).item()
            score = cos[idx].item()
            print(f"DEBUG: Điểm embedding: {score}")
            
            if score > 0.5:
                matched_q = qa_corpus[idx]
                for qa in qa_list:
                    if matched_q in qa["questions"]:
                        if qa.get("answer_file"):
                            file_html = create_file_attachment_html(qa["answer_file"])
                            save_conversation(session_id, question, "File được tham chiếu", qa["answer_file"], 'file')
                            return jsonify({"answer": file_html})
                        else:
                            response = format_text_response(qa.get("answer", "Không có câu trả lời"))
                            save_conversation(session_id, question, response, None, 'text')
                            return jsonify({"answer": response})
        except Exception as e:
            print(f"Lỗi embedding search: {e}")

    # Không tìm thấy câu trả lời
    response = "❌ Không tìm thấy câu trả lời phù hợp."
    save_conversation(session_id, question, response, None, 'text')
    return jsonify({"answer": response})

@app.route("/file-content/<filename>")
def file_content(filename):
    """API để lấy nội dung file"""
    try:
        content = get_file_content(filename)
        formatted_content = format_file_content(content, filename)
        return jsonify({"content": formatted_content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Khởi tạo nhanh - không load model ngay
print("🚀 Server đã sẵn sàng! (AI model sẽ được tải khi cần)")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
