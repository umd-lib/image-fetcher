# image-fetcher

Utilities to fetch images stored in Fedora through the IIIF Image API

## Why?

The initial use-case for these utilities was to pre-warm a Cantaloupe IIIF Image Server
image cache with images retrieved from a Fedora 4 repository. Pre-warming was required
because the network retrieval speed for large images from Fedora 4 is not fast enough
to provide a smooth user experience when viewing them in a IIIF Image Viewer.

## Quick Start

```bash
git clone git@github.com:umd-lib/image-fetcher.git
cd image-fetcher
pyenv install -s $(cat .python-version)
python -m venv .venv
pip install -r requirements.txt -e .

# configuration is done through environment variables
export REPO_ENDPOINT_URI=https://fcrepo-qa.lib.umd.edu/fcrepo/rest
export IIIF_BASE_URI=https://iiif-qa.lib.umd.edu/images/iiif/2/
export STOMP_SERVER=127.0.0.1:63613

# pre-fetch an image directly
image-fetch {FCREPO_URI}

# start the STOMP listener in the background
# and write the log file to image-fetch.log
image-fetch-listen 2> image-fetch.log &

# send a message to request a pre-fetch
image-fetch-send {FCREPO_URI}
```

## Utilities

### image-fetch

Directly fetch zero or more images via IIIF based on their Fedora URI.

### image-fetch-listen

Listen for requests to fetch an image via IIIF based on its Fedora URI.
Connects to a STOMP server host and port (`STOMP_SERVER`; e.g., `localhost:61613`)
and listens on a queue (`IMAGES_QUEUE`; default is `/queue/images`) for messages
with a Fedora URI in a specific header (`URI_HEADER_NAME`; default is `CamelFcrepoUri`).

When it receives such a message, it translates that URI to a IIIF Image URI,
and requests that new URI.

If there are any problems processing the message (e.g., a bad URI, network error,
etc.), the listener sends a NACK frame to the STOMP server. This should result in
the message being put into the dead-letter queue. By default, on ActiveMQ the
dead-letter queue name is `ActiveMQ.DLQ`.

### image-fetch-send

Send zero or more requests to fetch an image to the `IMAGES_QUEUE` on `STOMP_SERVER`.

Each URI given on the command line generates its own message.

## Configuration

Configuration of the utilities is done through environment variables:

| Name                | Required | Default Value    |
|---------------------|----------|------------------|
| `REPO_ENDPOINT_URI` | **Yes**  |                  |
| `IIIF_BASE_URI`     | **Yes**  |                  |
| `STOMP_SERVER`      | **Yes**  |                  |
| `LOG_LEVEL`         | No       | `INFO`           |
| `URI_HEADER_NAME`   | No       | `CamelFcrepoUri` |
| `IMAGES_QUEUE`      | No       | `/queue/images`  |

These can either be specified in the environment itself or via a `.env` file.
