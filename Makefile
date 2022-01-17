all: test

.PHONY: install test run run-docker

install:
	poetry install

test:
	poetry run pytest --log-cli-level=INFO --show-capture=stdout --durations=10

run:
	poetry run ./scripts/run-local

run-docker:
	./scripts/run-docker