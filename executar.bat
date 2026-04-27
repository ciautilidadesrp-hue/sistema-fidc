@echo off
cd /d "%~dp0"
echo Iniciando Sistema de Modelagem de FIDCs...
echo.

REM Verifica se o ambiente virtual existe
if not exist ".venv" (
    echo Criando ambiente virtual...
    python -m venv .venv
    echo.
)

REM Ativa o ambiente virtual
call .venv\Scripts\activate.bat

REM Instala dependencias se necessario
echo Verificando dependencias...
pip install -r requirements.txt --quiet

echo.
echo Abrindo o sistema no navegador...
streamlit run src/app.py

pause