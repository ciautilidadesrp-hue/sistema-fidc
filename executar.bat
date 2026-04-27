@echo off
cd /d "%~dp0"
echo ============================================================
echo  Sistema de Modelagem de FIDCs
echo ============================================================
echo.

REM ─── 1) Verifica se Python esta instalado ───────────────────
where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH.
    echo Instale o Python em https://www.python.org/downloads/
    echo e marque a opcao "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

REM ─── 2) Cria o ambiente virtual se nao existir ──────────────
if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
    echo.
)

REM ─── 3) Ativa o ambiente virtual ────────────────────────────
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERRO] Falha ao ativar o ambiente virtual.
    pause
    exit /b 1
)

REM ─── 4) Carrega variaveis de ambiente locais (opcional) ─────
if exist "setenv.bat" call setenv.bat

REM ─── 5) Instala dependencias apenas se streamlit faltar ─────
.venv\Scripts\python.exe -c "import streamlit" >nul 2>nul
if errorlevel 1 (
    echo Instalando dependencias... isso pode demorar alguns minutos na primeira vez.
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar dependencias.
        pause
        exit /b 1
    )
    echo.
)

REM ─── 6) Roda o Streamlit ────────────────────────────────────
echo Abrindo o sistema no navegador...
echo (Para encerrar, feche esta janela ou pressione Ctrl+C)
echo.
streamlit run src\app.py

echo.
echo Servidor encerrado.
pause
