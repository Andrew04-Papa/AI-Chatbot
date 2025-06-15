import os
import subprocess
import sys
import time
import webbrowser
import threading
import platform

def get_python_executable():
    """Tìm đường dẫn Python phù hợp"""
    # Thử các đường dẫn Python phổ biến trên Windows
    possible_paths = [
        sys.executable,
        "python",
        "python3",
        "C:\\Users\\MSI\\AppData\\Local\\Programs\\Python\\Python313\\python.exe",
        "C:\\Python313\\python.exe",
        "C:\\Program Files\\Python313\\python.exe"
    ]
    
    for path in possible_paths:
        try:
            result = subprocess.run([path, "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Tìm thấy Python: {path}")
                return path
        except:
            continue
    
    print("❌ Không tìm thấy Python. Vui lòng cài đặt Python hoặc thêm vào PATH.")
    return None

def install_requirements(python_path):
    """Cài đặt các thư viện cần thiết"""
    print("=== Cài đặt các thư viện Python cần thiết ===")
    requirements_path = os.path.join(os.path.dirname(__file__), "server", "requirements.txt")
    try:
        result = subprocess.run(
            [python_path, "-m", "pip", "install", "-r", requirements_path],
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ Đã cài đặt thành công các thư viện")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi cài đặt thư viện: {e}")
        print("=== Thông báo lỗi chi tiết từ pip ===")
        print(e.stdout)
        print(e.stderr)
        return False

def initialize_database(python_path):
    """Khởi tạo database"""
    print("=== Khởi tạo database PostgreSQL ===")
    try:
        # Sử dụng đường dẫn tuyệt đối
        init_db_path = os.path.join(os.path.dirname(__file__), "server", "init_db.py")
        import_qa_data_path = os.path.join(os.path.dirname(__file__), "server", "import_qa_data.py")
        subprocess.run([python_path, init_db_path], check=True)
        print("✅ Đã khởi tạo database thành công")
        
        subprocess.run([python_path, import_qa_data_path], check=True)
        print("✅ Đã import dữ liệu thành công")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi khởi tạo database: {e}")
        print("Vui lòng kiểm tra PostgreSQL đã được cài đặt và chạy")
        return False

def start_python_server(python_path):
    """Khởi động Python server"""
    print("=== Khởi động Python server ===")
    try:
        if platform.system() == "Windows":
            subprocess.Popen([python_path, "embedding/server.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([python_path, "embedding/server.py"])
        
        print("✅ Python server đã khởi động tại http://localhost:5000")
        return True
    except Exception as e:
        print(f"❌ Lỗi khi khởi động Python server: {e}")
        return False

def start_client():
    """Khởi động client với live-server"""
    print("=== Khởi động client ===")
    try:
        # Kiểm tra Node.js
        subprocess.run(["node", "--version"], check=True, capture_output=True)

        # Tìm đường dẫn npx
        npx_path = "npx"
        if platform.system() == "Windows":
            # Thử tìm npx.cmd trong PATH
            for p in os.environ["PATH"].split(";"):
                candidate = os.path.join(p, "npx.cmd")
                if os.path.isfile(candidate):
                    npx_path = candidate
                    break

            subprocess.Popen([npx_path, "live-server", "client", "--port=8080"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(["npx", "live-server", "client", "--port=8080"])

        print("✅ Client đã khởi động tại http://localhost:8080")
        return True
    except subprocess.CalledProcessError:
        print("⚠️ Node.js chưa được cài đặt hoặc live-server chưa có")
        print("Bạn có thể mở file client/index.html trực tiếp trong trình duyệt")
        return False
    except FileNotFoundError as e:
        print(f"❌ Không tìm thấy npx hoặc live-server: {e}")
        print("Bạn có thể mở file client/index.html trực tiếp trong trình duyệt")
        return False

def open_browser():
    """Mở trình duyệt sau 5 giây"""
    time.sleep(5)
    try:
        webbrowser.open("http://localhost:8080")
        print("🌐 Đã mở trình duyệt")
    except:
        print("⚠️ Không thể mở trình duyệt tự động")

def main():
    print("🚀 Đang khởi động File Chatbot System...")
    print("="*60)
    
    # Bước 1: Tìm Python
    python_path = get_python_executable()
    if not python_path:
        input("Nhấn Enter để thoát...")
        return
    
    # Bước 2: Cài đặt requirements
    if not install_requirements(python_path):
        input("Nhấn Enter để thoát...")
        return
    
    # Bước 3: Khởi tạo database
    if not initialize_database(python_path):
        print("⚠️ Bỏ qua lỗi database, tiếp tục khởi động server...")
    
    # Bước 4: Khởi động Python server
    if not start_python_server(python_path):
        input("Nhấn Enter để thoát...")
        return
    
    # Bước 5: Khởi động client
    start_client()
    
    # Bước 6: Mở trình duyệt
    threading.Timer(5, open_browser).start()
    
    print("\n" + "="*60)
    print("🎉 Hệ thống đã khởi động thành công!")
    print("📱 Client: http://localhost:8080")
    print("🐍 Python API: http://localhost:5000")
    print("📊 Debug API: http://localhost:5000/debug")
    print("="*60)
    print("Nhấn Ctrl+C để dừng hoặc đóng cửa sổ này")
    
    try:
        # Giữ script chạy
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Đang dừng hệ thống...")

if __name__ == "__main__":
    main()