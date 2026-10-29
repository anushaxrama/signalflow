.PHONY: setup ingest serve worker test check
setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.lock
ingest:
	.venv/bin/python -m signalflow.cli ingest --days 7
serve:
	.venv/bin/python -m signalflow.cli serve
worker:
	.venv/bin/python -m signalflow.cli worker
test:
	.venv/bin/pytest -q
check:
	.venv/bin/python -m signalflow.cli check
