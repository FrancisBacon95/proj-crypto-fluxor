#!/bin/bash

# VM 부팅 시 자동 실행 스크립트
# proj-crypto-fluxor 프로젝트를 자동으로 시작합니다.

set -e  # 에러 발생 시 스크립트 중단

# ====== 설정 변수 ======
REPO_OWNER="FrancisBacon95"
REPO_NAME="proj-crypto-fluxor"
APP_DIR="/home/app"
REPO_DIR="${APP_DIR}/${REPO_NAME}"
# ======================

# 로그 파일 설정
LOG_FILE="/var/log/crypto-fluxor-startup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[job] VM startup script initialized"
echo "=== VM 부팅 시 자동 실행 스크립트 시작 ==="
echo "시작 시간: $(date)"

echo "[job] fetch GitHub token from secrets"
GITHUB_TOKEN="$(gcloud secrets versions access latest --secret=gcp_github_token)"
export GITHUB_TOKEN="$GITHUB_TOKEN"

# [필수 패키지 확보] git, curl 설치 (없으면 설치)
if ! command -v git >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
  echo "[job] install required packages (git, curl)"
  sudo apt-get update && sudo apt-get install -y git curl
fi

# [/home/app] 디렉토리 사전 생성 및 권한 설정
echo "[job] prepare app directory"
# 디렉토리가 이미 있을 경우를 대비해 -p 옵션 사용 (존재해도 에러 없음)
if [ ! -d "${APP_DIR}" ]; then
  sudo mkdir -p "${APP_DIR}"
fi
sudo chown "$(whoami):$(whoami)" "${APP_DIR}"

# 작업 디렉토리로 이동 (존재 보장 후)
cd "$APP_DIR"

echo "[job] cleanup existing project directory"
rm -rf "${REPO_DIR}" 2>/dev/null || true

echo "[job] clone project from GitHub"
git clone "https://${GITHUB_TOKEN}@github.com/${REPO_OWNER}/${REPO_NAME}.git" "${REPO_DIR}" -b main

echo "[job] navigate to project directory"
cd "${REPO_DIR}"

echo "[job] update vm utility scripts in home directory"

# 새로운 스크립트 파일들 복사
cp -f ${REPO_DIR}/vm_utils/setup.sh ${APP_DIR}/setup.sh
cp -f ${REPO_DIR}/vm_utils/reset.sh ${APP_DIR}/reset.sh

# 실행 권한 부여
chmod +x ${APP_DIR}/setup.sh
chmod +x ${APP_DIR}/reset.sh

# uv 설치(시스템 경로) - 부팅 시 PATH 문제 방지
echo "[job] install uv (system-wide) if not exists"
export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found, installing to /usr/local/bin ..."
  curl -LsSf https://astral.sh/uv/install.sh | sh -s -- --install-dir /usr/local/bin
fi
echo "[job] uv path: $(command -v uv)"
uv --version || true

echo "[job] install and sync uv package"
cd ${REPO_DIR}
export PATH="$HOME/.local/bin:$PATH"
uv sync
