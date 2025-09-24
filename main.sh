#!/usr/bin/env bash
set -eux

# 인자 파싱
TEST_MODE=false
if [ "${1:-}" = "--test" ]; then
    TEST_MODE=true
    echo "[job] running in test mode"
else
    echo "[job] running in production mode"
fi

# 최신 main 브랜치 가져오기
echo "[job] pull latest code from main branch"
git pull origin main

# uv 패키지 설치 및 동기화
echo "[job] install and sync uv package"
uv sync

echo "[job] setup environment variables from secrets"
gcloud secrets versions access latest --secret=proj_crypto_fluxor_env > "${REPO_DIR}/.env"
chmod 600 "${REPO_DIR}/.env"
echo "${REPO_DIR}/.env 저장 완료 (chmod 600)"

echo "[job] setup GCP service account credentials"
gcloud secrets versions access latest --secret=gcp_service_account_json > "${REPO_DIR}/gcp_service_account.json"
chmod 600 "${REPO_DIR}/gcp_service_account.json"
echo "${REPO_DIR}/gcp_service_account.json 저장 완료 (chmod 600)"

# uv로 실행 (테스트 모드에 따라 다른 명령어 실행)
if [ "$TEST_MODE" = "true" ]; then
    echo "[job] execute main_in_vm.py with --test flag"
    uv run main_in_vm.py --test
else
    echo "[job] execute main_in_vm.py in production mode"
    uv run main_in_vm.py
fi