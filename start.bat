@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ローカルLLM文章補正ツール

echo ============================================================
echo  ローカルLLM文章補正ツール を起動します
echo ============================================================
echo.

REM --- Ollama の起動チェック（任意） ---
where ollama >nul 2>nul
if %errorlevel%==0 (
  echo [OK] Ollama コマンドを検出
) else (
  echo [注意] Ollama が見つかりません。先に Ollama を起動してください。
)
echo.

REM --- ホットキー(AHK)を常駐起動 ---
if exist "ahk\hotkeys.ahk" (
  echo ホットキー(AHK)を常駐します...
  start "" "ahk\hotkeys.ahk"
) else (
  echo [注意] ahk\hotkeys.ahk が見つかりません。
)
echo.

REM --- Python を決定（py ランチャ優先） ---
where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)

echo バックエンドを起動します。
echo このウィンドウは開いたままにしてください（閉じると停止します）。
echo.
%PY% run_app.py

echo.
echo バックエンドが終了しました。
pause
