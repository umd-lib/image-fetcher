import pytest

from iiif import ImageServer


@pytest.fixture
def image_server():
    return ImageServer('http://example.com/iiif/')


def test_default_params(image_server):
    image_uri = image_server.image_uri('foo')
    assert image_uri.identifier == 'foo'
    assert image_uri.base_uri == 'http://example.com/iiif/foo'
    assert image_uri.info_uri == 'http://example.com/iiif/foo/info.json'
    assert image_uri.region == 'full'
    assert image_uri.size == 'full'
    assert image_uri.rotation == '0'
    assert image_uri.quality == 'default'
    assert image_uri.format == 'jpg'
    assert str(image_uri) == 'http://example.com/iiif/foo/full/full/0/default.jpg'


def test_copies_are_equal_not_identical(image_server):
    image_uri = image_server.image_uri('foo')
    copied_image_uri = image_uri.replace()
    assert copied_image_uri == image_uri
    assert copied_image_uri is not image_uri


def test_params(image_server):
    image_uri = image_server.image_uri('foo', size='80,80', rotation='90', format='png')
    assert image_uri.size == '80,80'
    assert image_uri.rotation == '90'
    assert image_uri.format == 'png'
    # check that defaults are unchanged
    assert image_uri.region == 'full'
    assert image_uri.quality == 'default'
    assert str(image_uri) == 'http://example.com/iiif/foo/full/80,80/90/default.png'


def test_copy_changing_params(image_server):
    image_uri = image_server.image_uri('foo')
    new_uri = image_uri.replace(region='0,0,100,100')
    assert image_uri.region == 'full'
    assert new_uri.region == '0,0,100,100'
