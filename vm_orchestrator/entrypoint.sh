#!/usr/bin/env bash
set -euo pipefail

# ===== 설정 (환경변수로 주입) =====
PROJECT_ID="${PROJECT_ID:-proj-asset-allocation}"
REGION="${REGION:-asia-northeast3}"                  # e.g. asia-northeast3
ZONE="${ZONE:-asia-northeast3-c}"                      # e.g. asia-northeast3-c
INSTANCE="${INSTANCE:-crypto-fluxor-vm}"              # e.g. crypto-fluxor-vm
STATIC_NAME="${STATIC_NAME:-crypto-fluxor-ip}"        # e.g. crypto-fluxor-ip
ACC_NAME="${ACC_NAME:-External NAT}"  # 기본 Access Config 이름
TIMEOUT="${TIMEOUT:-1800}"            # VM 종료 대기 시간 (초단위, 기본 30분)
echo "[job] start orchestration"

# 0) IP 조회 (전제: 다른 데서 안 쓰는 RESERVED 상태)
STATIC_IP="$(gcloud compute addresses describe "$STATIC_NAME" \
  --project="$PROJECT_ID" --region="$REGION" --format='value(address)')"
echo "[job] use static IP: $STATIC_IP"

# 1-1) 외부 IP 붙이기(있으면 제거)
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

# 1-2) 외부 IP 붙이기(없으면 바로 추가)
echo "[job] add access-config -> $STATIC_IP"
gcloud compute instances add-access-config "$INSTANCE" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --access-config-name="$ACC_NAME" \
  --network-interface=nic0 \
  --address="$STATIC_IP"

# 2) IS_TEST=true 세팅
echo "[job] set IS_TEST=true"
gcloud compute instances add-metadata "$INSTANCE" \
  --project="$PROJECT_ID" --zone="$ZONE" \
  --metadata=IS_TEST=true

# 3) startup-script 갱신
gcloud compute instances add-metadata "$INSTANCE" \
  --zone="$ZONE" \
  --metadata-from-file startup-script=./startup.sh

# 4) VM 시작
echo "[job] starting instance..."
gcloud compute instances start "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE"

# 5) 종료(TERMINATED)까지 폴링 대기 (타임아웃 30분 예시)
echo "[job] wait for TERMINATED..."
DEADLINE=$((SECONDS + TIMEOUT))
while :; do
  CUR="$(gcloud compute instances describe "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE" \
    --format='value(status)')"
  [[ "$CUR" == "TERMINATED" ]] && { echo "[job] terminated ✅"; break; }
  [[ $SECONDS -ge $DEADLINE ]] && { echo "[err] timeout waiting for VM shutdown"; exit 2; }
  sleep 5
done

# 6) 외부 IP 떼기(비용 절감)
echo "[job] detach access-config"
gcloud compute instances delete-access-config "$INSTANCE" \
  --project="$PROJECT_ID" --zone="$ZONE" \
  --network-interface=nic0 --access-config-name="$ACC_NAME"

# 7) IS_TEST=false 복구
gcloud compute instances add-metadata "$INSTANCE" \
  --project="$PROJECT_ID" --zone="$ZONE" \
  --metadata=IS_TEST=false

echo "[job] done 🎉"