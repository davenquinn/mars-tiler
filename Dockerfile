# From here:
# https://stackoverflow.com/questions/53835198/integrating-python-poetry-with-docker
# NOTE: we might want to make things a bit nicer here

# Right now this must be built in the root directory of the Docker-compose project

FROM python:3.9-bullseye

WORKDIR /code

RUN pip install "poetry==1.1.11" && \
  rm -rf /var/lib/apt/lists/* && \
  poetry config virtualenvs.create false

# Fix ca certificates error for LetsEncrypt (late 2021/early 2022 hotfix)
# https://stackoverflow.com/questions/69408776/how-to-force-older-debian-to-forget-about-dst-root-ca-x3-expiration-and-use-isrg
RUN apt update \
  && apt install -y ca-certificates \
  && sed -i '/^mozilla\/DST_Root_CA_X3.crt$/ s/^/!/' /etc/ca-certificates.conf \
  && update-ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Install python tools
COPY ./deps/python-tools ./deps/python-tools/

ENV PIP_DEFAULT_TIMEOUT=100 \
  PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy only requirements to cache them in docker layer
COPY ./poetry.lock ./pyproject.toml /code/

# Project initialization:
RUN poetry install --no-interaction --no-ansi --no-root

ENV GDAL_CACHEMAX 200
ENV GDAL_DISABLE_READDIR_ON_OPEN EMPTY_DIR
ENV GDAL_HTTP_MULTIPLEX YES
ENV GDAL_HTTP_MERGE_CONSECUTIVE_RANGES YES
ENV CPL_VSIL_CURL_ALLOWED_EXTENSIONS ".tif,.vrt,.cog.tif"
ENV VSI_CACHE NO
ENV GDAL_HTTP_VERSION 2
ENV MARS_TILER_PORT 8000
ENV MARS_DATA_DIR /mars-data

# Creating folders, and files for a project:
COPY ./ /code/

# Install the root package
RUN poetry install --no-interaction --no-ansi
# Override some poetry packages with local versions
RUN pip install -r poetry-overrides.txt

# Attempt to fix certificates for LetsEncrypt
# https://github.com/brazil-data-cube/stac.py/issues/112
RUN pip install certifi-system-store && python -m certifi -v


CMD gunicorn mars_tiler:app \
  --bind 0.0.0.0:8000 \
  --workers 8 \
  --worker-class uvicorn.workers.UvicornWorker