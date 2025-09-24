#!/bin/bash

# VM 부팅 시 자동 실행 스크립트
# proj-crypto-fluxor 프로젝트를 자동으로 시작합니다.

set -e  # 에러 발생 시 스크립트 중단

# ====== 설정 변수 ======
REPO_OWNER="FrancisBacon95"
REPO_NAME="proj-crypto-fluxor"
REPO_DIR="/home/chlwogur34/${REPO_NAME}"
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

echo "[job] setup environment variables from secrets"
gcloud secrets versions access latest --secret=proj_crypto_fluxor_env > .env
chmod 600 .env

echo "[job] setup GCP service account credentials"
gcloud secrets versions access latest --secret=gcp_service_account_json > gcp_service_account.json
chmod 600 gcp_service_account.json

echo "[job] check test mode from instance metadata"
# 메타데이터 서버에서 IS_TEST 값 가져오기
IS_TEST="$(curl -s -H 'Metadata-Flavor: Google' \
  http://metadata/computeMetadata/v1/instance/attributes/IS_TEST || echo false)"
echo "IS_TEST 값: $IS_TEST"

echo "[job] determine script to execute"
# IS_TEST 값에 따라 실행할 스크립트와 인자 결정
SCRIPT_NAME="main.sh"
if [ "$IS_TEST" = "true" ]; then
    SCRIPT_ARGS="--test"
else
    SCRIPT_ARGS=""
fi

echo "[job] execute main script: $SCRIPT_NAME $SCRIPT_ARGS"
echo "$SCRIPT_NAME $SCRIPT_ARGS 실행 중..."
# 스크립트 실행
if [ -n "$SCRIPT_ARGS" ]; then
    ./"$SCRIPT_NAME" $SCRIPT_ARGS
else
    ./"$SCRIPT_NAME"
fi

echo "[job] VM startup script completed"
echo "=== VM 부팅 시 자동 실행 스크립트 완료 ==="
echo "완료 시간: $(date)"

echo "[job] prepare for instance shutdown"
sleep 5

echo "[job] shutdown instance"
# GCP 인스턴스 자동 종료 (sudo 권한 필요)
sudo shutdown -h now
