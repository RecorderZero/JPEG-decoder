@PHONY: install-uv
install-uv:
	curl -LsSf https://astral.sh/uv/install.sh | sh

@PHONY: clean
clean:
	rm -rf __pycache__

@PHONY: test
test:
	uv run pytest tests/