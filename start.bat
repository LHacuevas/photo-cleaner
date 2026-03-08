@echo off
echo ========================================
echo   Photo Cleaner - Quick Start
echo ========================================
echo.

REM Check if backend venv exists
if not exist ".venv" (
    echo [1/4] Creating Python virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r backend\requirements.txt
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
start "Photo Cleaner Backend" cmd /k "call .venv\Scripts\activate && cd backend && python main.py"

timeout /t 3 /nobreak >nul

echo [4/4] Starting frontend...
start "Photo Cleaner Frontend" cmd /k "cd frontend && npm start"

echo.
echo ========================================
echo   Photo Cleaner is starting!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3001
echo ========================================
echo.
echo Press any key to exit this window...
pause >nul
