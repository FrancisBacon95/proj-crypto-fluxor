#!/bin/bash

# VM 부팅 시 자동 실행 스크립트
# proj-crypto-fluxor 프로젝트를 자동으로 시작합니다.

set -e  # 에러 발생 시 스크립트 중단

# ====== 설정 변수 ======
APP_DIR="/opt"
REPO_NAME="proj-crypto-fluxor"
REPO_DIR="${APP_DIR}/${REPO_NAME}"
# ======================

echo "[job] VM startup script initialized"
echo "=== VM 부팅 시 자동 실행 스크립트 시작 ==="
echo "시작 시간: $(date)"

# 작업 디렉토리로 이동 (존재 보장 후)
echo "[job] navigate to project directory"
cd "$REPO_DIR"

echo "[job] pull project from GitHub"
git pull origin main

echo "[job] install/update dependencies"
uv sync

echo "[job] start application with uv"
uv run $REPO_DIR/main_in_vm.py --test


