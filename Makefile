.PHONY: install test run-backend run-frontend docker-up docker-down clean

install:
	python -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt

test:
	.venv/bin/pytest backend/tests -v

run-backend:
	.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

run-frontend:
	.venv/bin/streamlit run frontend/app.py --server.port 8501

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	rm -rf __pycache__ .pytest_cache *.db chroma_data
