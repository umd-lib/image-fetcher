FROM python:3.10.4-slim AS base

WORKDIR /opt/image-fetcher
COPY requirements.txt setup.py /opt/image-fetcher/

RUN pip install -r requirements.txt -e .
COPY * /opt/image-fetcher/

FROM base as image-fetch-listen
ENTRYPOINT ["image-fetch-listen"]

FROM base as image-fetch-send
ENTRYPOINT ["image-fetch-send"]

FROM base as image-fetch
ENTRYPOINT ["image-fetch"]
