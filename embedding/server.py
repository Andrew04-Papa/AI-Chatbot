import torch
from sentence_transformers import SentenceTransformer, util
import fitz
from docx import Document
import pandas as pd
from flask import Flask, request, jsonify
from flask import send_from_directory
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import sys
import os
import json
import unicodedata

app = Flask(__name__)
CORS(app)

model = SentenceTransformer("all-MiniLM-L6-v2")
qa_embeddings = []
qa_corpus = []

def get_file_content(filename):
    upload_folder = os.path.join(os.path.dirname(__file__), "uploads")
    file_path = os.path.join(upload_folder, filename)
    ext = os.path.splitext(filename)[1].lower()
    try:
        if ext == ".pdf":
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
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

# Thêm đường dẫn server vào sys.path để import db_config
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'server'))
from db_config import DB_CONFIG

def get_db_connection():
    """Tạo kết nối đến PostgreSQL database"""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    return conn

def load_qa():
    """Load Q&A từ database"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT id, questions, answer, answer_file FROM qa_entries ORDER BY id")
    rows = cursor.fetchall()
    qa_data = []
    for row in rows:
        # Parse questions nếu là chuỗi JSON
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
    cursor.close()
    conn.close()
    return qa_data

def update_qa_embeddings():
    global qa_embeddings, qa_corpus
    qa_list = load_qa()
    qa_corpus = [q for qa in qa_list for q in qa["questions"]]
    if qa_corpus:
        qa_embeddings = model.encode(qa_corpus, convert_to_tensor=True)
    else:
        qa_embeddings = []

# Thay thế hàm save_qa
def save_qa(data):
    """Không cần thiết khi sử dụng PostgreSQL"""
    pass  # Dữ liệu được lưu trực tiếp vào database trong các API endpoints

@app.route("/api/qa", methods=["GET"])
def api_get_qa():
    data = load_qa()
    return jsonify(data)

@app.route("/qa-list", methods=["GET"])
def qa_list():
    return jsonify(load_qa())

@app.route("/qa-add", methods=["POST"])
def qa_add():
    questions = request.form.getlist("questions[]")
    print("DEBUG: questions nhận được khi add:", questions)
    if not questions or (len(questions) == 1 and not questions[0].strip()):
        # Nếu không có câu hỏi, trả về lỗi
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
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO qa_entries (questions, answer, answer_file) VALUES (%s, %s, %s)",
        (json.dumps(questions, ensure_ascii=False), answer, answer_file)
    )
    conn.commit()
    cursor.close()
    conn.close()
    update_qa_embeddings() 
    return jsonify({"message": "success"})

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
    cursor = conn.cursor()
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
    cursor.close()
    conn.close()
    update_qa_embeddings()
    return jsonify({"message": "success"})

@app.route("/qa-delete/<int:index>", methods=["DELETE"])
def qa_delete(index):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM qa_entries WHERE id=%s", (index+1,))
    conn.commit()
    cursor.close()
    conn.close()
    update_qa_embeddings() 
    return jsonify({"message": "deleted"})

@app.route("/files/<filename>")
def serve_file(filename):
    upload_folder = os.path.join(os.path.dirname(__file__), "uploads")
    return send_from_directory(upload_folder, filename, as_attachment=True)

def normalize_text(text):
    # Loại bỏ dấu tiếng Việt, chuyển về chữ thường, loại bỏ khoảng trắng thừa
    text = unicodedata.normalize('NFD', text)
    text = ''.join([c for c in text if unicodedata.category(c) != 'Mn'])
    return text.lower().strip()

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("question") or data.get("message") or ""
    question_norm = normalize_text(question)
    qa_list = load_qa()
    print("DEBUG: Câu hỏi nhận được:", question)
    print("DEBUG: Dữ liệu Q&A:", qa_list)
    # So khớp tuyệt đối trước
    for qa in qa_list:
        for q in qa["questions"]:
            q_norm = normalize_text(q)
            if question_norm == q_norm:
                if qa.get("answer_file"):
                    # Nếu người dùng hỏi về nội dung file
                    if "nội dung" in question_norm or "bên trong" in question_norm or "trong file" in question_norm:
                        text = get_file_content(qa["answer_file"])
                        return jsonify({"answer": text})
                    # Nếu chỉ hỏi về file, trả về link tải file như cũ
                    return jsonify({"answer_file": qa["answer_file"]})
                return jsonify({"answer": qa.get("answer", "Không có câu trả lời")})

    # So khớp gần đúng
    if len(question_norm) > 4:
        for qa in qa_list:
            for q in qa["questions"]:
                q_norm = normalize_text(q)
                if question_norm in q_norm or q_norm in question_norm:
                    if qa.get("answer_file"):
                        # Nếu người dùng hỏi về nội dung file
                        if "nội dung" in question_norm or "bên trong" in question_norm or "trong file" in question_norm:
                            text = get_file_content(qa["answer_file"])
                            return jsonify({"answer": text})
                        # Nếu chỉ hỏi về file, trả về link tải file như cũ
                        return jsonify({"answer_file": qa["answer_file"]})
                    return jsonify({"answer": qa.get("answer", "Không có câu trả lời")})

    # Nếu vẫn không tìm thấy, dùng embedding
    if qa_embeddings:
        query_vec = model.encode([question], convert_to_tensor=True)
        cos = util.cos_sim(query_vec, qa_embeddings)[0]
        idx = torch.argmax(cos).item()
        score = cos[idx].item()
        print("DEBUG: Điểm embedding:", score)
        if score > 0.5:
            matched_q = qa_corpus[idx]
            for qa in qa_list:
                if matched_q in qa["questions"]:
                    if qa.get("answer_file"):
                        # Nếu người dùng hỏi về nội dung file
                        if "nội dung" in question_norm or "bên trong" in question_norm or "trong file" in question_norm:
                            text = get_file_content(qa["answer_file"])
                            return jsonify({"answer": text})
                        # Nếu chỉ hỏi về file, trả về link tải file như cũ
                        return jsonify({"answer_file": qa["answer_file"]})
                    return jsonify({"answer": qa.get("answer", "Không có câu trả lời")})

    return jsonify({"answer": "❌ Không tìm thấy câu trả lời phù hợp."})

update_qa_embeddings()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

@app.route("/file-content/<filename>")
def file_content(filename):
    upload_folder = os.path.join(os.path.dirname(__file__), "uploads")
    file_path = os.path.join(upload_folder, filename)
    ext = os.path.splitext(filename)[1].lower()
    try:
        if ext == ".pdf":
            import fitz
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            return jsonify({"content": text})
        elif ext == ".docx":
            from docx import Document
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
            return jsonify({"content": text})
        elif ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            return jsonify({"content": text})
        else:
            return jsonify({"error": "Không hỗ trợ định dạng file này"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500