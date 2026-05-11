FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /simulation

RUN pip install --no-cache-dir fastapi uvicorn

COPY simulation/mock-services /simulation

