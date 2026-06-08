#!/usr/bin/env bash
# BioForge CD Studio 백엔드 실행 (macOS/Linux)
cd "$(dirname "$0")/.."
pip install -r requirements.txt
pip install -r backend/requirements.txt
echo "  http://localhost:8100  에서 프런트엔드가 열립니다."
python -m uvicorn backend.app:app --reload --port 8100
