#!/usr/bin/env bash
set -eux

# 최신 main 브랜치 가져오기
git pull origin main

# uv 패키지 설치 및 동기화
uv sync --frozen --no-cache

# uv로 실행
uv run main_in_vm.py