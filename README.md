# proj-crypto-fluxor

## 📊 개요

`proj-crypto-fluxor`는 머신러닝 기반의 암호화폐 자동 투자 시스템입니다. 
데이터 분석과 예측 모델을 활용하여 암호화폐 거래를 자동화하고, 
비트코인 적립식 투자를 통해 안정적인 포트폴리오를 구성합니다.

## 🎯 주요 기능

### 1. ML 모델 기반 거래 로직
- **CTREND 모델**: LightGBM 기반의 암호화폐 가격 예측 모델
- **기술적 지표**: RSI, MACD, 볼린저 밴드, 스토캐스틱 등 다양한 기술적 지표 활용
- **데이터 기반 의사결정**: 과거 데이터와 시장 지표를 종합하여 매수/매도 결정

### 2. 비트코인 적립식 투자
- **정기 적립**: 설정된 금액으로 비트코인 정기 매수
- **리스크 분산**: 변동성 높은 알트코인과 안정적인 비트코인의 균형 투자
- **자동화**: 수동 개입 없이 지속적인 투자 실행

## 🏗️ 시스템 아키텍처

### 핵심 모듈

#### 📈 `ctrend_model.py` - 예측 모델
```python
class CTRENDAllocator:
    - LightGBM 기반 회귀 모델
    - 7일 후 가격 변동률 예측
    - 시가총액 필터링으로 거래 대상 선정
```

#### 🔧 `feature_store.py` - 피처 엔지니어링
```python
class FeatureStoreByCrypto:
    - 모멘텀 오실레이터 (RSI, Stochastic, CCI)
    - 이동평균 지표 (SMA, MACD)
    - 거래량 지표 (Volume SMA, Chaikin)
    - 변동성 지표 (Bollinger Bands, Markov Regime)
```

#### 💰 `trader.py` - 거래 실행
```python
def execute_sell_logic():  # 매도 로직
def execute_buy_logic():   # 매수 로직
def sell_expired_crypto(): # 만료 자산 정리
```

#### 🚀 `main.py` - 메인 실행 엔진
```python
def run():  # 전체 투자 로직 실행
def test(): # 테스트 모드 실행
```

## 📋 투자 전략

### 1. 데이터 수집 및 전처리
- **거래소**: 빗썸 일별 OHLCV 데이터
- **시가총액**: CoinMarketCap 데이터로 거래 대상 필터링
- **시장 심리**: Fear & Greed Index 활용

### 2. 예측 모델 학습
- **학습 데이터**: 과거 2년간의 일별 데이터
- **피처**: 50+ 기술적 지표 및 시장 지표
- **타겟**: 7일 후 가격 변동률

### 3. 포트폴리오 구성
- **롱 포지션**: 예측 점수 상위 20% 종목 매수
- **숏 포지션**: 예측 점수 하위 20% 종목 매도
- **리밸런싱**: 만료된 포지션 자동 정리 (40일 기준)

## 🌐 클라우드 인프라

### Google Cloud Platform 기반 운영
- **VM 인스턴스**: 모델 학습 및 거래 실행
- **BigQuery**: 대용량 시계열 데이터 저장
- **Cloud Run**: VM 오케스트레이션 및 스케줄링
- **Secret Manager**: API 키 및 환경변수 안전 관리

### 자동화 워크플로우
1. **Cloud Run**에서 VM 인스턴스 시작
2. **startup.sh**로 환경 설정 및 FastAPI 서버 실행
3. **entrypoint.sh**에서 API 호출로 거래 로직 트리거
4. 거래 완료 후 VM 자동 종료로 비용 최적화

## 📁 프로젝트 구조

```
proj-crypto-fluxor/
├── main.py                 # 메인 실행 파일
├── fastapi_app.py          # API 서버 (VM 내부)
├── src/
│   ├── ctrend_model.py     # ML 예측 모델
│   ├── feature_store.py    # 피처 엔지니어링
│   ├── trader.py           # 거래 실행 로직
│   ├── bithumb.py          # 빗썸 API 클라이언트
│   ├── upbit.py            # 업비트 API 클라이언트
│   └── connection/         # 외부 서비스 연결
│       ├── bigquery.py     # BigQuery 연결
│       ├── slack.py        # Slack 알림
│       └── gsheets.py      # Google Sheets
├── vm_orchestrator/
│   ├── entrypoint.sh       # Cloud Run 제어 스크립트
│   └── startup.sh          # VM 시작 스크립트
└── vm_utils/               # VM 관련 문서 및 설정
```

## 🔧 설치 및 실행

### 환경 요구사항
- Python 3.9+
- UV 패키지 매니저
- Google Cloud SDK
- 암호화폐 거래소 API 키 (빗썸, 업비트)

### 로컬 실행
```bash
# 의존성 설치
uv sync

# 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 및 설정값 입력

# 테스트 실행
python main.py --test

# 실제 거래 실행
python main.py
```

### 클라우드 배포
```bash
# VM 서비스 계정 설정
gcloud compute instances set-service-account "YOUR_VM_INSTANCE" \
  --service-account=YOUR_SERVICE_ACCOUNT@PROJECT_ID.iam.gserviceaccount.com

# startup 스크립트 등록
gcloud compute instances add-metadata YOUR_VM_INSTANCE \
  --metadata-from-file startup-script=./vm_orchestrator/startup.sh

# Cloud Run에서 실행
./vm_orchestrator/entrypoint.sh
```

## 📊 모니터링 및 알림

### Slack 통합
- 거래 실행 결과 실시간 알림
- 에러 발생 시 즉시 알림
- 일일 투자 성과 리포트

### 로깅 시스템
- KST 기준 타임스탬프
- 파일별 상세 로그 기록
- 거래 내역 BigQuery 저장

## ⚠️ 리스크 관리

### 자동 안전장치
- **만료 자산 정리**: 40일 초과 보유 자산 자동 매도
- **예산 분산**: 선정된 종목 수만큼 균등 분할 투자
- **예외 처리**: 주요 코인(BTC) 거래 제외 설정

## 📈 성과 지표

- **일일 수익률**: 전날 대비 포트폴리오 변동률
- **샤프 비율**: 위험 조정 수익률
- **최대 낙폭**: 포트폴리오 최대 손실폭
- **승률**: 수익 거래 비율

## 📄 라이선스

이 프로젝트는 개인 투자 목적으로 제작되었습니다. 
투자 결과에 대한 책임은 사용자에게 있으며, 
실제 투자 시 충분한 검토와 위험 관리가 필요합니다.

---
