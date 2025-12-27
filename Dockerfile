
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y default-jre && \
    apt-get clean

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install gunicorn

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]