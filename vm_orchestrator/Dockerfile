# gcloud 포함 공식 이미지
FROM gcr.io/google.com/cloudsdktool/cloud-sdk:slim

WORKDIR /app
RUN apt-get update && apt-get install -y bash curl jq && rm -rf /var/lib/apt/lists/*

COPY . .
RUN chmod +x /app/entrypoint.sh
CMD ["/app/entrypoint.sh"]