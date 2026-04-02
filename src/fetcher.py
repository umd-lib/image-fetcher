import logging
import os
import re
from functools import cached_property
from threading import Event

import backoff
import click
import requests
import stomp
from codetiming import Timer
from dotenv import load_dotenv
from papaya.iiif2 import ImageService, ImageResource, FULL_IMAGE_PARAMS
from papaya.source import RepositoryService
from requests import RequestException
from stomp import PrintingListener, ConnectionListener, Connection
from stomp.exception import NotConnectedException, ConnectFailedException
from stomp.utils import Frame

load_dotenv()

REPO_ENDPOINT = os.environ.get('REPO_ENDPOINT')
REPO_PREFIX = os.environ.get('REPO_PREFIX')
IIIF_IMAGE_ENDPOINT = os.environ.get('IIIF_IMAGE_ENDPOINT')
IIIF_IMAGE_ORIGIN = os.environ.get('IIIF_IMAGE_ORIGIN', None)
STOMP_SERVER = os.environ.get('STOMP_SERVER')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
URI_HEADER_NAME = os.environ.get('URI_HEADER_NAME', 'CamelFcrepoUri')
IMAGES_QUEUE = os.environ.get('IMAGES_QUEUE', '/queue/images')
IMAGES_ERROR_QUEUE = os.environ.get('IMAGES_ERROR_QUEUE', '/queue/images.errors')

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

HTTP_URI_PREFIXES = re.compile(r'^https?://')


class FetcherContext:
    @cached_property
    def repo_service(self):
        return RepositoryService(endpoint=REPO_ENDPOINT, prefix=REPO_PREFIX)

    @cached_property
    def image_service(self):
        return ImageService(endpoint=IIIF_IMAGE_ENDPOINT, origin=IIIF_IMAGE_ORIGIN)

    def iiif_identifier(self, repo_uri: str) -> str:
        return self.repo_service.get_iiif_id(repo_uri)


def fetch_iiif_image(image_resource: ImageResource):
    full_image_url = image_resource.request_url(FULL_IMAGE_PARAMS)
    logger.info(f'Fetching {full_image_url} for {image_resource.image_id}')
    try:
        with Timer(logger=None) as timer:
            request_url = image_resource.request_url(FULL_IMAGE_PARAMS)
            response = get_url(request_url)
    except RequestException as e:
        logger.error(f'Request error: {e}')
        raise RuntimeError(f'Unable to retrieve {request_url}; Request error: {e}')

    if response.ok:
        logger.info(f'Fetched {len(response.content)} bytes in {timer.last:0.4f} seconds from {request_url}')
    else:
        logger.error(f'HTTP error: {response.status_code} {response.reason}')
        raise RuntimeError(f'Unable to retrieve {request_url}; HTTP error: {response.status_code} {response.reason}')


@backoff.on_exception(backoff.expo, RequestException, max_tries=3)
def get_url(url):
    return requests.get(url)


@click.command()
@click.argument('identifiers', nargs=-1)
def cli(identifiers):
    ctx = FetcherContext()
    for identifier in identifiers:
        try:
            if HTTP_URI_PREFIXES.match(identifier):
                # http: or https: repository URI, convert to a IIIF identifier
                iiif_identifier = ctx.iiif_identifier(identifier)
                logger.debug(f'Converted repo URI {identifier} to IIIF identifier {iiif_identifier}')
            else:
                iiif_identifier = identifier
            resource = ctx.image_service.resource(iiif_identifier)
            fetch_iiif_image(resource)
        except (AssertionError, RuntimeError) as e:
            logger.error(e)
            logger.warning(f'Skipping {identifier}')


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
        self.connection = connection
        self.ctx = FetcherContext()

    def on_message(self, frame: Frame):
        if URI_HEADER_NAME in frame.headers:
            repo_uri = frame.headers[URI_HEADER_NAME]
            message_id = frame.headers['message-id']
            subscription = frame.headers['subscription']
            destination = frame.headers['destination']
            logger.info(f'Received message on {destination} for repo URI {repo_uri}')
            try:
                frame.headers['IIIFIdentifier'] = self.ctx.repo_service.get_iiif_id(repo_uri)
                image_resource = self.ctx.image_service.resource(frame.headers['IIIFIdentifier'])
                frame.headers['IIIFUri'] = image_resource.uri()
                logger.info(f'Converted repo URI {repo_uri} to IIIF URI {frame.headers["IIIFUri"]}')
                fetch_iiif_image(image_resource)
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


def send_uris(connection: Connection, uris: list[str]):
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
