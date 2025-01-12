FROM python:3.9-slim

WORKDIR /app

# Copy the necessary files to the working directory
COPY . .

# Set PYTHONPATH
ENV PYTHONPATH "${PYTHONPATH}:/app"

# Debug: List files in /app and print PYTHONPATH

RUN ls -R /app

RUN echo $PYTHONPATH

# Install dependencies
# Install dependencies
RUN pip install 'poetry>=1.8,<1.9'
RUN poetry export --without-hashes --format=requirements.txt > requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Cloud Run은 이 포트를 사용합니다.
ENV PORT 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]