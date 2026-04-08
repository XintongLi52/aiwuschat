FROM python:3.12-alpine AS builder

RUN pip install --no-cache-dir --prefix=/install flask flask-cors openai gunicorn

FROM python:3.12-alpine

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . .

RUN mkdir -p uploads

EXPOSE 8080

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "--timeout", "240", "server:app"]
