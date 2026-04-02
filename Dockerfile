FROM python:3.14.0-slim AS base

WORKDIR /opt/image-fetcher
COPY --parents pyproject.toml ./src/** /opt/image-fetcher/
RUN pip install -e .

FROM base AS image-fetch-listen
ENTRYPOINT ["image-fetch-listen"]

FROM base AS image-fetch-send
ENTRYPOINT ["image-fetch-send"]

FROM base AS image-fetch
ENTRYPOINT ["image-fetch"]
