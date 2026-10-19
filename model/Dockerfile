FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
# llama-cpp-python(생성 모델 nlu-gen-v1 실행)은 설치할 때 C++ 로 빌드한다. 빌드 도구는 같은 단계에서 지운다.
# GGML_NATIVE=OFF + AVX2: 빌드한 컴퓨터가 아닌 다른 서버(GKE 등)에서도 돌게
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON"
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake libgomp1     && pip install --no-cache-dir -r requirements.txt     && apt-get purge -y build-essential cmake && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
COPY app ./app
COPY weights ./weights
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
