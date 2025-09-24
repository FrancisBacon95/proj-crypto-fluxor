#!/bin/bash

# VM 부팅 시 자동 실행 스크립트
# proj-crypto-fluxor 프로젝트를 자동으로 시작합니다.

set -e  # 에러 발생 시 스크립트 중단

# ====== 설정 변수 ======
REPO_OWNER="FrancisBacon95"
REPO_NAME="proj-crypto-fluxor"
HOME_DIR="/home/chlwogur34"
REPO_DIR="${HOME_DIR}/${REPO_NAME}"
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

echo "[job] cleanup existing project directory"
rm -rf "${REPO_DIR}" 2>/dev/null || true

echo "[job] clone project from GitHub"
git clone "https://${GITHUB_TOKEN}@github.com/${REPO_OWNER}/${REPO_NAME}.git" "${REPO_DIR}" -b main

echo "[job] navigate to project directory"
cd "${REPO_DIR}"

echo "[job] update vm utility scripts in home directory"

# 새로운 스크립트 파일들 복사
cp -f ${REPO_DIR}/setup.sh ${HOME_DIR}/setup.sh
cp -f ${REPO_DIR}/startup.sh ${HOME_DIR}/startup.sh
cp -f ${REPO_DIR}/reset.sh ${HOME_DIR}/reset.sh

# 실행 권한 부여
chmod +x ${HOME_DIR}/reset.sh
chmod +x ${HOME_DIR}/setup.sh
chmod +x ${HOME_DIR}/startup.sh

echo "[job] install and sync uv package"
cd ${REPO_DIR}
uv sync

