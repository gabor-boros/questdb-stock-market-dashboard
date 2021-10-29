FROM python:3.8-slim

ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH /app

RUN apt-get update && apt-get install -y gcc python3-dev libpq-dev

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY . /app

WORKDIR /app
ENTRYPOINT [ "/app/scripts/entrypoint.sh" ]