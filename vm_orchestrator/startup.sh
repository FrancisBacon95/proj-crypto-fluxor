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
#!/bin/bash
# 리포 이름을 변수화하고, .env와 gcp_service_account.json을 리포 디렉토리 내부에 생성
set -euo pipefail

PROJECT_ID="proj-asset-allocation"

echo "[job] authenticate with gcloud"
gcloud auth login --no-launch-browser || true
gcloud auth application-default login --no-launch-browser || true

echo "[job] configure project settings"
gcloud config set project "${PROJECT_ID}"

echo "[job] install system packages with sudo"
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git curl build-essential python3 python3-pip

echo "[job] install uv package manager system-wide with sudo"
curl -Ls https://astral.sh/uv/install.sh | sudo sh -s -- --install-dir /usr/local/bin
echo "export PATH=/usr/local/bin:\$PATH" | sudo tee -a /etc/environment
echo "[job] uv package manager installed system-wide"

echo "[job] all setup tasks completed"

# 로그 파일 설정
LOG_FILE="/var/log/crypto-fluxor-startup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[job] VM startup script initialized"
echo "=== VM 부팅 시 자동 실행 스크립트 시작 ==="
echo "시작 시간: $(date)"

echo "[job] fetch GitHub token from secrets"
GITHUB_TOKEN="$(gcloud secrets versions access latest --secret=gcp_github_token)"
export GITHUB_TOKEN="$GITHUB_TOKEN"

# 패키지는 이미 앞에서 설치됨

# [/home/app] 디렉토리 사전 생성 및 권한 설정
echo "[job] prepare app directory with sudo"
sudo mkdir -p "${APP_DIR}"
sudo chown "$(whoami):$(whoami)" "${APP_DIR}"
sudo chmod 755 "${APP_DIR}"

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

# APP_DIR 모든 파일에 대해 777 권한 부여
chmod 777 ${APP_DIR}/*

# uv는 이미 앞에서 설치됨
echo "[job] verify uv installation"
export PATH="/usr/local/bin:$PATH"
hash -r || true
which uv && uv --version

echo "[job] install and sync uv package"
cd "${REPO_DIR}"
export PATH="/usr/local/bin:$PATH"
uv sync
