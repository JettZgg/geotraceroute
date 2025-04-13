from setuptools import setup, find_packages

setup(
    name="geotraceroute",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi==0.104.1",
        "uvicorn==0.24.0",
        "python-dotenv==1.0.0",
        "redis==5.0.1",
        "pytest==7.4.3",
        "python-multipart==0.0.6",
        "geoip2==4.8.0",
        "aiohttp==3.9.3",
        "jinja2==3.1.3",
        "maxminddb==2.5.1",
        "pytest-asyncio==0.21.1",
        "httpx==0.25.1",
    ],
    entry_points={
        'console_scripts': [
            'geotraceroute=geotraceroute.main:main',
        ],
    },
    python_requires=">=3.9",
    package_data={
        'geotraceroute': [
            'web/static/*',
            'web/templates/*',
        ],
    },
) 