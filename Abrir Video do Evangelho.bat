@echo off
cd /d "%~dp0"

if not exist "venv\Scripts\streamlit.exe" (
    echo Nao encontrei o programa instalado nesta pasta.
    echo Peca para a equipe tecnica revisar a instalacao ^(ver README.md^).
    pause
    exit /b 1
)

if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    mkdir "%USERPROFILE%\.streamlit" >nul 2>nul
    (
        echo [general]
        echo email = ""
    ) > "%USERPROFILE%\.streamlit\credentials.toml"
)

echo Abrindo o Video do Evangelho...
echo Uma aba vai abrir sozinha no navegador em alguns segundos.
echo NAO FECHE esta janela enquanto estiver usando o programa.
echo Para encerrar, feche esta janela.
echo.

"venv\Scripts\streamlit.exe" run app\main.py

pause
