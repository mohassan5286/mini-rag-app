# Mini-RAG: Retrieval-Augmented Generation Backend

**Mini-RAG** is a production-ready FastAPI backend for asynchronous Retrieval-Augmented Generation. Engineered with MongoDB and Qdrant, it leverages a strict controller-based architecture and provider factories to completely decouple the core data ingestion and querying pipelines from the underlying LLM and vector database integrations.

---

## Tech Stack

| Component | Technology | Description |
| --- | --- | --- |
| **Framework** | FastAPI | API routing and request handling |
| **Database** | MongoDB (Motor) | Stores project metadata, file references, and chunks |
| **Vector Engine** | Qdrant | Local or remote semantic vector search |
| **LLM & Embeddings** | Cohere / OpenAI | Text embedding generation and LLM response generation |

---

## Requirements

* **Python:** 3.8 or later
* **Environment Management:** [MiniConda](https://docs.conda.io/en/latest/miniconda.html)
* **Infrastructure:** Docker & Docker Compose (for MongoDB and Qdrant services)

---

## Installation & Setup

### 1. Configure the Python Environment

Download and install MiniConda, then create and activate a dedicated environment for the project:

```bash
conda create -n mini-rag python=3.8
conda activate mini-rag

```

### 2. Install Dependencies

Install the required Python packages from the repository root:

```bash
pip install -r requirements.txt

```

### 3. Setup Application Environment Variables

Create the main environment file and populate it with your specific API keys and configuration parameters (e.g., `OPENAI_API_KEY`):

```bash
cp .env.example .env

```

### 4. Run Docker Compose Services

Initialize the backend infrastructure (databases and vector stores) using Docker. Ensure you configure the Docker-specific environment variables first:

```bash
cd docker
cp .env.example .env

```

Start the containers in detached mode:

```bash
docker compose up -d

```

### 5. Start the FastAPI Server

Return to the project root and launch the application using Uvicorn:

```bash
cd ..
cd src
uvicorn main:app --reload

```

The interactive API documentation will be accessible at: `http://localhost:8000/docs`

---

## Application Workflow

To test the complete RAG lifecycle, interact with the endpoints in the following order:

### Step 1: Upload a Document

Stream a file into the project's local asset directory and register it in MongoDB.

* **Endpoint:** `POST /upload/{project_id}`
* **Payload:** Multipart form data (File)

### Step 2: Process & Chunk

Extract the text from the uploaded document and divide it into overlapping logical chunks.

* **Endpoint:** `POST /process/{project_id}`
* **Payload (JSON):**
```json
{
  "chunk_size": 400,
  "overlap_size": 40,
  "do_reset": false
}

```

### Step 3: Push to Vector Database

Generate embeddings for the chunks and store them in the Qdrant vector database.

* **Endpoint:** `POST /index/push/{project_id}`
* **Payload (JSON):**
```json
{
  "do_reset": false
}

```

### Step 4: Check Vector Index Stats (Optional)
Verify that your chunks were successfully embedded and stored by checking the collection's point count and health status.

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

Query the project. The system will search Qdrant for the most relevant context, inject it into the prompt template, and generate an answer using the LLM.

* **Endpoint:** `POST /index/answer/{project_id}`
* **Payload (JSON):**
```json
{
  "text": "What is the main conclusion of the uploaded document?",
  "limit": 5
}

```
