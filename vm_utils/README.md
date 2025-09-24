# proj-vm-utils

GCP VM에서 proj-crypto-fluxor 프로젝트를 자동화하여 설정, 실행, 정리하는 유틸리티 스크립트 모음입니다.

## 📋 개요

이 프로젝트는 Google Cloud Platform(GCP) 가상 머신에서 crypto-fluxor 프로젝트를 효율적으로 관리하기 위한 자동화 스크립트들을 제공합니다.

## 🚀 스크립트 설명

### 1. `setup.sh` - 초기 환경 설정
VM 환경을 처음 설정할 때 실행하는 스크립트입니다.

**주요 기능:**
- gcloud CLI 로그인 (브라우저 없이)
- GCP 프로젝트 설정
- Git, curl 등 필수 도구 설치
- GitHub 토큰을 GCP Secret Manager에서 가져와 환경변수 설정
- proj-crypto-fluxor 리포지토리 클론
- `.env` 파일 및 `gcp_service_account.json` 파일을 Secret Manager에서 다운로드
- uv (Python 패키지 매니저) 설치

**사용법:**
```bash
chmod +x setup.sh
./setup.sh
```

### 2. `startup.sh` - VM 부팅 시 자동 실행
VM이 부팅될 때 자동으로 proj-crypto-fluxor 프로젝트를 실행하는 스크립트입니다.

**주요 기능:**
- 프로젝트 디렉토리 확인 및 이동
- main.sh 실행 권한 부여 및 실행
- 실행 로그를 `/var/log/crypto-fluxor-startup.log`에 기록
- 작업 완료 후 자동으로 VM 종료

**사용법:**
```bash
chmod +x startup.sh
sudo ./startup.sh
```

**GCP 메타데이터로 부팅 시 자동 실행 설정:**
```bash
# VM 생성 시 또는 수정 시
gcloud compute instances add-metadata INSTANCE_NAME \
  --metadata startup-script='#!/bin/bash
cd /path/to/proj-vm-utils
./startup.sh'
```

### 3. `reset.sh` - 환경 정리
설정된 환경을 정리하고 초기화하는 스크립트입니다.

**주요 기능:**
- proj-crypto-fluxor 클론 디렉토리 삭제
- uv 및 관련 캐시 파일 제거
- Git 제거
- apt 캐시 정리

**사용법:**
```bash
chmod +x reset.sh
./reset.sh
```

## 📁 프로젝트 구조

```
proj-vm-utils/
├── README.md          # 프로젝트 설명서
├── setup.sh          # 초기 환경 설정 스크립트
├── startup.sh        # VM 부팅 시 자동 실행 스크립트
└── reset.sh          # 환경 정리 스크립트
```

## 🔧 사용 시나리오

### 1. 새로운 VM 환경 설정
```bash
# 1. 리포지토리 클론
git clone https://github.com/FrancisBacon95/proj-vm-utils.git
cd proj-vm-utils

# 2. 초기 환경 설정
./setup.sh
```

### 2. VM 부팅 시 자동 실행 설정
```bash
# VM 메타데이터에 startup-script 추가
gcloud compute instances add-metadata YOUR_INSTANCE_NAME \
  --metadata startup-script-url="gs://your-bucket/startup.sh"
```

### 3. 환경 초기화가 필요한 경우
```bash
./reset.sh
```

## ⚙️ 요구 사항

- **GCP 프로젝트**: `proj-asset-allocation`
- **필요한 Secret Manager 항목**:
  - `gcp_github_token`: GitHub 개인 액세스 토큰
  - `proj_crypto_fluxor_env`: 프로젝트 환경변수 파일
  - `gcp_service_account_json`: GCP 서비스 계정 키 파일
- **권한**: gcloud CLI 사용 권한 및 Secret Manager 접근 권한

## 📝 참고사항

- 모든 스크립트는 bash로 작성되었습니다.
- `setup.sh`는 strict mode (`set -euo pipefail`)로 실행됩니다.
- `startup.sh`는 작업 완료 후 자동으로 VM을 종료합니다.
- 로그는 `/var/log/crypto-fluxor-startup.log`에 저장됩니다.

## 🔒 보안

- GitHub 토큰과 서비스 계정 키는 GCP Secret Manager를 통해 안전하게 관리됩니다.
- `gcp_service_account.json` 파일은 `chmod 600`으로 권한이 제한됩니다.
- 민감한 정보는 환경변수로 관리되며 셸 프로파일에 영구 저장됩니다.
