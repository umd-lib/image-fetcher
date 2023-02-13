import logging
import os
from threading import Event
from typing import Union, List

import backoff
import click
import requests
import stomp
from codetiming import Timer
from dotenv import load_dotenv
from requests import RequestException
from stomp import PrintingListener, ConnectionListener, Connection
from stomp.exception import NotConnectedException, ConnectFailedException
from stomp.utils import Frame

from iiif import ImageServer, ImageURI

load_dotenv()

REPO_ENDPOINT_URI = os.environ.get('REPO_ENDPOINT_URI')
IIIF_BASE_URI = os.environ.get('IIIF_BASE_URI')
STOMP_SERVER = os.environ.get('STOMP_SERVER')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
URI_HEADER_NAME = os.environ.get('URI_HEADER_NAME', 'CamelFcrepoUri')
IMAGES_QUEUE = os.environ.get('IMAGES_QUEUE', '/queue/images')
IMAGES_ERROR_QUEUE = os.environ.get('IMAGES_ERROR_QUEUE', '/queue/images.errors')

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)


def get_iiif_identifier(repo_uri: str) -> str:
    assert repo_uri.startswith(REPO_ENDPOINT_URI), \
        f'Repo URI {repo_uri} must start with the endpoint URI {REPO_ENDPOINT_URI}'

    repo_path = repo_uri[len(REPO_ENDPOINT_URI):]
    assert repo_path.startswith('/'), f'Repo path "{repo_path}" must start with "/"'

    return 'fcrepo' + repo_path.replace('/', ':')


def fetch_iiif_image(image_uri: Union[str, ImageURI]):
    try:
        with Timer(logger=None) as timer:
            response = get_url(str(image_uri))
    except RequestException as e:
        logger.error(f'Request error: {e}')
        raise RuntimeError(f'Unable to retrieve {image_uri}; Request error: {e}')

    if response.ok:
        logger.info(f'Fetched {len(response.content)} bytes in {timer.last:0.4f} seconds from {image_uri}')
    else:
        logger.error(f'HTTP error: {response.status_code} {response.reason}')
        raise RuntimeError(f'Unable to retrieve {image_uri}; HTTP error: {response.status_code} {response.reason}')


@backoff.on_exception(backoff.expo, RequestException, max_tries=3)
def get_url(url):
    return requests.get(url)


@click.command()
@click.argument('uris', nargs=-1)
def cli(uris):
    iiif_server = ImageServer(IIIF_BASE_URI)
    for repo_uri in uris:
        try:
            iiif_identifier = get_iiif_identifier(repo_uri)
            full_image_uri = iiif_server.image_uri(iiif_identifier)
            logger.info(f'Converted repo URI {repo_uri} to IIIF URI {full_image_uri}')
            fetch_iiif_image(full_image_uri)
        except (AssertionError, RuntimeError) as e:
            logger.error(e)
            logger.warning(f'Skipping {repo_uri}')


class LoggingListener(PrintingListener):
    def __init__(self, level=logging.INFO):
        super().__init__()
        self.level = level

    # must use the "mangled name" to properly override
    # the "__print" method in the parent class
    def _PrintingListener__print(self, msg, *args):
        logger.log(self.level, msg, *args)


class ProcessingListener(ConnectionListener):
    def __init__(self, connection: Connection):
        self.iiif_server = ImageServer(IIIF_BASE_URI)
        self.connection = connection

    def on_message(self, frame: Frame):
        if URI_HEADER_NAME in frame.headers:
            repo_uri = frame.headers[URI_HEADER_NAME]
            message_id = frame.headers['message-id']
            subscription = frame.headers['subscription']
            destination = frame.headers['destination']
            logger.info(f'Received message on {destination} for repo URI {repo_uri}')
            try:
                frame.headers['IIIFIdentifier'] = get_iiif_identifier(repo_uri)
                frame.headers['IIIFUri'] = self.iiif_server.image_uri(frame.headers['IIIFIdentifier'])
                logger.info(f'Converted repo URI {repo_uri} to IIIF URI {frame.headers["IIIFUri"]}')
                fetch_iiif_image(frame.headers['IIIFUri'])
            except (AssertionError, RuntimeError) as e:
                logger.error(e)
                self.connection.send(
                    destination=IMAGES_ERROR_QUEUE,
                    headers={
                        **frame.headers,
                        'Error': str(e),
                        'original-destination': destination,
                    },
                    body=frame.body,
                )
            finally:
                self.connection.ack(message_id, subscription)


class DisconnectListener(ConnectionListener):
    def __init__(self, disconnected: Event):
        self.disconnected = disconnected

    def on_disconnected(self):
        self.disconnected.set()


def create_stomp_connection(stomp_server, listeners=None, **kwargs) -> Connection:
    logger.debug(stomp_server)
    connection = stomp.Connection11([tuple(stomp_server.split(':', 1))], **kwargs)
    if listeners is None:
        listeners = []
    for name, listener in listeners:
        if isinstance(listener, ConnectionListener):
            connection.set_listener(name, listener)
        elif callable(listener):
            # when given a class or other callable, create a listener by calling
            # it with the current connection
            connection.set_listener(name, listener(connection))
        else:
            logger.error(f'Expecting a ConnectionListener instance or class, or a callable for listener "{name}"')
            raise ValueError
    try:
        connection.connect()
        return connection
    except ConnectFailedException:
        logger.error(f'Unable to connect to STOMP server at {stomp_server}')
        raise


@click.command()
def stomp_consumer():
    disconnected = Event()
    try:
        connection = create_stomp_connection(
            STOMP_SERVER,
            listeners=(
                ('debug', LoggingListener(logging.DEBUG)),
                ('process', ProcessingListener),
                ('disconnect', DisconnectListener(disconnected)),
            ),
        )
    except (ConnectFailedException, ValueError):
        raise SystemExit(1)

    connection.subscribe(IMAGES_QUEUE, 'image-fetcher', ack='client-individual')
    try:
        while not disconnected.wait(1):
            pass
    except KeyboardInterrupt:
        connection.disconnect()


@click.command()
@click.argument('uris', nargs=-1)
def stomp_producer(uris):
    if len(uris) == 0:
        raise SystemExit(0)

    try:
        connection = create_stomp_connection(
            STOMP_SERVER,
            listeners=[('debug', LoggingListener(logging.DEBUG))]
        )
    except (ConnectFailedException, ValueError):
        raise SystemExit(1)

    try:
        send_uris(connection, uris)
    except UnsentURIs as e:
        logger.warning('The following URIs were NOT submitted:')
        for unsent_uri in e.uris:
            logger.warning(unsent_uri)
        raise SystemExit(1)

    if connection.is_connected():
        connection.disconnect()


def send_uris(connection: Connection, uris: List[str]):
    for n, repo_uri in enumerate(uris):
        logger.info(f'Sending repo URI {repo_uri} to stomp://{STOMP_SERVER}{IMAGES_QUEUE} for image pre-fetching')
        try:
            connection.send(
                destination=IMAGES_QUEUE,
                headers={
                    URI_HEADER_NAME: repo_uri
                },
                body='',
                persistent='true',
            )
        except NotConnectedException:
            logger.error(f'Unexpected disconnection from STOMP server at {STOMP_SERVER}')
            raise UnsentURIs(uris[n:])


class UnsentURIs(Exception):
    def __init__(self, uris, *args):
        super().__init__(*args)
        self.uris = uris
