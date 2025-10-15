#!/usr/bin/env bash
# ================================================================
# VM 오케스트레이션 실행 스크립트
# ------------------------------------------------
# - 예약된 고정 IP를 항상 붙여서 유지 (화이트리스트용)
# - 필요 시 Compute Engine VM 인스턴스를 시작/중지
# - API 헬스 체크 후 /run 엔드포인트 호출
# - IP를 "in-use" 상태로 유지하여 요금을 낮춤
# ================================================================
set -euo pipefail

# ===== 환경 변수 설정 (기본값 포함) =====
PROJECT_ID="${PROJECT_ID:-proj-asset-allocation}"
REGION="${REGION:-asia-northeast3}"                  # 예: asia-northeast3
ZONE="${ZONE:-asia-northeast3-a}"
INSTANCE="${INSTANCE:-crypto-fluxor-vm}"              # 예: crypto-fluxor-vm
STATIC_NAME="${STATIC_NAME:-crypto-fluxor-ip}"        # 예: crypto-fluxor-ip
ACC_NAME="${ACC_NAME:-External NAT}"  # 기본 Access Config 이름
TIMEOUT="${TIMEOUT:-1800}"            # VM 종료 대기 시간 (초 단위, 기본 30분)
ROOT_DIR="${ROOT_DIR:-/opt}"
PORT="${PORT:-8000}"                  # FastAPI 포트
echo "[job] start orchestration"

# ===== 로깅 헬퍼 & 가드 =====
# STARTED_INSTANCE는 스크립트가 직접 VM을 시작했는지 여부를 추적
# → cleanup()에서 우리가 시작한 VM만 중지하도록 함
STARTED_INSTANCE=false
API_BASE_URL=""

log(){ echo "[log] $*"; }
fail(){ echo "[err] $*" >&2; exit 1; }

# ===== 헬퍼 함수들 =====

# 인스턴스 상태(RUNNING/TERMINATED 등) 조회
get_instance_status(){
  gcloud compute instances describe "$INSTANCE" \
    --project="$PROJECT_ID" --zone="$ZONE" \
    --format='value(status)'
}

# 인스턴스의 nic0에 붙은 외부 NAT IP 조회
get_attached_ip(){
  gcloud compute instances describe "$INSTANCE" \
    --project="$PROJECT_ID" --zone="$ZONE" \
    --format='value(networkInterfaces[0].natIP)'
}

# 예약된 고정 IP가 리전에 존재하는지 확인
# 없으면 실패 (사전에 수동 생성 필요)
ensure_static_ip(){
  log "예약된 고정 IP 확인: $STATIC_NAME ($REGION)"
  STATIC_IP="$(gcloud compute addresses describe "$STATIC_NAME" \
    --project="$PROJECT_ID" --region="$REGION" --format='value(address)' 2>/dev/null || true)"
  [[ -z "$STATIC_IP" ]] && fail "고정 IP '$STATIC_NAME' 이(가) $REGION 에 없음. 먼저 수동으로 생성해야 함."
  log "사용할 고정 IP: $STATIC_IP"
}

# 인스턴스의 NIC(nic0)에 지정된 고정 IP가 붙어 있는지 확인
# 다른 IP/액세스 구성이 있으면 제거 후 교체
ensure_access_config(){
  local current_ip
  current_ip="$(get_attached_ip || true)"
  if [[ -n "$current_ip" && "$current_ip" == "$STATIC_IP" ]]; then
    log "이미 올바른 IP($current_ip)가 붙어 있음 → 생략"
    return 0
  fi

  # 다른 access-config/IP가 붙어 있으면 제거
  local acc_name
  acc_name="$(gcloud compute instances describe "$INSTANCE" \
    --project="$PROJECT_ID" --zone="$ZONE" \
    --format="value(networkInterfaces[0].accessConfigs[0].name)" 2>/dev/null || true)"
  if [[ -n "$acc_name" ]]; then
    log "기존 access-config 제거: ($acc_name) $current_ip"
    gcloud compute instances delete-access-config "$INSTANCE" \
      --project="$PROJECT_ID" --zone="$ZONE" \
      --network-interface=nic0 --access-config-name="$acc_name"
  fi

  log "access-config 추가 -> $STATIC_IP"
  gcloud compute instances add-access-config "$INSTANCE" \
    --project="$PROJECT_ID" --zone="$ZONE" \
    --access-config-name="$ACC_NAME" \
    --network-interface=nic0 \
    --address="$STATIC_IP"

  # 검증
  local attached
  attached="$(get_attached_ip || true)"
  [[ -z "$attached" ]] && fail "access-config 추가 후 IP 없음"
  [[ "$attached" != "$STATIC_IP" ]] && fail "IP 불일치: 기대=$STATIC_IP, 실제=$attached"
  log "access-config 확인 완료: $attached"
}

# 인스턴스가 원하는 상태(RUNNING/TERMINATED)가 될 때까지 대기
wait_for_status(){
  # 사용법: wait_for_status TARGET_STATUS MAX_WAIT_SEC
  local target="$1"; local deadline=$((SECONDS + ${2:-600}))
  log "상태=$target 대기 중 (최대 ${2:-600}초)"
  while :; do
    local s; s="$(get_instance_status || true)"
    if [[ "$s" == "$target" ]]; then
      log "상태=$s"
      break
    fi
    [[ $SECONDS -ge $deadline ]] && fail "상태=$target 대기 타임아웃 (마지막=$s)"
    sleep 5
  done
}

# API 헬스 체크 (200/204/302 응답 시 성공)
# 지수적 backoff로 지정 시간까지 재시도
wait_for_health(){
  # 사용법: wait_for_health URL MAX_WAIT_SEC
  local url="$1"; local deadline=$((SECONDS + ${2:-600}))
  local sleep_s=2
  log "API 헬스 체크: $url (타임아웃 ${2:-600}초)"
  while :; do
    local code
    code=$(curl -s -o /tmp/health_body -w "%{http_code}" -X GET "$url" --max-time 5 || echo "000")
    if [[ "$code" == "200" || "$code" == "204" || "$code" == "302" ]]; then
      local body; body=$(cat /tmp/health_body 2>/dev/null || true)
      log "API OK ($code): ${body:0:120}"
      break
    fi
    [[ $SECONDS -ge $deadline ]] && fail "API 헬스 체크 타임아웃 (마지막 코드=$code)"
    log "API 헬스 체크 대기... ${sleep_s}초 후 재시도"
    sleep "$sleep_s"; (( sleep_s = sleep_s < 20 ? sleep_s * 2 : 20 ))
  done
}

# 종료 시 실행되는 cleanup 핸들러
# 스크립트가 시작한 VM만 중지시킴
cleanup(){
  if [[ "$STARTED_INSTANCE" == true ]]; then
    log "cleanup: 인스턴스 중지"
    gcloud compute instances stop "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE" || true
  fi
}

trap cleanup EXIT ERR INT

# ===== 메인 실행 순서 =====
# 1) 고정 IP 확인
# 2) access-config가 고정 IP로 설정되어 있는지 확인
# 3) startup-script 메타데이터 갱신
# 4) 인스턴스가 꺼져있으면 시작
# 5) RUNNING 상태 될 때까지 대기
# 6) API 헬스 체크
# 7) /run 엔드포인트 호출
# 8) 인스턴스 중지 (IP는 계속 붙여둠)
ensure_static_ip
ensure_access_config

# startup-script 갱신
gcloud compute instances add-metadata "$INSTANCE" \
  --zone="$ZONE" \
  --metadata-from-file startup-script=./startup.sh

# VM 시작 (필요 시만)
STATUS=$(get_instance_status || true)
if [[ "$STATUS" != "RUNNING" ]]; then
  log "인스턴스 시작..."
  STARTED_INSTANCE=true
  gcloud compute instances start "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE"
else
  log "이미 RUNNING 상태 → 시작 생략"
  STARTED_INSTANCE=false
fi

wait_for_status RUNNING 600

API_BASE_URL="http://$STATIC_IP:$PORT"
HEALTHCHECK_URL="$API_BASE_URL/"
wait_for_health "$HEALTHCHECK_URL" 600

# /run 엔드포인트 호출
RUN_URL="$API_BASE_URL/run"
echo "[job] API URL: $RUN_URL"

response=$(curl -s -X GET "$RUN_URL" \
  -H "Content-Type: application/json" \
  --max-time 30 || echo "curl_failed")

if [ "$response" = "curl_failed" ]; then
  echo "[err] API 호출 실패"
else
  echo "[job] API 응답: $response"
fi

log "인스턴스 중지..."
gcloud compute instances stop "$INSTANCE" --project="$PROJECT_ID" --zone="$ZONE"
wait_for_status TERMINATED 300
STARTED_INSTANCE=false

# NOTE: 고정 IP는 NIC에 계속 붙여둬서 'in-use' 상태로 유지 (요금 절감). 분리하지 말 것.