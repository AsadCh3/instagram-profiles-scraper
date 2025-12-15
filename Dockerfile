FROM apify/actor-python:3.11

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /usr/src/app

COPY requirements.txt .
RUN pip install --no-deps --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "main"]
