from setuptools import setup

setup(
    name='image-fetcher',
    version='1.0.0rc3',
    install_requires=[
        'backoff',
        'click',
        'codetiming',
        'requests',
        'stomp.py',
    ],
    extras_require={
        'test': ['pytest']
    },
    entry_points={
        'console_scripts': [
            'image-fetch = fetcher:cli',
            'image-fetch-listen = fetcher:stomp_consumer',
            'image-fetch-send = fetcher:stomp_producer'
        ],
    },
)
