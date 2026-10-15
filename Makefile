.PHONY: test seed demo api

test:
	python -m pytest --cov=policy --cov-fail-under=90

seed:
	python scripts/seed.py

demo:
	python scripts/demo_run.py

api:
	python -m uvicorn app.main:app --app-dir backend --port 8000
