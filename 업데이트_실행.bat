@echo off
chcp 65001 > nul
title DUVETICA 대시보드 업데이트
color 0A

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   DUVETICA 발주입고현황 대시보드 업데이트   ║
echo  ╚══════════════════════════════════════════╝
echo.

:: 현재 스크립트 위치로 이동
cd /d "%~dp0"

:: Python 설치 확인
python --version > nul 2>&1
if errorlevel 1 (
    echo  [오류] Python이 설치되어 있지 않습니다.
    echo.
    echo  Python 설치 방법:
    echo    1. https://www.python.org/downloads/ 접속
    echo    2. "Download Python" 클릭 후 설치
    echo    3. 설치 시 "Add Python to PATH" 반드시 체크
    echo    4. 설치 완료 후 이 파일을 다시 실행
    echo.
    echo  또는 인터넷 연결 상태에서 index.html 을
    echo  바로 열어도 현재 저장된 데이터로 대시보드를 볼 수 있습니다.
    echo.
    pause
    exit /b
)

:: 입력 파일 확인
if not exist "NEW INPUT\26SS_PO.xlsx" (
    echo  [오류] NEW INPUT 폴더의 데이터 파일을 찾을 수 없습니다.
    echo  "NEW INPUT\" 폴더에 다음 파일이 있어야 합니다:
    echo    26SS_PO.xlsx / 25SS_PO.xlsx
    echo    26SS입고현황.xlsx / 25SS입고현황.xlsx
    echo    24fw-26ss_stylemaster_v8.csv
    echo.
    pause
    exit /b
)

:: 업데이트 실행
echo  엑셀 데이터를 읽어 대시보드를 업데이트합니다...
echo.
python update_dashboard.py
if errorlevel 1 (
    echo.
    echo  [오류] 업데이트 중 문제가 발생했습니다.
    echo  담당자에게 문의해 주세요.
    pause
    exit /b
)

echo.
echo  대시보드를 브라우저로 열겠습니다...
timeout /t 1 /nobreak > nul
start "" "index.html"

echo.
echo  완료! 브라우저에서 대시보드를 확인하세요.
echo  (창을 닫아도 됩니다)
echo.
timeout /t 3 /nobreak > nul
