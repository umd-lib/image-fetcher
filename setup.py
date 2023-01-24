from setuptools import setup

setup(
    name='image-fetcher',
    version='1.0.0-dev',
    py_modules=['fetcher', 'iiif'],
    install_requires=[
        'click',
        'codetiming',
        'requests',
        'stomp.py',
    ],
    entry_points={
        'console_scripts': [
            'image-fetch = fetcher:cli',
            'image-fetch-listen = fetcher:stomp_consumer',
            'image-fetch-send = fetcher:stomp_producer'
        ],
    },
)
