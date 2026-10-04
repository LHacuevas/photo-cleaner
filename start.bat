@echo off
echo ========================================
echo   Photo Cleaner - Inicio rapido
echo ========================================
echo.

REM Entorno virtual de Python
if not exist ".venv" (
    echo [1/4] Creando entorno virtual de Python...
    python -m venv .venv
)

REM Siempre se sincronizan las dependencias: es rapido si ya estan al dia
REM y evita errores tras actualizar el proyecto.
echo [2/4] Comprobando dependencias...
call .venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check -r backend\requirements.txt
pushd frontend
call npm install --no-audit --no-fund --loglevel=error
popd

echo [3/4] Arrancando el backend...
start "Photo Cleaner Backend" cmd /k "cd backend && ..\.venv\Scripts\python.exe main.py"

timeout /t 3 /nobreak >nul

echo [4/4] Arrancando el frontend...
start "Photo Cleaner Frontend" cmd /k "cd frontend && npm start"

echo.
echo ========================================
echo   Photo Cleaner se esta iniciando
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo ========================================
echo.
echo Pulsa una tecla para cerrar esta ventana...
pause >nul
