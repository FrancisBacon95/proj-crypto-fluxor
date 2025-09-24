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

echo "[job] install git and curl"
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl

echo "[job] install uv package manager"
curl -Ls https://astral.sh/uv/install.sh | sh
echo "export PATH=$HOME/.local/bin:$PATH" >> ~/.bashrc
echo "[job] uv package manager installed"

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

# APP_DIR 모든 파일에 대해 777 권한 부여
chmod 777 ${APP_DIR}/*

# uv 설치(시스템 경로) - 부팅 시 PATH 문제 방지
# 1) /usr/local/bin 우선 설치, 2) 실패 시 사용자 로컬(~/.local/bin)로 폴백
#    설치 후 실제 바이너리 경로를 확인해 변수(UV_BIN)에 담아 사용
echo "[job] install uv (system-wide) if not exists"
export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"

# 설치 시도 1: /usr/local/bin
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found, installing to /usr/local/bin ..."
  curl -LsSf https://astral.sh/uv/install.sh | sh -s -- --install-dir /usr/local/bin || true
fi

# 설치 시도 2: 로컬(~/.local/bin) 폴백
if ! command -v uv >/dev/null 2>&1; then
  echo "[fallback] installing uv to $HOME/.local/bin ..."
  mkdir -p "$HOME/.local/bin"
  curl -LsSf https://astral.sh/uv/install.sh | sh -s -- --install-dir "$HOME/.local/bin" || true
fi

# 설치 결과 확인 및 경로 고정
hash -r || true
UV_BIN="$(command -v uv || true)"
if [ -z "$UV_BIN" ]; then
  echo "[error] uv installation failed. PATH=$PATH"
  ls -l /usr/local/bin || true
  ls -l "$HOME/.local/bin" || true
  exit 1
fi

echo "[job] uv path: $UV_BIN"
"$UV_BIN" --version || true

echo "[job] install and sync uv package"
cd "${REPO_DIR}"
# PATH에 양쪽 경로를 모두 보장하고, 명확히 발견된 uv 경로(UV_BIN)로 실행
export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"
"${UV_BIN}" sync
