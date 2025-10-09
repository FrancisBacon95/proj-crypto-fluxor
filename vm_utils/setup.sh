#!/bin/bash
# setup.sh - VM 환경 초기화 스크립트
# - GCP 인증 및 프로젝트 설정
# - 필수 패키지 설치 (git, curl)
# - uv 패키지 매니저 전역 설치
# - GitHub Token을 시스템 전역 환경변수로 등록

set -euo pipefail

PROJECT_ID="proj-asset-allocation"

echo "[job] authenticate with gcloud"
gcloud auth login --no-launch-browser || true
gcloud auth application-default login --no-launch-browser || true

echo "[job] configure project settings"
gcloud config set project "${PROJECT_ID}"

echo "[job] install git and curl"
sudo apt update -y && sudo apt upgrade -y
sudo apt install -y git curl

echo "[job] install uv package manager"
# 1) uv 설치(사용자 로컬에 떨굼)
curl -Ls https://astral.sh/uv/install.sh | sh -s -- --yes
# 2) 전역 경로로 배포
sudo cp "$HOME/.local/bin/uv" /usr/local/bin/uv
sudo chmod 755 /usr/local/bin/uv
echo "[info] uv installed → $(/usr/local/bin/uv --version)"

# 3) 프로젝트 클론
REPO_OWNER="FrancisBacon95"
REPO_NAME="proj-crypto-fluxor"
REPO_DIR="/opt/${REPO_NAME}"
GITHUB_TOKEN="$(gcloud secrets versions access latest --secret=gcp_github_token)"
echo "[job] clone project from GitHub"
git clone "https://${GITHUB_TOKEN}@github.com/${REPO_OWNER}/${REPO_NAME}.git" "${REPO_DIR}" -b main
git config --global --add safe.directory "${REPO_DIR}"

echo "[job] all setup tasks completed"