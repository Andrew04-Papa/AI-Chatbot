import os
import subprocess
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_requirements():
    """Kiểm tra và cài đặt các thư viện cần thiết"""
    try:
        # Thử import các thư viện cần thiết
        import psycopg2
        import flask
        import sentence_transformers
        logger.info("✅ Đã cài đặt các thư viện cần thiết")
    except ImportError as e:
        logger.info(f"⚠️ Thiếu thư viện: {e}")
        logger.info("⚠️ Đang cài đặt các thư viện cần thiết...")
        
        # Cài đặt psycopg2-binary thay vì psycopg2
        requirements = [
            "flask==2.0.1",
            "flask-cors==3.0.10",
            "sentence-transformers==2.2.2",
            "torch==1.13.1",
            "pymupdf==1.19.6",
            "python-docx==0.8.11",
            "psycopg2-binary==2.9.3",
            "pandas==1.3.5",
            "openpyxl==3.0.10",
            "numpy==1.21.6"
        ]
        
        for req in requirements:
            logger.info(f"Đang cài đặt {req}")
            subprocess.run([sys.executable, "-m", "pip", "install", req])
        
        logger.info("✅ Đã cài đặt xong các thư viện")

def initialize_database():
    """Khởi tạo database"""
    try:
        import init_db
        if init_db.create_database():
            if init_db.create_tables():
                init_db.migrate_existing_data()
                logger.info("✅ Đã khởi tạo database thành công")
                return True
        return False
    except Exception as e:
        logger.error(f"❌ Lỗi khi khởi tạo database: {e}")
        return False

def run_server():
    """Chạy server"""
    try:
        import server
        logger.info("🚀 Đang khởi động server...")
        server.app.run(debug=True)
    except Exception as e:
        logger.error(f"❌ Lỗi khi chạy server: {e}")

if __name__ == "__main__":
    logger.info("🔄 Đang kiểm tra môi trường...")
    check_requirements()
    
    if initialize_database():
        run_server()
    else:
        logger.error("❌ Không thể khởi động server do lỗi database")