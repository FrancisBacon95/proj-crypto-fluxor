#!/bin/bash

# 1) proj-crypto-fluxor 클론 디렉토리 삭제
rm -rf ~/proj-crypto-fluxor

# 4) uv 제거 (설치 스크립트로 깔린 ~/.cargo/bin/uv 기준)
rm -f ~/.cargo/bin/uv
rm -rf ~/.local/share/uv ~/.cache/uv

# 5) Git 제거
sudo apt remove -y git
sudo apt autoremove -y

# 6) apt 캐시 청소 (선택)
sudo apt clean