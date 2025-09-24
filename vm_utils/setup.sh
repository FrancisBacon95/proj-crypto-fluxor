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