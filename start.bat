@echo off
echo ========================================
echo   Photo Cleaner - Quick Start
echo ========================================
echo.

REM Check if backend venv exists
if not exist "backend\venv" (
    echo [1/4] Creating Python virtual environment...
    cd backend
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt
    cd ..
) else (
    echo [1/4] Virtual environment already exists ✓
)

REM Check if node_modules exists
if not exist "frontend\node_modules" (
    echo [2/4] Installing Node dependencies...
    cd frontend
    call npm install
    cd ..
) else (
    echo [2/4] Node dependencies already installed ✓
)

echo [3/4] Starting backend server...
start "Photo Cleaner Backend" cmd /k "cd backend && venv\Scripts\activate && python main.py"

timeout /t 3 /nobreak >nul

echo [4/4] Starting frontend...
start "Photo Cleaner Frontend" cmd /k "cd frontend && npm start"

echo.
echo ========================================
echo   Photo Cleaner is starting!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo ========================================
echo.
echo Press any key to exit this window...
pause >nul
