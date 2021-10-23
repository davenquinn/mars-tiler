# From here:
# https://stackoverflow.com/questions/53835198/integrating-python-poetry-with-docker
# NOTE: we might want to make things a bit nicer here

FROM python:3.9

WORKDIR /code

RUN apt-get update && \
  pip install "poetry==1.1.10" && \
  rm -rf /var/lib/apt/lists/*

# Copy only requirements to cache them in docker layer
COPY poetry.lock pyproject.toml /code/

# Project initialization:
RUN --mount=type=cache,target=/root/.cache \
  poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi --no-root

EXPOSE 8000

# Creating folders, and files for a project:
COPY . /code

# Install the root package
RUN poetry install --no-interaction --no-ansi 