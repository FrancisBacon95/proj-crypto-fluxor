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
# RUN poetry export --without-hashes --format=requirements.txt > requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt

# Cloud Run은 이 포트를 사용합니다.
EXPOSE 8080
CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]