import os
from dotenv import load_dotenv
from adalflow.components.model_client.ollama_client import OllamaClient as _AdalOllamaClient
import ollama

# Load environment variables from .env file
load_dotenv()


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


class Config:
    """Application configuration from environment variables"""
    
    # ============================================================
    # Application Settings
    # ============================================================
    APP_NAME: str = "DiagWiki"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = os.environ.get("NODE_ENV", "development")
    PORT: int = int(os.environ.get("PORT", "8001"))
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    
    # ============================================================
    # LLM Configuration - IMPORTANT FOR RELIABILITY
    # ============================================================
    # Ollama host URL
    OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    
    # Timeout (seconds) for LLM API calls
    # This prevents indefinite hangs when Ollama is busy or reloading models
    LLM_TIMEOUT: float = float(os.environ.get("LLM_TIMEOUT", "120.0"))
    
    # Keep-alive duration for Ollama models (prevents frequent reloads)
    # Set to "10m" to keep model loaded for 10 minutes after last request
    OLLAMA_KEEP_ALIVE: str = os.environ.get("OLLAMA_KEEP_ALIVE", "10m")
    
    # Model names
    GENERATION_MODEL: str = os.environ.get("GENERATION_MODEL", "qwen3-coder:30b")
    EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
    
    # Embedding client timeout (embeddings are fast, shorter timeout)
    EMBEDDING_TIMEOUT: float = float(os.environ.get("EMBEDDING_TIMEOUT", "30.0"))
    
    # ============================================================
    # Text Splitting Configuration
    # ============================================================
    TEXT_SPLIT_BY: str = os.environ.get("TEXT_SPLIT_BY", "token")
    TEXT_CHUNK_SIZE: int = int(os.environ.get("TEXT_CHUNK_SIZE", "1000"))
    TEXT_CHUNK_OVERLAP: int = int(os.environ.get("TEXT_CHUNK_OVERLAP", "50"))
    
    # ============================================================
    # Localization
    # ============================================================
    DEFAULT_LANGUAGE: str = os.environ.get("DEFAULT_LANGUAGE", "en")
    
    # ============================================================
    # RAG Configuration
    # ============================================================
    # Maximum characters for RAG context to prevent LLM overflow
    MAX_RAG_CONTEXT_CHARS: int = int(os.environ.get("MAX_RAG_CONTEXT_CHARS", "100000"))
    
    # Maximum number of source files to include in RAG context
    MAX_SOURCES: int = int(os.environ.get("MAX_SOURCES", "40"))
    
    # Maximum characters per file when reading manual references
    MAX_FILE_CHARS: int = int(os.environ.get("MAX_FILE_CHARS", "50000"))
    
    # Default top_k for RAG queries
    RAG_TOP_K: int = int(os.environ.get("RAG_TOP_K", "40"))
    
    # Special top_k for section identification iterations
    RAG_SECTION_ITERATION_TOP_K: int = int(os.environ.get("RAG_SECTION_ITERATION_TOP_K", "80"))
    
    # Maximum tokens for document chunking
    MAX_TOKEN_LIMIT: int = int(os.environ.get("MAX_TOKEN_LIMIT", "8192"))
    
    # Maximum tokens for embedding (to prevent overflow)
    MAX_EMBEDDING_TOKENS: int = int(os.environ.get("MAX_EMBEDDING_TOKENS", "6000"))
    
    # Preview length for file sources
    SOURCE_PREVIEW_LENGTH: int = int(os.environ.get("SOURCE_PREVIEW_LENGTH", "600"))
    
    # ============================================================
    # LLM Generation Parameters
    # ============================================================
    # Default temperature for creative generation (diagrams, wiki)
    DEFAULT_TEMPERATURE: float = float(os.environ.get("DEFAULT_TEMPERATURE", "0.7"))
    
    # Lower temperature for focused tasks (title generation)
    FOCUSED_TEMPERATURE: float = float(os.environ.get("FOCUSED_TEMPERATURE", "0.3"))
    
    # Context window size - use large window for all operations
    LARGE_CONTEXT_WINDOW: int = int(os.environ.get("LARGE_CONTEXT_WINDOW", "16384"))
    
    # ============================================================
    # API Configuration
    # ============================================================
    # Thread pool size for async operations
    MAX_WORKERS: int = int(os.environ.get("MAX_WORKERS", "4"))
    
    # ============================================================
    # Computed Configuration (Generated from above values)
    # ============================================================
    @classmethod
    def get_embedding_config(cls):
        """Get embedding configuration dict"""
        return {
            "client": TimeoutOllamaClient(host=cls.OLLAMA_HOST, timeout=cls.EMBEDDING_TIMEOUT),
            "model_kwargs": {
                "model": cls.EMBEDDING_MODEL,
                "keep_alive": cls.OLLAMA_KEEP_ALIVE
            }
        }
    
    @classmethod
    def get_text_split_config(cls):
        """Get text splitting configuration dict"""
        return {
            "split_by": cls.TEXT_SPLIT_BY,
            "chunk_size": cls.TEXT_CHUNK_SIZE,
            "chunk_overlap": cls.TEXT_CHUNK_OVERLAP,
        }
    
    @classmethod
    def get_llm_client(cls):
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
            host=cls.OLLAMA_HOST,
            timeout=cls.LLM_TIMEOUT
        )
    
    @classmethod
    def is_development(cls) -> bool:
        return cls.ENVIRONMENT != "production"


# Export commonly used values for backward compatibility
APP_NAME = Config.APP_NAME
APP_VERSION = Config.APP_VERSION
OLLAMA_HOST = Config.OLLAMA_HOST
GENERATION_MODEL = Config.GENERATION_MODEL
EMBEDDING_MODEL = Config.EMBEDDING_MODEL
