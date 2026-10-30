# Cisco Cricket Log Intelligence

A containerized cricket log intelligence application that combines structured data storage, vector similarity search, and a local LLM to search and retrieve relevant cricket events using natural-language queries.

## Features

- Parses cricket log files into structured event records.
- Stores cricket events in MongoDB.
- Uses Qdrant for vector-based semantic search.
- Generates embeddings using `sentence-transformers/all-MiniLM-L6-v2`.
- Uses a local Ollama LLM (`qwen2.5:0.5b`) for query processing or response generation.
- Exposes search functionality through a Django REST API.
- Provides a web interface built with HTML, CSS, and JavaScript.
- Runs Django, MongoDB, and Qdrant in Docker containers.
+

## Technology Stack

- **Backend:** Python, Django REST Framework, Gunicorn
- **Frontend:** HTML, CSS, JavaScript
- **Database:** MongoDB
- **Vector Database:** Qdrant
- **Embeddings:** Sentence Transformers
- **Local LLM:** Ollama, Qwen 2.5 0.5B
- **Containerization:** Docker, Docker Compose

## Prerequisites

Install the following before running the project:

- Python 3.11
- Docker Desktop with Docker Compose
- Git
- Ollama for Windows
- The Ollama model `qwen2.5:0.5b`

## Project Setup

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd "Cisco Cricket_log Intelligence"
```

Replace the repository URL with your actual GitHub URL.

### 2. Configure environment variables

Create a `.env` file in the project root using `.env.example` as a reference.

Configure the required MongoDB credentials and database settings. Use your own strong credentials; never commit `.env` to Git.

The Docker Compose configuration must use the service names `mongodb` and `qdrant` for connections from the Django container.

### 3. Start Ollama

Install Ollama, then run:

```powershell
ollama pull qwen2.5:0.5b
ollama list
```

Ensure Ollama is running on the Windows host and the model is available.

### 4. Start the backend and databases

From the project root:

```powershell
docker compose up -d
```

Check container status:

```powershell
docker compose ps
```

View Django logs if needed:

```powershell
docker logs --tail 100 cricket-django
```

The Django API should be available at:

`http://127.0.0.1:8000/api/search/`

### 5. Start the frontend

Open another PowerShell terminal in the project root and run:

```powershell
python -m http.server 5500 --directory frontend
```

Open the application in your browser:

`http://127.0.0.1:5500/`

Keep this terminal open while using the frontend.

## API

**Search endpoint**

```text
POST http://127.0.0.1:8000/api/search/
```

Use the request body expected by the application's search API. For example, if your endpoint accepts a `query` field:

```json
{
  "query": "Show events for MATCH001"
}
```

The exact request schema depends on the implemented API view.

## Stopping the Application

Stop the frontend using `Ctrl+C` in its terminal.

Stop the Docker services with:

```powershell
docker compose stop
```

To start them again:

```powershell
docker compose up -d
```

Persistent MongoDB and Qdrant data are stored in Docker volumes. Avoid `docker compose down -v` unless you intentionally want to remove the volumes and their data.

## Notes

- Docker images contain application software, not the existing database contents.
- A fresh clone does not automatically include your MongoDB records, Qdrant vectors, or local Ollama model.
- Data ingestion and vector indexing may be required on a new machine.
- Keep credentials, private datasets, database backups, and generated secrets out of version control.

## Future Improvements

- Automated API and integration tests.
- Authentication and API rate limiting.
- Automated database backup and recovery.
- Deployment to a remote server.
