# Copyright 2026 Primel Jayawardana
# SPDX-License-Identifier: Apache-2.0

from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="smartcache",
    version="1.0.0",
    author="Primel Jayawardana",
    author_email="primel@primelj.dev",
    description="Intelligent in-memory caching with LRU/LFU eviction, TTL, and thread-safety",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/primelj/smartcache",
    packages=find_packages(exclude=["tests*", "examples*"]),
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Caching",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "pytest-xdist>=3.0",
        ]
    },
)
