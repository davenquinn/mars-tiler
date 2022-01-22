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

test-docker:
	docker-compose build tile_server
	docker-compose run --rm tile_server scripts/run-tests