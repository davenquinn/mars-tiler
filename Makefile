all: test

.PHONY: install test run run-docker

install:
	poetry install

test:
	./scripts/run-tests

run:
	poetry run ./scripts/run-local

run-docker:
	./scripts/run-docker