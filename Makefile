all: test

test:
	poetry run pytest --log-cli-level=INFO -x --show-capture=stdout
