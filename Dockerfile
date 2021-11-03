# From here:
# https://stackoverflow.com/questions/53835198/integrating-python-poetry-with-docker
# NOTE: we might want to make things a bit nicer here

# Right now this must be built in the root directory of the Docker-compose project

FROM python:3.9

RUN apt-get update && \
  pip install "poetry==1.1.11" && \
  rm -rf /var/lib/apt/lists/* && \
  poetry config virtualenvs.create false

# First, install python tools
COPY ./python-tools /python-tools
WORKDIR /python-tools/birdbrain
RUN poetry install --no-interaction --no-ansi

ENV PIP_DEFAULT_TIMEOUT=100 \
  PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy only requirements to cache them in docker layer
COPY ./tools/tile-server/poetry.lock ./tools/tile-server/pyproject.toml /tools/tile-server/

# Project initialization:
WORKDIR /tools/tile-server
RUN poetry install --no-interaction --no-ansi --no-root

EXPOSE 8000

ENV GDAL_DISABLE_READDIR_ON_OPEN EMPTY_DIR
ENV GDAL_HTTP_MULTIPLEX YES
ENV GDAL_HTTP_VERSION 2

# Creating folders, and files for a project:
COPY ./tools/tile-server /tools/tile-server/

# Install the root package
RUN poetry install --no-interaction --no-ansi 