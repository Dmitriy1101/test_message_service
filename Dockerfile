FROM python:3.11-alpine3.20

RUN pip install --upgrade pip
COPY ./poetry.lock ./pyproject.toml ./

RUN pip install poetry && \
    pip install poetry-plugin-export  && \
    poetry export --output ./requirements.txt --without-hashes && \
    pip install -r ./requirements.txt


COPY core /core

WORKDIR /core

USER root

RUN adduser --disabled-password server-user

USER server-user