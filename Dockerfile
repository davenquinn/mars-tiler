# From here:
# https://stackoverflow.com/questions/53835198/integrating-python-poetry-with-docker
# NOTE: we might want to make things a bit nicer here

# This is basically the setup of RasterIO's own Dockerfile.
# CA certificates should now be managed by the GDAL base image.
FROM osgeo/gdal:ubuntu-small-3.3.3 AS base
ENV LANG="C.UTF-8" LC_ALL="C.UTF-8"
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  python3 python3-pip python3-dev python3-venv cython3 g++ gdb postgresql-client && \
  rm -rf /var/lib/apt/lists/*

WORKDIR /code/deps/rasterio
COPY ./deps/rasterio/requirements*.txt ./
RUN python3 -m venv /code/.venv && \
  /code/.venv/bin/python -m pip install -U pip && \
  /code/.venv/bin/python -m pip install -r requirements-dev.txt

COPY ./deps/rasterio /code/deps/rasterio
RUN /code/.venv/bin/python setup.py install

RUN apt-get update && apt-get install -y postgresql-client

FROM base AS main

WORKDIR /code/

RUN pip3 install "poetry==1.1.12" && \
  rm -rf /var/lib/apt/lists/* && \
  poetry config virtualenvs.in-project true

WORKDIR /code

# Install local dependencies
COPY ./deps/python-tools /code/deps/python-tools

ENV PIP_DEFAULT_TIMEOUT=100 \
  PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy only requirements to cache them in docker layer
COPY ./poetry.lock /code/
COPY ./pyproject.toml /code/

# # Project initialization:
RUN poetry install --no-interaction --no-ansi --no-root

EXPOSE 8000

ENV MARS_TILER_PORT 8000
ENV GDAL_CACHEMAX 200
ENV GDAL_DISABLE_READDIR_ON_OPEN EMPTY_DIR
ENV GDAL_HTTP_MULTIPLEX YES
ENV GDAL_HTTP_MERGE_CONSECUTIVE_RANGES YES
ENV CPL_VSIL_CURL_ALLOWED_EXTENSIONS ".tif,.TIF,.tiff"
ENV VSI_CACHE NO
ENV GDAL_HTTP_VERSION 2
ENV VSI_CACHE TRUE
ENV VSI_CACHE_SIZE 200000

# Creating folders, and files for a project:
COPY ./ /code/

# Install the root package
RUN poetry install --no-interaction --no-ansi

CMD .venv/bin/gunicorn mars_tiler:app \
  --bind 0.0.0.0:8000 \
  --workers 8 \
  --worker-class uvicorn.workers.UvicornWorker