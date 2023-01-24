FROM python:3.10.4-slim

WORKDIR /opt/image-fetcher
COPY requirements.txt setup.py /opt/image-fetcher/

RUN pip install -r requirements.txt -e .
COPY * /opt/image-fetcher/

CMD 'image-fetch-listen'
