# Gộp embedding_server.py + file_chatbot_server.py
from flask import Flask, request, jsonify, send_from_directory
from sentence_transformers import SentenceTransformer, util
from flask_cors import CORS
import os, json, torch, fitz  
import shutil
from docx import Document
import webbrowser
import threading
import threading

# 🧹 Xoá tất cả file trong embedding/uploads mỗi lần khởi động
upload_folder = os.path.join("embedding", "uploads")
if os.path.exists(upload_folder):
    for f in os.listdir(upload_folder):
        file_path = os.path.join(upload_folder, f)
        if os.path.isfile(file_path):
            os.remove(file_path)


app = Flask(__name__)
CORS(app)
model = SentenceTransformer("all-MiniLM-L6-v2")

def delete_file_delayed(path, delay=300):  # delay = 300s = 5 phút
    threading.Timer(delay, lambda: os.remove(path)).start()

def delete_if_unused(filename):
    global current_file_context, file_documents
    if current_file_context is None or current_file_context["filename"] != filename:
        file_path = os.path.join("embedding/uploads", filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        file_documents = [doc for doc in file_documents if doc["filename"] != filename]
        with open("embedding/file_data.json", "w", encoding="utf-8") as f:
            json.dump([{"filename": d["filename"], "chunks": d["chunks"]} for d in file_documents], f, ensure_ascii=False)

# ========================== Q&A DATA ==========================
qa_file = os.path.join(os.path.dirname(__file__), 'qaData.json')
qa_data = []
qa_corpus = []
qa_embeddings = []

def load_qa():
    with open(qa_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_qa(data):
    with open(qa_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_qa_embeddings():
    global qa_data, qa_corpus, qa_embeddings
    qa_data = load_qa()
    qa_corpus = [q for entry in qa_data for q in entry['questions']]
    qa_embeddings = model.encode(qa_corpus, convert_to_tensor=True)

update_qa_embeddings()

@app.route('/qa-list', methods=['GET'])
def get_qa_list():
    return jsonify(load_qa())

@app.route('/qa-add', methods=['POST'])
def add_qa():
    questions = request.form.getlist('questions[]')
    answer = request.form.get('answer', '')
    file = request.files.get('file')
    new_entry = {"questions": questions}
    if answer:
        new_entry['answer'] = answer
    if file and file.filename:
        file_path = os.path.join('embedding/files', file.filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        new_entry['answer_file'] = file.filename
    data = load_qa()
    data.append(new_entry)
    save_qa(data)
    update_qa_embeddings()
    return jsonify({'message': '✅ Đã thêm Q&A thành công!'})

@app.route('/qa-update/<int:index>', methods=['POST'])
def update_qa(index):
    questions = request.form.getlist('questions[]')
    answer = request.form.get('answer', '')
    file = request.files.get('file')
    data = load_qa()
    if index >= len(data):
        return jsonify({'error': 'Index không hợp lệ'}), 400
    data[index]['questions'] = questions
    data[index]['answer'] = answer
    if file and file.filename:
        old = data[index].get('answer_file')
        if old:
            old_path = os.path.join('embedding/files', old)
            if os.path.exists(old_path): os.remove(old_path)
        file_path = os.path.join('embedding/files', file.filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        data[index]['answer_file'] = file.filename
    save_qa(data)
    update_qa_embeddings()
    return jsonify({'message': '✅ Đã cập nhật Q&A thành công!'})

@app.route('/qa-delete/<int:index>', methods=['DELETE'])
def delete_qa(index):
    data = load_qa()
    if index >= len(data): return jsonify({'error': 'Index không tồn tại'}), 404
    entry = data.pop(index)
    if 'answer_file' in entry:
        fpath = os.path.join('embedding/files', entry['answer_file'])
        if os.path.exists(fpath): os.remove(fpath)
    save_qa(data)
    update_qa_embeddings()
    return jsonify({'message': '✅ Đã xoá Q&A + file thành công!'})

@app.route('/files/<path:filename>')
def download_file(filename):
    uploads_dir = os.path.join(os.getcwd(), "embedding", "uploads")
    files_dir = os.path.join(os.getcwd(), "embedding", "files")
    fname_lower = filename.lower()

    print(f"[DOWNLOAD] Yêu cầu tải file: {filename}")
    print(f"[CHECK] uploads/: {os.listdir(uploads_dir)}")

    # ✅ Tìm file trong uploads/
    for f in os.listdir(uploads_dir):
        if f.lower() == fname_lower:
            print(f"[FOUND] File có sẵn trong uploads/: {f}")
            return send_from_directory(uploads_dir, f, as_attachment=True)

    # ✅ Nếu chưa có → tìm trong files/ và tự động copy sang uploads/
    for f in os.listdir(files_dir):
        if f.lower() == fname_lower:
            src = os.path.join(files_dir, f)
            dst = os.path.join(uploads_dir, f)
            shutil.copyfile(src, dst)
            print(f"[AUTO-COPY] File vừa được copy từ files → uploads/: {f}")
            return send_from_directory(uploads_dir, f, as_attachment=True)

    print(f"[ERROR] Không tìm thấy file: {filename}")
    return jsonify({"error": "Không tìm thấy file"}), 404

# ======================= FILE CHATBOT =======================
CHUNK_SIZE = 50
file_documents = []
file_documents = []
current_file_context = None  
@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files['file']
    ext = file.filename.split('.')[-1].lower()
    save_path = os.path.join("embedding/uploads", file.filename)
    os.makedirs("embedding/uploads", exist_ok=True)
    file.save(save_path)
    delete_file_delayed(save_path) 
    if ext == 'pdf':
        text = extract_text_from_pdf(save_path)
    elif ext == 'docx':
        text = extract_text_from_docx(save_path)
    else:
        return jsonify({"error": "Chỉ hỗ trợ PDF và DOCX"}), 400
    chunks = chunk_text(text)
    embeds = model.encode(chunks, convert_to_tensor=True)
    file_documents.append({"filename": file.filename, "chunks": chunks, "embeddings": embeds})
    global current_file_context
    current_file_context = file_documents[-1]  
    with open("embedding/file_data.json", "w", encoding="utf-8") as f:
        json.dump([{"filename": d["filename"], "chunks": d["chunks"]} for d in file_documents], f, ensure_ascii=False)
    return jsonify({"message": "Đã xử lý file", "chunks": len(chunks)})


def chunk_text(text, size=CHUNK_SIZE):
    words = text.split()
    return [' '.join(words[i:i+size]) for i in range(0, len(words), size)]

def extract_text_from_pdf(path):
    doc = fitz.open(path)
    return "\n".join([p.get_text() for p in doc])

def extract_text_from_docx(path):
    doc = Document(path)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

# ======================= API CHAT =======================
@app.route("/chat", methods=["POST"])
def chat():
    question = request.json.get("question", "")
    mode = request.json.get("use", "auto")
    query_vec = model.encode(question, convert_to_tensor=True)
    best = {"score": -1, "answer": "❓ Không tìm thấy câu trả lời phù hợp."}

    if mode in ["qa", "auto"]:
        cos = util.cos_sim(query_vec, qa_embeddings)[0]
        idx = torch.argmax(cos).item()
        score = cos[idx].item()
        if score > best['score'] and score > 0.25:  
            entry = next(e for e in qa_data if qa_corpus[idx] in e['questions'])

            fileBlock = ""
            if 'answer_file' in entry:
                fname = entry['answer_file']
                url = f"/files/{fname}"
                fileBlock = f"""
                    <div>
                        <div style="display: flex; align-items: center; font-weight: bold; color: #003e64;">
                            <span style="font-size: 20px; font-weight: bold;">📄</span>
                            <span style="font-weight: bold; font-size: 16px; color: #002b50;">Tệp đính kèm:</span>
                        </div>
                        <div style="margin-left: 4px;">
                            <a href="{url}" target="_blank"
                                style="color: #7a1ea1; text-decoration: none;">
                                {fname}
                            </a>
                        </div>
                    </div>
                    """
            # Chuyển nội dung xuống dòng HTML
            answer_html = entry.get('answer', '').replace('\r\n', '<br>').replace('\n', '<br>')

            # Ghép file và nội dung
            if fileBlock and answer_html:
                full_answer = fileBlock + "<br>" + answer_html
            elif fileBlock:
                full_answer = fileBlock
            else:
                full_answer = answer_html

            if (answer_html or fileBlock) and score > best['score']:
                best = {"score": score, "answer": full_answer}
            else:
                best = {"score": -1, "answer": "❓ Không tìm thấy câu trả lời phù hợp."}

    if mode in ["file", "auto"]:
        # ✅ Trích tên file được đề cập trong câu hỏi (không phân biệt hoa thường)
        global current_file_context, matched_doc
        filename_in_question = question.lower().replace(" ", "")
        matched_doc = current_file_context  
        if not file_documents:
            print("🆕 Đang nạp lại tất cả file từ embedding/files/")
            for fname in os.listdir("embedding/files"):
                if fname.endswith(".pdf") or fname.endswith(".docx"):
                    full_path = os.path.join("embedding/files", fname)
                    ext = fname.split('.')[-1].lower()
                    if ext == 'pdf':
                        text = extract_text_from_pdf(full_path)
                    elif ext == 'docx':
                        text = extract_text_from_docx(full_path)
                    else:
                        continue
                    chunks = chunk_text(text)
                    embeds = model.encode(chunks, convert_to_tensor=True)
                    file_documents.append({
                        "filename": fname,
                        "chunks": chunks,
                        "embeddings": embeds
                    })
            print(f"✅ Đã nạp {len(file_documents)} file vào RAM")
            print(f"🔔 Câu hỏi nhận được: {question}")
            print(f"📦 Hiện có {len(file_documents)} file trong RAM")
            print(f"🔍 File cần tìm (normalized): {filename_in_question}")
        
        from difflib import SequenceMatcher

        best_match = None
        highest_ratio = 0.0
        for doc in file_documents:
            fname_base = os.path.splitext(doc["filename"])[0].lower().replace(" ", "")
            ratio = SequenceMatcher(None, filename_in_question, fname_base).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                best_match = doc

        if best_match and highest_ratio > 0.6:  
            doc = best_match
            fname = doc["filename"]
            upload_path = os.path.join("embedding/uploads", fname)
            original_path = os.path.join("embedding/files", fname)

            if not os.path.exists(upload_path) and os.path.exists(original_path):
                shutil.copyfile(original_path, upload_path)

            if "embeddings" not in doc:
                ext = fname.split('.')[-1].lower()
                if ext == 'pdf':
                    text = extract_text_from_pdf(upload_path)
                elif ext == 'docx':
                    text = extract_text_from_docx(upload_path)
                else:
                    return jsonify({"error": "File không hỗ trợ"}), 400
                chunks = chunk_text(text)
                embeds = model.encode(chunks, convert_to_tensor=True)
                doc["chunks"] = chunks
                doc["embeddings"] = embeds

            matched_doc = doc
            current_file_context = doc
            threading.Timer(300, lambda: delete_if_unused(fname)).start()

        if matched_doc:
            cos = util.cos_sim(query_vec, matched_doc["embeddings"])[0]
            print(f"[QUESTION] {question}")
            for i, c in enumerate(cos):
                print(f"Chunk {i} | Score: {c.item():.4f} | Preview: {matched_doc['chunks'][i][:60]}")

            top_k = 3
            top_idxs = torch.topk(cos, top_k).indices.tolist()

            best_text = "<br><br>".join([matched_doc["chunks"][i] for i in top_idxs])
            score = cos[top_idxs[0]].item()
            if score > best['score']:
                best = {
                    "score": score,
                    "answer": f"<b>Trích từ file <u>{matched_doc['filename']}</u>:</b><br>{best_text}"
                }

            # 🧹 Dọn sau 5 phút nếu không dùng tiếp
            if current_file_context:
                fname = current_file_context["filename"]
                threading.Timer(300, lambda: delete_if_unused(fname)).start()
                current_file_context = None
    return jsonify(best) 


# ✅ Phục vụ index.html từ thư mục client
@app.route('/')
def serve_index():
    return send_from_directory(os.path.join(os.path.dirname(__file__), '../client'), 'index.html')

# ✅ Phục vụ tất cả file tĩnh từ client/
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(os.path.join(os.path.dirname(__file__), '../client'), path)

def open_browser_once():
    if not os.path.exists(".browser_opened"):
        with open(".browser_opened", "w") as f:
            f.write("yes")
        webbrowser.open_new("http://localhost:5000")

if __name__ == '__main__':
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Timer(1, open_browser_once).start()
    app.run(debug=True)

