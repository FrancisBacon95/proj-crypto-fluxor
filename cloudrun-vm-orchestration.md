
# Cloud Run을 통한 VM Job 실행 플로우

## 개요

Cloud Run을 오케스트레이터로 사용하여 VM에서 특정 작업을 안전하게 실행하는 구조입니다.
VM 내부에서는 FastAPI 서버가 실행되고, Cloud Run에서 API 호출을 통해 작업을 제어합니다.
이를 통해 자동화된 실행과 원격 제어가 가능한 안전한 구조를 제공합니다.

## 파일 구조

### 1. startup.sh (VM 내부 실행 스크립트)
- **역할**: VM이 켜질 때 자동으로 실행되는 파일
- **위치**: VM의 startup-script 메타데이터로 등록
- **기능**:
  - 프로젝트 코드 업데이트 (git pull)
  - 환경변수 설정 (.env 파일)
  - 의존성 설치 (uv sync)
  - FastAPI 서버 실행 (uvicorn)

### 2. entrypoint.sh (Cloud Run 제어 스크립트)
- **역할**: Cloud Run에서 VM을 제어하는 파일
- **실행 환경**: Cloud Run 컨테이너 내부
- **기능**:
  - VM에 Static IP 할당
  - VM 시작 및 상태 모니터링
  - FastAPI 서버 헬스체크
  - API 호출을 통한 작업 실행
  - VM 종료 및 리소스 정리

### 3. fastapi_app.py (VM 내부 API 서버)
- **역할**: VM 내에서 Cloud Run의 요청을 받아 로직을 실행할 수 있는 서버
- **실행 환경**: VM 내부 (startup.sh에서 실행)
- **제공 엔드포인트**:
  - `GET /`: 헬스체크
  - `GET /run`: 실제 투자 로직 실행
  - `GET /test`: 테스트 모드 실행

## 실행 흐름

### 1. Cloud Run에서 VM 준비 (entrypoint.sh)
Cloud Run이 VM을 시작하고 FastAPI 서버가 준비될 때까지 대기합니다.

```bash
# 1) Static IP를 VM에 할당
STATIC_IP=$(gcloud compute addresses describe "$STATIC_NAME" \
  --region="$REGION" --format="value(address)")

gcloud compute instances add-access-config "$VM" \
  --zone="$ZONE" \
  --network-interface=nic0 \
  --access-config-name="External NAT" \
  --address="$STATIC_IP"

# 2) VM 시작
gcloud compute instances start "$INSTANCE" --zone="$ZONE"

# 3) FastAPI 서버 헬스체크 대기
API_BASE_URL="http://$STATIC_IP:8000"
curl -s -X GET "$API_BASE_URL/" --max-time 5
```

### 2. VM 내부에서 환경 설정 (startup.sh)
VM이 부팅되면 startup.sh가 실행되어 환경을 설정하고 FastAPI 서버를 시작합니다.

```bash
# 1) 프로젝트 코드 업데이트
cd /opt/proj-crypto-fluxor
git pull origin main

# 2) 환경변수 설정
gcloud secrets versions access latest --secret=proj_crypto_fluxor_env > .env

# 3) 의존성 설치
uv sync

# 4) FastAPI 서버 시작
uv run uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --reload
```

### 3. API 호출을 통한 작업 실행 (entrypoint.sh → fastapi_app.py)
FastAPI 서버가 준비되면 Cloud Run에서 API 호출을 통해 작업을 실행합니다.

```bash
# Cloud Run에서 API 호출
RUN_URL="http://$STATIC_IP:8000/run"
response=$(curl -s -X GET "$RUN_URL" \
  -H "Content-Type: application/json" \
  --max-time 30)
```

```python
# fastapi_app.py 에서 실제 로직 실행
@app.get("/run")
def run_endpoint():
    try:
        run()  # main.py의 실제 투자 로직 실행
        return {"status": "ok", "message": "run() executed"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
```

### 4. 리소스 정리 (entrypoint.sh)
작업 완료 후 VM을 종료하고 Static IP를 해제하여 비용을 절감합니다.

```bash
# 1) VM 종료
gcloud compute instances stop "$INSTANCE" --zone="$ZONE"

# 2) 종료 상태 확인
while :; do
  STATUS=$(gcloud compute instances describe "$INSTANCE" --format='value(status)')
  [[ "$STATUS" == "TERMINATED" ]] && break
  sleep 5
done

# 3) Static IP 해제
gcloud compute instances delete-access-config "$INSTANCE" \
  --zone="$ZONE" \
  --network-interface=nic0 \
  --access-config-name="External NAT"
```

## 주요 특징

### 1. API 기반 제어
- Cloud Run에서 VM의 FastAPI 서버로 HTTP 요청을 보내 작업 실행
- `/run`: 실제 투자 로직 실행
- `/test`: 테스트 모드 실행  
- `/`: 헬스체크

### 2. 자동화된 리소스 관리
- VM 시작 시 자동으로 Static IP 할당
- 작업 완료 후 VM 종료 및 IP 해제로 비용 최적화
- 타임아웃 설정으로 무한 대기 방지

### 3. 안전한 실행 환경
- 환경변수는 Google Cloud Secret Manager에서 안전하게 관리
- VM 상태 모니터링을 통한 안정적인 실행
- 에러 발생 시 적절한 정리 작업 수행

## 사전 준비

### 1. VM 서비스 계정 설정
VM이 Google Cloud Secret Manager와 기타 GCP 서비스에 접근할 수 있도록 적절한 서비스 계정을 설정해야 합니다.

```bash
gcloud compute instances set-service-account "YOUR_VM_INSTANCE_NAME" \
  --zone="YOUR_ZONE" --project="YOUR_PROJECT_ID" \
  --service-account=YOUR_SERVICE_ACCOUNT@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --scopes=https://www.googleapis.com/auth/cloud-platform
```


### 2. VM에 startup.sh 등록
```bash
gcloud compute instances add-metadata YOUR_VM_INSTANCE_NAME \
  --zone=YOUR_ZONE \
  --metadata-from-file startup-script=./startup.sh
```

**예시:**
```bash
gcloud compute instances add-metadata YOUR_VM_INSTANCE_NAME \
  --zone=asia-northeast3-c \
  --metadata-from-file startup-script=./startup.sh
```

### 3. Cloud Run에서 entrypoint.sh 실행
```bash
# Cloud Run 컨테이너 내에서
chmod +x entrypoint.sh
./entrypoint.sh
```

### 4. 환경변수 설정
필요한 환경변수들을 Cloud Run에 설정:
- `PROJECT_ID`: GCP 프로젝트 ID
- `REGION`: VM이 위치한 리전
- `ZONE`: VM이 위치한 존
- `INSTANCE`: VM 인스턴스 이름
- `STATIC_NAME`: 사용할 Static IP 이름
