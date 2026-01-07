# DiagWiki

**AI-powered diagram-first wiki that automatically generates interactive Mermaid diagrams from your codebase.**

## What It Does

DiagWiki transforms any codebase into an interactive visual wiki where **diagrams are the primary content**, not supplements. It uses LLM + RAG to:

- Automatically analyze your codebase and identify key architectural aspects
- Generate comprehensive Mermaid diagrams (flowchart, sequence, class, state, erDiagram)
- Provide interactive explanations for every node and edge
- Fix broken diagrams with intelligent error correction
- Answer questions about your codebase using RAG

## Problem It Solves

Traditional documentation becomes outdated quickly and is text-heavy. DiagWiki solves this by:

- **Auto-generating** up-to-date visual documentation from your actual code
- **Diagram-first** approach - visual understanding beats walls of text
- **Interactive** - click any component to see detailed explanations
- **Self-healing** - automatically fixes diagram syntax errors
- **RAG-powered** - grounds all content in your actual codebase

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Ollama running locally (for LLM inference)
    - Use `ollama pull [model_name]` to download models
    - Generation Model tested: `qwen2.5-coder:7b`, `qwen3-coder:30b`
    - Embedding Model tested: `nomic-embed-text`

### Backend Setup

```bash
cd backend
conda env create -f environment.yml
conda activate diagwiki
python main.py
```

Backend runs on `http://localhost:8001`

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`. Use any web browser to access and interact with DiagWiki.

## Core Features

### 1. **Automatic Section Identification** (3-Iteration System)
- Analyzes your codebase using RAG
- Identifies 2-5 key architectural aspects
- Assigns relevant files to each diagram section

### 2. **Intelligent Diagram Generation**
- Supports multiple diagram types (flowchart, sequence, class, state, ER)
- Generates node/edge explanations automatically
- Validates Mermaid syntax before rendering

### 3. **Interactive Diagram Viewer**
- Click nodes/edges to see detailed explanations
- Tabbed interface for multiple diagrams
- Real-time Mermaid rendering

### 4. **Smart Error Correction**
- Detects Mermaid syntax errors automatically
- Uses LLM to fix broken diagrams
- Provides specific error guidance (e.g., ER vs class diagram syntax)

### 5. **RAG-Powered Q&A**
- Ask questions about any diagram
- Retrieves relevant code context
- Grounded answers with source citations

### 6. **Caching & Persistence**
- Caches generated diagrams for fast reloading
- Stores wiki data in structured JSON format
- Manual diagram editing support

## Configuration

All configuration is in `backend/const/const.py`. Key settings:

**LLM Configuration:**
- `GENERATION_MODEL`: LLM model (default: `qwen3-coder:30b`)
- `EMBEDDING_MODEL`: Embedding model (default: `nomic-embed-text`)
- `OLLAMA_HOST`: Ollama server URL (default: `http://localhost:11434`)
- `LLM_TIMEOUT`: API timeout in seconds (default: 120)
- `OLLAMA_KEEP_ALIVE`: Keep model loaded duration (default: `10m`)

**RAG Configuration:**
- `RAG_TOP_K`: Documents per query (default: 40)
- `RAG_SECTION_ITERATION_TOP_K`: Higher retrieval for section identification (default: 80)
- `MAX_RAG_CONTEXT_CHARS`: Max context size (default: 100,000)

**Generation Parameters:**
- `DEFAULT_TEMPERATURE`: Creative generation (default: 0.7)
- `FOCUSED_TEMPERATURE`: Focused tasks (default: 0.3)
- `LARGE_CONTEXT_WINDOW`: Context window (default: 16,384)
- `MAX_WORKERS`: Thread pool size (default: 4)

## Tech Stack

**Backend:**
- FastAPI (REST API)
- AdalFlow (RAG framework)
- Ollama (LLM inference)
- ChromaDB (vector database)

**Frontend:**
- SvelteKit
- Mermaid.js (diagram rendering)
- TypeScript

## Project Structure

```
DiagWiki/
├── backend/
│   ├── main.py              # FastAPI server
│   ├── api.py               # API endpoints
│   ├── const/               # Configuration & prompts
│   ├── utils/               # Core logic (RAG, diagram generation, wiki)
│   └── data/                # Generated wikis & cache
├── frontend/
│   └── src/
│       ├── routes/          # SvelteKit pages
│       └── lib/components/  # UI components
└── README.md
```

## API Endpoints

- `POST /identifyDiagramSections` - Auto-identify diagram sections
- `POST /generateSectionDiagram` - Generate diagram for a section
- `POST /fixCorruptedDiagram` - Fix broken diagram syntax
- `POST /askDiagramQuestion` - Q&A about diagrams
- `POST /updateDiagram` - Update diagram manually
- `GET /constants` - Get system configuration

## License

See [LICENSE](LICENSE) file for details.
