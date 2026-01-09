# DiagWiki

## Explaining Code with Interactive Diagrams, no api calls, no privacy concerns!

DiagWiki analyzes your code and generates diagram-based wiki pages that explain how your system works. Instead of reading walls of text, you explore interactive diagrams where you can click on any component to understand its role. 

It is a local deployment tool that leverages large language models (LLMs) running on your machine via [Ollama](https://ollama.ai), ensuring your code never leaves your environment. **So, no expensive API calls or data privacy concerns!**

## Click the image below to watch the demo video:
[![Demo Video](https://img.youtube.com/vi/NtdctuuEF_8/0.jpg)](https://youtu.be/NtdctuuEF_8)

## What It Solves

1. Understand complex codebase and present architecture visually with query chat boxes for clarity
2. Generate accurate, detailed diagrams automatically from code for documentation
3. Enable complete control of any step of the diagram generation process - either fully automatic or use instruction & designated files to guide the process.

## Use DiagWiki to visualize this project itself

### API Call Workflow for Diagram Generation
![api-call-flow](/imgs/api-call-workflow-for-diagram-generation.svg)

### Backend Architecture
![backend-architecture](/imgs/backend-api-architecture.svg)

### UI State Management and Caching
![ui-state-management](/imgs/ui-state-management-and-caching.svg)

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
# From project root, in one command:
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

Access application at `http://localhost:5173` on default.

## Technical Stack

**Why these choices?**

- **Local Ollama + Python**: Privacy-first. Your code never leaves your machine. LLMs run locally without sending data to external APIs.

- **Python + FastAPI**: Fast development for AI/RAG workflows. Direct integration with AdalFlow (RAG framework) and ChromaDB (vector database).

- **Svelte**: Lightweight and fast. Clean component model without virtual DOM overhead. Perfect for interactive diagram rendering with Mermaid.js.

- **Mermaid.js**: Industry-standard diagram syntax. Supports flowcharts, sequence diagrams, class diagrams, state diagrams, and ER diagrams.

**Stack:**
- Backend: Python, FastAPI, AdalFlow (RAG), Ollama (LLM)
- Frontend: SvelteKit, TypeScript, Mermaid.js

## License

See [LICENSE](LICENSE) file.

