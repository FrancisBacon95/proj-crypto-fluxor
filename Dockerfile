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
RUN pip install poetry
RUN pip install uvicorn
# Cloud Run은 이 포트를 사용합니다.
ENV PORT 8080
CMD ["sh", "-c", "poetry run uvicorn main:app --host 0.0.0.0 --port $PORT"]