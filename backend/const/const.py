from adalflow.components.model_client.ollama_client import OllamaClient as _AdalOllamaClient
import ollama


class TimeoutOllamaClient(_AdalOllamaClient):
    """
    OllamaClient with configurable timeout.
    
    The base AdalFlow OllamaClient doesn't expose timeout configuration,
    so we override the init methods to add it.
    """
    
    def __init__(self, host: str = None, timeout: float = None):
        """Initialize with optional timeout."""
        self._timeout = timeout
        super().__init__(host=host)
    
    def init_sync_client(self):
        """Create the synchronous client with timeout."""
        self.sync_client = ollama.Client(
            host=self._host,
            timeout=self._timeout
        )
    
    def init_async_client(self):
        """Create the async client with timeout."""
        self.async_client = ollama.AsyncClient(
            host=self._host,
            timeout=self._timeout
        )

class Const:
    CODE_EXTENSIONS = [
        ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".hpp", ".go", ".rs",
        ".jsx", ".tsx", ".html", ".css", ".php", ".swift", ".cs", ".svelte", ".rb",
        # Backend & Scripts
        ".sql", ".sh", ".bash", ".pl", ".scala", ".kt", ".kts", ".m", ".mm",
        # Frontend & Modern Web
        ".vue", ".astro", ".less", ".scss", ".sass", ".graphql", ".gql",
        # Config as Code
        ".tf", ".hcl", ".dockerfile"
    ]
    DOC_EXTENSIONS = [
        ".md", ".txt", ".rst", ".json", ".yaml", ".yml",
        # Configuration & Schema
        ".toml", ".ini", ".conf", ".cfg", ".xml", ".csv", ".tsv",
        ".env.example", ".lock", ".jsonl", ".proto"
    ]
    DIR_SKIP_LIST = [
        "node_modules", "venv", "__pycache__", ".git", "dist", "build", ".venv",
        # IDEs & System
        ".idea", ".vscode", ".vs", ".DS_Store", "thumbs.db",
        # Package Manager Artifacts
        "packages", "vendor", "bower_components", ".npm", ".yarn",
        # Testing & Coverage
        "coverage", ".nyc_output", ".pytest_cache", ".tox",
        # Build & Cache
        "target", "out", "bin", "obj", ".cache", ".next", ".nuxt", ".svelte-kit",
        # Mobile Artifacts
        "Pods", "DerivedData", ".gradle"
    ]

    # ============================================================
    # LLM Configuration - IMPORTANT FOR RELIABILITY
    # ============================================================
    # Timeout (seconds) for LLM API calls
    # This prevents indefinite hangs when Ollama is busy or reloading models
    LLM_TIMEOUT = 180.0  # 3 minutes - enough for model reload + generation
    
    # Keep-alive duration for Ollama models (prevents frequent reloads)
    # Set to "10m" to keep model loaded for 10 minutes after last request
    # This reduces cold-start delays significantly for the 30B model
    OLLAMA_KEEP_ALIVE = "10m"
    
    # Host configuration
    OLLAMA_HOST = "http://localhost:11434"

    EMBEDDING_CONFIG = {
        "client": TimeoutOllamaClient(timeout=30.0),  # Embeddings are fast, shorter timeout
        "model_kwargs": {
        "model": "nomic-embed-text"
        }
    }

    TEXT_SPLIT_CONFIG = {
        "split_by": "word",
        "chunk_size": 350,
        "chunk_overlap": 50,
    }

    GENERATION_MODEL = "qwen3-coder:30b"
    EMBEDDING_MODEL = "nomic-embed-text"


def get_llm_client():
    """
    Get an OllamaClient configured with proper timeout.
    
    This prevents indefinite hangs when:
    - Ollama server is busy
    - Model needs to be reloaded (cold start)
    - Network issues occur
    
    Returns:
        TimeoutOllamaClient with timeout configured
    """
    return TimeoutOllamaClient(
        host=Const.OLLAMA_HOST,
        timeout=Const.LLM_TIMEOUT
    )