# fastapi_app.py
import uvicorn
from fastapi import FastAPI

# 👉 현재 파일의 코드가 main.py라면 아래 임포트를 맞게 바꿔주세요.
# from main import run, test
from main_in_vm import run, test  # ← 파일/모듈명에 맞게 수정

app = FastAPI(title="Crypto Auto Trader API", version="1.0.0")


@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/run")
def run_endpoint():
    try:
        run()  # run()은 반환값이 없으므로 Slack/로그로 확인
        return {"status": "ok", "message": "run() executed"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/test")
def test_endpoint():
    try:
        result = test()  # {'result': 'ok', ...} 형태
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


if __name__ == "__main__":
    uvicorn.run("fastapi_app:app", host="0.0.0.0", port=8000, reload=True)
