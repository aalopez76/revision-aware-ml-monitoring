# The weekly job runs in this container. It is a batch job: no server, no
# orchestrator, no Kubernetes. The reason is in the README, "Outside Scope".
#
# The container builds the same virtual environment the project is developed in,
# from the same lockfile, so a figure produced here is a figure produced there.
FROM python:3.11-slim

# Pinned: an unpinned installer is an unpinned environment.
RUN pip install --no-cache-dir uv==0.11.19

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# --frozen fails if the lockfile and pyproject.toml have drifted apart, which is
# the behaviour we want: better a failed build than a silent resolution. The
# dev extra is not installed; this image runs the job, it does not test it.
RUN uv sync --frozen

COPY scripts/ ./scripts/

# One weekly pull. Nothing is trained here; training is a separate step so that
# a failed pull cannot silently produce a model.
CMD ["/app/.venv/bin/python", "scripts/weekly_capture.py"]
