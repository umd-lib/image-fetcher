from dataclasses import dataclass, replace


class ImageServer:
    def __init__(self, base_uri: str):
        self.base_uri = base_uri

    def image_uri(self, identifier: str, **params) -> 'ImageURI':
        return ImageURI(server=self, identifier=identifier, **params)


@dataclass
class ImageURI:
    server: ImageServer
    identifier: str
    region: str = 'full'
    size: str = 'full'
    rotation: str = '0'
    quality: str = 'default'
    format: str = 'jpg'

    @property
    def base_uri(self):
        return self.server.base_uri + self.identifier

    @property
    def info_uri(self):
        return self.base_uri + '/info.json'

    def __str__(self):
        return f'{self.base_uri}/{self.region}/{self.size}/{self.rotation}/{self.quality}.{self.format}'

    def __call__(self, *args, **kwargs):
        return self.replace(**kwargs)

    def replace(self, **params):
        return replace(self, **params)
