FROM python:3.11-slim-bookworm

ENV BUN_INSTALL=/usr/local/bun

WORKDIR /
COPY requirements.txt .
COPY *.py ./
COPY migrations ./migrations
COPY dependents.json .
COPY ./ts ./ts
COPY ts.sh .

RUN apt-get update \
    && apt-get -y install libpq-dev gcc git ripgrep curl unzip

# Install Bun
RUN curl -fsSL https://bun.sh/install | bash \
    && ln -s $BUN_INSTALL/bin/bun /usr/local/bin/bun

RUN pip install --no-cache-dir -r requirements.txt
RUN cd ts && bun install --frozen-lockfile

CMD ["python", "main.py"]
