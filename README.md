# RAG for User Manuals

## Folder Structure

```
root/
├── config/                  # System-level parameters
│   ├── llm.yaml             # LLM settings (temperature, models, tokens)
│   └── retriever.yaml       # Retrieval settings (top-k, similarity thresholds)
├── data/                    # Knowledge base and assets
│   ├── raw/                 # Original source documents (PDFs, docs, raw text)
│   ├── processed/           # Cleaned and chunked docs ready for embedding
│   └── vectordb/            # Persisted vector indexes or databases
├── app/                     # Core RAG logic and endpoints
│   ├── __init__.py
│   ├── main.py              # FastAPI or primary orchestration entry point
│   ├── ingest.py            # Document processing pipeline (loading and chunking)
│   ├── retriever.py         # Vector similarity search and reranking
│   ├── generator.py         # Prompt formatting and LLM integration
│   └── utils.py             # Helper functions
```

## Getting Started
1. Install uv
```
pip install uv
uv venv --python 3.12.12
.venv/Scripts/activate
```

2. Install dependencies
```
uv sync
```

3. Cope .env.exmaple to .env file and add API Keys
```

```

4. Run local Qdrant server
```
docker compose up qdrant -d
```

5. Run app.py
```
cd ./src
python -m uvicorn app.main:app --reload
```

6. Run frontend
```
cd ./ui
npm i
npm run dev
```
