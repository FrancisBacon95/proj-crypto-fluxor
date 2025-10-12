
# Cloud Run을 통한 VM Job 실행 플로우

## 개요

Cloud Run을 오케스트레이터로 사용하여 VM에서 특정 작업을 안전하게 실행하는 구조입니다.
VM 내부의 startup.sh는 메타데이터 플래그(IS_TEST)를 확인해 실행 여부를 결정합니다.
이를 통해 자동화된 실행과 디버깅 시 안전성을 동시에 확보합니다.

## 사전 준비
### 1. VM에 startup.sh 등록
VM이 부팅될 때 실행할 스크립트를 준비하고, VM 메타데이터에 등록합니다.  

```bash
gcloud compute instances add-metadata crypto-fluxor-vm \ㄴ
  --zone=asia-northeast3-c \
  --metadata-from-file startup-script=./startup.sh
```

### 2.	IS_TEST 메타데이터 플래그 활용
startup.sh 내부에서는 아래와 같이 IS_TEST 값을 읽어 실행 여부를 결정해야 합니다.
```bash
# 메타데이터 서버에서 IS_TEST 값 가져오기
IS_TEST="$(curl -s -H 'Metadata-Flavor: Google' \
  http://metadata/computeMetadata/v1/instance/attributes/IS_TEST || echo false)"

if [ "$IS_TEST" != "true" ]; then
  echo "[startup] IS_TEST is false → skip"
  exit 0
fi
```

## 실행 단계

### 1. 실행 플래그 설정

  Cloud Run 함수가 VM 실행 전, 메타데이터에 IS_TEST=true를 설정합니다.
  ```bash
  gcloud compute instances add-metadata crypto-fluxor-vm \
    --zone=asia-northeast3-c \
    --metadata=IS_TEST=true
  ```

###  2. STATIC_IP 부착 및 VM 시작

Cloud Run이 예약된 STATIC_IP를 VM에 붙인 뒤 인스턴스를 시작합니다.
VM 부팅 시 startup.sh가 실행되고, IS_TEST=true 조건에 따라 작업을 수행합니다.
```bash
# 변수
REGION="asia-northeast3"
STATIC_NAME="crypto-fluxor-ip"
ZONE="asia-northeast3-c"
VM="crypto-fluxor-vm"

# STATIC_NAME으로 실제 주소 조회
STATIC_IP=$(gcloud compute addresses describe "$STATIC_NAME" \
  --region="$REGION" --format="value(address)")

# VM NIC(nic0)에 Access Config 추가(외부 IP 부여)
gcloud compute instances add-access-config "$VM" \
  --zone="$ZONE" \
  --network-interface=nic0 \
  --access-config-name="External NAT" \
  --address="$STATIC_IP"

# 확인
gcloud compute instances describe "$VM" \
  --zone="$ZONE" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

### 3. VM 내부 작업 및 종료

startup.sh는 지정된 로직을 실행한 후, 작업 완료 시 VM을 shutdown 합니다.

### 4. 실행 플래그 초기화

Cloud Run이 후처리 단계에서 메타데이터를 다시 IS_TEST=false로 변경합니다.
```
gcloud compute instances add-metadata crypto-fluxor-vm \
  --zone=asia-northeast3-c \
  --metadata=IS_TEST=false
```
