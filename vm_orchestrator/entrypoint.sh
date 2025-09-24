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
ROOT_DIR="${ROOT_DIR:-/home/chlwogur34}"
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
  --metadata-from-file startup-script=${ROOT_DIR}/startup.sh

# VM 시작
echo "[job] starting instance..."
gcloud compute instances start "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE"

# SSH 가능해질 때까지 대기 (최대 10분)
echo "[job] waiting for SSH to become available..."
BOOT_DEADLINE=$((SECONDS + 600))
until gcloud compute ssh "$INSTANCE" \
  --project="$PROJECT_ID" --zone="$ZONE" \
  --command="true" >/dev/null 2>&1; do
  [[ $SECONDS -ge $BOOT_DEADLINE ]] && { echo "[err] timeout waiting for SSH"; exit 3; }
  sleep 5
done
echo "[job] SSH available ✅"

# 대상 파일과 uv 실행 가능 여부가 갖춰질 때까지 대기 (최대 15분)
echo "[job] waiting for target command prerequisites..."
READY_DEADLINE=$((SECONDS + 900))
while :; do
  if gcloud compute ssh "$INSTANCE" \
    --project="$PROJECT_ID" --zone="$ZONE" \
    --command="test -f '\''${ROOT_DIR}/${REPO_NAME}/run.sh'\'' && command -v uv >/dev/null"; then
    echo "[job] prerequisites OK ✅"
    break
  fi
  [[ $SECONDS -ge $READY_DEADLINE ]] && { echo "[err] timeout waiting for prerequisites"; exit 4; }
  sleep 5
done

# 원격 실행
echo "[job] execute remote command via SSH"
gcloud compute ssh "$INSTANCE" \
  --project="$PROJECT_ID" --zone="$ZONE" \
  --command="uv run '\''${ROOT_DIR}/${REPO_NAME}/run.sh'\''"

# 종료(TERMINATED)까지 폴링 대기 (타임아웃 30분 예시)
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