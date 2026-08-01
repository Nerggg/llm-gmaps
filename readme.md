1. run webui from docker
	`````
	docker run -d -p 3000:8080 \
	  --add-host=host.docker.internal:host-gateway \
	  -v open-webui:/app/backend/data \
	  --name open-webui \
	  --restart always \
	  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
	  ghcr.io/open-webui/open-webui:main
	`````
2. initialize backend
	`````
	cd backend
	python -m venv venv
	source venv/bin/activate
	pip install fastapi uvicorn httpx python-dotenv slowapi pydantic
	`````
	after backend is initialized, run this from root to run backend
	`````
	uvicorn backend.main:app --reload --port 8000
	`````
