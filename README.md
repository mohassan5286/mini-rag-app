Here is the cleaned and properly formatted `README.md`, with the conversational artifacts removed and the markdown structure fixed:

# Mini-RAG: Retrieval-Augmented Generation Backend

Mini-RAG is a FastAPI backend for Retrieval-Augmented Generation. It uses PostgreSQL (`pgvector`), RabbitMQ, and Celery to cleanly separate data processing and background tasks from your LLMs.

### Tech Stack

| Component | Technology | Description |
| --- | --- | --- |
| **Framework** | FastAPI | API routing and request handling |
| **Database & Vector Engine** | PostgreSQL (`pgvector`) | Stores project metadata, file references, chunks, and semantic vectors |
| **Message Broker** | RabbitMQ | Reliable message routing for background tasks |
| **Result Backend / Cache** | Redis | Stores Celery task states and temporary caching |
| **Background Processing** | Celery & Celery Beat | Asynchronous document parsing, chunking, and periodic scheduling |
| **LLM & Embeddings** | Cohere / OpenAI | Text embedding generation and LLM response generation |

### Requirements

* **Python:** 3.10 or later
* **Environment Management:** [MiniConda](https://docs.conda.io/en/latest/miniconda.html)
* **Infrastructure:** Docker & Docker Compose

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/mohassan5286/mini-rag-app.git
cd mini-rag-app

```

### 2. Configure Environment Variables

#### Root Application Config

```bash
cp .env.example .env

```

#### Docker & Database Service Configs

Navigate to `docker/env` and create the active config files from each template:

```bash
cd docker/env

cp .env.example.app .env.app
cp .env.example.postgres .env.postgres
cp .env.example.redis .env.redis
cp .env.example.rabbitmq .env.rabbitmq
cp .env.example.grafana .env.grafana
cp .env.example.postgres-exporter .env.postgres-exporter

cd ../..

```

#### Database Migrations Config

```bash
cp docker/minirag/alembic.example.ini docker/minirag/alembic.ini

```

---

## Option A: Local Development Workflow

This setup runs data stores and message queues in Docker while running the application logic natively on your host machine for instant reload, interactive debugging, and fast iteration.

### 1. Start Core Infrastructure Containers

Spin up only PostgreSQL (`pgvector`), Redis, and RabbitMQ:

```bash
cd docker
docker compose up -d pgvector redis rabbitmq
cd ..

```

### 2. Configure Local Python Environment

Create and activate a virtual environment, then install requirements:

```bash
conda create -n mini-rag python=3.10 -y
conda activate mini-rag
pip install -r src/requirements.txt

```

### 3. Run Database Migrations

Apply Alembic migrations to generate tables and initialize the `pgvector` extension:

```bash
# 1. Copy the template to the correct schema directory
cp docker/minirag/alembic.example.ini src/models/db_schemes/minirag/alembic.ini

# 2. Run the migration using the copied config
alembic -c src/models/db_schemes/minirag/alembic.ini upgrade head

```

### 4. Run Services Across Dedicated Terminals

Open separate terminals (ensure you run `conda activate mini-rag` in each one):

* **Terminal 1 — FastAPI Server:**

```bash
cd src
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

```

*Swagger UI Documentation:* `http://localhost:8000/docs`

* **Terminal 2 — Celery Worker:**

```bash
python -m celery -A celery_app worker --queues=default,file_processing,data_indexing --pool=solo --loglevel=info

```

* **Terminal 3 — Celery Beat Scheduler:**

```bash
celery -A celery_app beat --loglevel=info

```

* **Terminal 4 — Flower Monitoring UI (Optional):**

```bash
celery -A src.celery_app flower --port=5555

```

*Flower UI:* `http://localhost:5555`

---

## Option B: Production Deployment Workflow

This workflow covers deploying the containerized stack to a server and enabling automated GitHub Actions CI/CD.

### 1. Server Provisioning & Sudo User Setup

Log into your Ubuntu server as `root` to create a dedicated deployment user:

```bash
adduser github_user
usermod -aG sudo github_user
su - github_user

```

### 2. Configure SSH Access & Deploy Keys

Generate an SSH key pair on the server so it can securely pull from your repository:

```bash
ssh-keygen -t ed25519 -C "deploy_key@local-vps" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub

```

* Copy the outputted public key.
* In your GitHub repository, navigate to **Settings > Deploy keys > Add deploy key** and paste the key.
* Clone the project into the user workspace:

```bash
mkdir -p ~/workspace && cd ~/workspace
git clone git@github.com:mohassan5286/mini-rag-app.git
cd mini-rag-app

```

*(Remember to configure your `.env` files here as outlined in the initial setup section).*

### 3. Configure Systemd Service & Permissions

Set up `minirag.service` so the OS manages your Docker stack, and allow the deployment user to restart it without a password.

* Allow passwordless systemctl execution:

```bash
sudo visudo

```

* Add this exact line to the bottom of the file:
`github_user ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart minirag.service, /usr/bin/systemctl daemon-reload`
* Install and start the systemd service:

```bash
sudo cp docker/minirag.service /etc/systemd/system/minirag.service
sudo systemctl daemon-reload
sudo systemctl enable minirag.service
sudo systemctl start minirag.service

```

### 4. Configure GitHub Actions Secrets

In your GitHub repository, navigate to **Settings > Secrets and variables > Actions** and create the following repository secrets to allow the pipeline to connect to your server:

| Secret Name | Value Description |
| --- | --- |
| `HOST_IP` | Public VPS IP address or active TCP tunnel endpoint |
| `HOST_PORT` | SSH port (`22` for standard VPS, or forwarding port if tunneled) |
| `HOST_USERNAME` | `github_user` |
| `HOST_SSH_KEY` | Private SSH key capable of logging into `github_user` |

Whenever a push is made to the target branch (e.g., `arch/sql-pgvector`), the `.github/workflows/deploy.yml` pipeline will connect via SSH, pull updated commits, and restart `minirag.service`.

---

## Application Workflow

To test the complete RAG lifecycle, interact with the endpoints in the following order:

### Step 1: Upload a Document

Stream a file into the project's local asset directory and register it in the database.

* **Endpoint:** `POST /upload/{project_id}`
* **Payload:** Multipart form data (File)

### Step 2: Process & Chunk (Asynchronous)

Extract the text from the uploaded document and divide it into overlapping logical chunks. This process is offloaded to the Celery workers.

* **Endpoint:** `POST /process/{project_id}`
* **Payload (JSON):**

```json
{
  "file_id": "file_id", 
  "chunk_size": 400,
  "overlap_size": 40,
  "do_reset": false
}

```

### Step 3: Push to Vector Database (Asynchronous)

Generate embeddings for the chunks and store them in PostgreSQL (`pgvector`).

* **Endpoint:** `POST /index/push/{project_id}`
* **Payload (JSON):**

```json
{
  "do_reset": false
}

```

### Step 4: Check Vector Index Stats (Optional)

Verify that your chunks were successfully embedded and stored by checking the collection's row count and health status.

* **Endpoint:** `GET /index/info/{project_id}`

### Step 5: Test Semantic Search (Optional)

Test the retrieval pipeline without triggering the LLM generation. This returns the raw chunks most semantically similar to your query.

* **Endpoint:** `POST /index/search/{project_id}`
* **Payload (JSON):**

```json
{
  "text": "What is the main conclusion of the uploaded document?",
  "limit": 5
}

```

### Step 6: Ask a RAG Question

Query the project. The system will search `pgvector` for the most relevant context, inject it into the prompt template, and generate an answer using the LLM.

* **Endpoint:** `POST /index/answer/{project_id}`
* **Payload (JSON):**

```json
{
  "text": "What is the main conclusion of the uploaded document?",
  "limit": 5
}

```

---

### Step 7: Combined Process & Push (Alternative Workflow)

Execute both the document chunking and vector embedding ingestion in a single, streamlined asynchronous API call. This bypasses the need to trigger the processing and pushing steps separately.

* **Endpoint:** `POST /process-and-push/{project_id}`
* **Payload (JSON):**

```json
{
  "file_id": "file_id",
  "chunk_size": 20,
  "overlap_size": 20,
  "do_reset": true
}

```
