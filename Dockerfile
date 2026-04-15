FROM python:3.14.0-slim AS base

WORKDIR /opt/image-fetcher
COPY pyproject.toml /opt/image-fetcher/
COPY src/ /opt/image-fetcher/src/
RUN pip install -e .

FROM base AS image-fetch-listen
ENTRYPOINT ["image-fetch-listen"]

FROM base AS image-fetch-send
ENTRYPOINT ["image-fetch-send"]

FROM base AS image-fetch
ENTRYPOINT ["image-fetch"]
