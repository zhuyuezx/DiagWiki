# DiagWiki

**Turn your codebase into interactive visual documentation automatically.**

DiagWiki analyzes your code and generates diagram-based wiki pages that explain how your system works. Instead of reading walls of text, you explore interactive diagrams where you can click on any component to understand its role.

[![Demo Video](https://img.youtube.com/vi/NtdctuuEF_8/0.jpg)](https://youtu.be/NtdctuuEF_8)

## What It Solves

Documentation gets outdated fast and is hard to maintain. Reading code without context is time-consuming.

DiagWiki solves this by:
- **Auto-generating** diagrams from your actual code
- **Visual-first** - diagrams show structure better than text
- **Interactive** - click components for detailed explanations
- **Always current** - regenerate anytime your code changes

## How to Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Ollama running locally
  - Install from [ollama.ai](https://ollama.ai)
  - Pull models: `ollama pull qwen2.5-coder:7b` and `ollama pull nomic-embed-text`
- Conda (recommended) or pip for Python packages

### Setup

1. **Create environment config**

```bash
cd backend
cp .env.example .env
# Edit .env if needed (defaults work for most setups)
```

2. **Install dependencies**

```bash
# Backend
cd backend
conda env create -f environment.yml
conda activate diagwiki

# Frontend
cd ../frontend
npm install
```

3. **Launch**

```bash
# From project root
./launch.sh
```

Or run manually:

```bash
# Terminal 1 - Backend
cd backend
conda activate diagwiki
python main.py

# Terminal 2 - Frontend
cd frontend
npm run dev
```

Access at `http://localhost:5173` on default.

## Technical Stack

**Why these choices?**

- **Local Ollama + Python**: Privacy-first. Your code never leaves your machine. LLMs run locally without sending data to external APIs.

- **Python + FastAPI**: Fast development for AI/RAG workflows. Direct integration with AdalFlow (RAG framework) and ChromaDB (vector database).

- **Svelte**: Lightweight and fast. Clean component model without virtual DOM overhead. Perfect for interactive diagram rendering with Mermaid.js.

- **Mermaid.js**: Industry-standard diagram syntax. Supports flowcharts, sequence diagrams, class diagrams, state diagrams, and ER diagrams.

**Stack:**
- Backend: Python, FastAPI, AdalFlow (RAG), Ollama (LLM), ChromaDB
- Frontend: SvelteKit, TypeScript, Mermaid.js

## License

See [LICENSE](LICENSE) file.

