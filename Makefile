# Everything runs inside .venv, managed by uv against uv.lock. Never the global
# interpreter: a figure produced under different versions is not the same
# figure, and a development hook blocks the global one outright.
#
# There is no target for an entry point that does not exist yet. G0's and G1's
# scripts appear here when they are written, not before.

.PHONY: install lint test verify capture all

install:
	uv sync --locked --extra dev

lint:
	uv run ruff check .

test:
	uv run pytest

verify:
	uv run python scripts/verify_results.py

# What the scheduled job runs. Leaves one dated file in reports/weekly/.
capture:
	uv run python scripts/weekly_capture.py

all: lint test verify
