@echo off
echo === Khoi dong File Chatbot System ===

REM Kiem tra Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python khong duoc tim thay trong PATH
    echo Dang su dung duong dan day du...
    set PYTHON_PATH="C:\Users\MSI\AppData\Local\Programs\Python\Python313\python.exe"
) else (
    set PYTHON_PATH=python
)

echo === Cai dat cac thu vien can thiet ===
%PYTHON_PATH% -m pip install -r server/requirements.txt

echo === Khoi tao database ===
%PYTHON_PATH% server/init_db.py

echo === Import du lieu ===
%PYTHON_PATH% server/import_qa_data.py

echo === Khoi dong Python server ===
start "Python Server" cmd /k "%PYTHON_PATH% embedding/server.py"

echo === Khoi dong client ===
start "Client" cmd /k "npx live-server client --port=8080"

echo === He thong da khoi dong ===
echo Python server: http://localhost:5000
echo Client: http://localhost:8080
echo Nhan phim bat ky de dong...
pause