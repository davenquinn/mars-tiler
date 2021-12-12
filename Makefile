all: test

install:
	poetry install
	poetry run pip install -r poetry-overrides.txt

test:
	poetry run pytest --log-cli-level=INFO --show-capture=stdout --durations=10

run:
	./run-local