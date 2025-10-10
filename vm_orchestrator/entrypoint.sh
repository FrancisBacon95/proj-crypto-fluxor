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
REPO_NAME="proj-crypto-fluxor"
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

# IS_TEST=true 세팅
echo "[job] set IS_TEST=true"
gcloud compute instances add-metadata "$INSTANCE" \
  --project="$PROJECT_ID" --zone="$ZONE" \
  --metadata=IS_TEST=true

# startup-script 갱신
gcloud compute instances add-metadata "$INSTANCE" \
  --zone="$ZONE" \
  --metadata-from-file startup-script=./startup.sh

# VM 시작
echo "[job] starting instance..."
gcloud compute instances start "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE"

# SSH 가능해질 때까지 대기 (최대 10분)
BOOT_DEADLINE=$((SECONDS + 600))

# 1) RUNNING 상태 대기
echo "[job] waiting for RUNNING state..."
while :; do
  STATUS=$(gcloud compute instances describe "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE" --format='value(status)')
  [[ "$STATUS" == "RUNNING" ]] && break
  [[ $SECONDS -ge $BOOT_DEADLINE ]] && { echo "[err] timeout waiting for RUNNING"; exit 3; }
  sleep 5
done

# 2) 외부 IP 확보 대기
echo "[job] waiting for external IP..."
VM_IP=""
LOOP_DEADLINE=$((SECONDS + 180))
while :; do
  VM_IP=$(gcloud compute instances describe "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE" \
    --format='value(networkInterfaces[0].accessConfigs[0].natIP)')
  [[ -n "$VM_IP" ]] && break
  [[ $SECONDS -ge $LOOP_DEADLINE ]] && { echo "[err] timeout waiting for external IP"; exit 3; }
  sleep 3
done

echo "[job] external IP: $VM_IP"

# 3) TCP/22 오픈 대기 (bash tcp redirection 사용)
echo "[job] waiting for SSH port 22 to open..."
LOOP_DEADLINE=$((SECONDS + 180))
while :; do
  if timeout 3 bash -c "</dev/tcp/$VM_IP/22" >/dev/null 2>&1; then
    break
  fi
  [[ $SECONDS -ge $LOOP_DEADLINE ]] && { echo "[err] timeout waiting for port 22"; exit 3; }
  sleep 3
done

echo "[job] SSH available & ready"

# 4) FastAPI 서버 대기 (포트 8000)
echo "[job] waiting for FastAPI server on port 8000..."
API_DEADLINE=$((SECONDS + 600))  # 최대 10분 대기
while :; do
  if timeout 3 bash -c "</dev/tcp/$VM_IP/8000" >/dev/null 2>&1; then
    echo "[job] FastAPI server is ready on port 8000"
    break
  fi
  [[ $SECONDS -ge $API_DEADLINE ]] && { echo "[err] timeout waiting for FastAPI server"; exit 4; }
  echo "[job] waiting for FastAPI server... ($(($API_DEADLINE - $SECONDS))s remaining)"
  sleep 5
done


# 5) API 호출 - /test 엔드포인트
echo "[job] calling /test endpoint"
API_URL="http://$STATIC_IP:8000/test"
echo "[job] API URL: $API_URL"

# curl로 GET 요청 보내기
response=$(curl -s -X GET "$API_URL" \
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