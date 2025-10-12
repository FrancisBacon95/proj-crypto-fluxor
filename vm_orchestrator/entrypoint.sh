#!/usr/bin/env bash
set -euo pipefail

# ===== 설정 (환경변수로 주입) =====
PROJECT_ID="${PROJECT_ID:-proj-asset-allocation}"
REGION="${REGION:-asia-northeast3}"                  # e.g. asia-northeast3
ZONE="${ZONE:-asia-northeast3-a}"
INSTANCE="${INSTANCE:-crypto-fluxor-vm}"              # e.g. crypto-fluxor-vm
STATIC_NAME="${STATIC_NAME:-crypto-fluxor-ip}"        # e.g. crypto-fluxor-ip
ACC_NAME="${ACC_NAME:-External NAT}"  # 기본 Access Config 이름
TIMEOUT="${TIMEOUT:-1800}"            # VM 종료 대기 시간 (초단위, 기본 30분)
ROOT_DIR="${ROOT_DIR:-/opt}"
PORT="${PORT:-8000}"                  # FastAPI port
echo "[job] start orchestration"

# IP 조회 (전제: 다른 데서 안 쓰는 RESERVED 상태)
STATIC_IP="$(gcloud compute addresses describe "$STATIC_NAME" \
  --project="$PROJECT_ID" --region="$REGION" --format='value(address)')"
echo "[job] use static IP: $STATIC_IP"

# 외부 IP 붙이기(있으면 제거)
if gcloud compute instances describe "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE" \
  --format="value(networkInterfaces[0].accessConfigs[0].name)" | grep -q .; then
  # 현재 붙은 외부 IP 조회
  # nic0의 현재 access-config 이름 & IP
  ACC_NAME_CUR="$(gcloud compute instances describe "$INSTANCE" \
    --project="$PROJECT_ID" --zone="$ZONE" \
    --format="value(networkInterfaces[0].accessConfigs[0].name)")"

  CUR_IP="$(gcloud compute instances describe "$INSTANCE" \
    --project="$PROJECT_ID" --zone="$ZONE" \
    --format="value(networkInterfaces[0].accessConfigs[0].natIP)")"

  echo "[job] delete access-config ($ACC_NAME_CUR) $CUR_IP"
  gcloud compute instances delete-access-config "$INSTANCE" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --access-config-name="$ACC_NAME_CUR" \
    --network-interface=nic0
fi

# 외부 IP 붙이기(없으면 바로 추가)
echo "[job] add access-config -> $STATIC_IP"
gcloud compute instances add-access-config "$INSTANCE" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --access-config-name="$ACC_NAME" \
  --network-interface=nic0 \
  --address="$STATIC_IP"

# startup-script 갱신
gcloud compute instances add-metadata "$INSTANCE" \
  --zone="$ZONE" \
  --metadata-from-file startup-script=./startup.sh

# VM 시작
echo "[job] starting instance..."
gcloud compute instances start "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE"

# RUNNING 상태 대기
echo "[job] waiting for RUNNING state..."
BOOT_DEADLINE=$((SECONDS + 600))  # 최대 10분 대기
while :; do
  STATUS=$(gcloud compute instances describe "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE" --format='value(status)')
  if [[ "$STATUS" == "RUNNING" ]]; then
    break
  fi
  if [[ $SECONDS -ge $BOOT_DEADLINE ]]; then
    echo "[err] timeout waiting for RUNNING"
    exit 3
  fi
  sleep 5
done

# FastAPI 서버 준비 대기 (헬스체크: "/")
API_BASE_URL="http://$STATIC_IP:$PORT"
HEALTHCHECK_URL="$API_BASE_URL/"
echo "[job] polling API health: $HEALTHCHECK_URL"
API_DEADLINE=$((SECONDS + 600))  # 최대 10분 대기

while :; do
  response=$(curl -s -X GET "$HEALTHCHECK_URL" --max-time 5 || echo "")
  if [[ -n "$response" ]]; then
    echo "[job] API health OK: $response"
    break
  fi
  if [[ $SECONDS -ge $API_DEADLINE ]]; then
    echo "[err] timeout waiting for API health"
    exit 4
  fi
  echo "[job] waiting for API health... ($((API_DEADLINE - SECONDS))s remaining)"
  sleep 10
done

# 5) API 호출 - run 엔드포인트
RUN_URL="$API_BASE_URL/run"
echo "[job] API URL: $RUN_URL"

# curl로 GET 요청 보내기
response=$(curl -s -X GET "$RUN_URL" \
  -H "Content-Type: application/json" \
  --max-time 30 || echo "curl_failed")

if [ "$response" = "curl_failed" ]; then
  echo "[err] API call failed"
else
  echo "[job] API response: $response"
fi

# 인스턴스 종료 (IP 떼기 전에)
echo "[job] stopping instance..."
gcloud compute instances stop "$INSTANCE" \
  --project="$PROJECT_ID" --zone="$ZONE"

# 인스턴스가 완전히 종료될 때까지 대기
echo "[job] waiting for instance to stop..."
STOP_DEADLINE=$((SECONDS + 300))  # 최대 5분 대기
while :; do
  STATUS=$(gcloud compute instances describe "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE" --format='value(status)')
  [[ "$STATUS" == "TERMINATED" ]] && { echo "[job] instance stopped successfully"; break; }
  [[ $SECONDS -ge $STOP_DEADLINE ]] && { echo "[err] timeout waiting for instance stop"; exit 6; }
  echo "[job] waiting for stop... current status: $STATUS"
  sleep 5
done

# 외부 IP 떼기(비용 절감)
echo "[job] detach access-config"
gcloud compute instances delete-access-config "$INSTANCE" \
  --project="$PROJECT_ID" --zone="$ZONE" \
  --network-interface=nic0 --access-config-name="$ACC_NAME"