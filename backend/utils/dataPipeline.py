import os
import hashlib, re
import requests
import logging
from const.const import Const
import adalflow as adal
from adalflow.core.component import DataComponent
from adalflow.core.types import Document
from copy import deepcopy
from tqdm import tqdm
from typing import Sequence
from adalflow.components.data_process import TextSplitter
from adalflow.core.db import LocalDB

logger = logging.getLogger(__name__)

def get_all_ollama_models(ollama_host: str = None) -> list:
    """
    Get list of all available Ollama models.
    
    Args:
        ollama_host: Ollama host URL, defaults to localhost:11434
        
    Returns:
        list: List of available model names (full names with tags)
    """
    if ollama_host is None:
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    
    try:
        # Remove /api prefix if present and add it back
        if ollama_host.endswith('/api'):
            ollama_host = ollama_host[:-4]
        
        response = requests.get(f"{ollama_host}/api/tags", timeout=5)
        if response.status_code == 200:
            models_data = response.json()
            available_models = [model.get('name', '') for model in models_data.get('models', [])]
            logger.info(f"Found {len(available_models)} Ollama models")
            return available_models
        else:
            logger.warning(f"Could not check Ollama models, status code: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not connect to Ollama to check models: {e}")
        return []

def check_ollama_model_exists(model_name: str, ollama_host: str = None) -> bool:
    """
    Check if an Ollama model exists before attempting to use it.
    Supports both rough matching (base name) and exact matching (with tag).
    
    Examples:
        - "qwen3-coder" matches "qwen3-coder:30b" (rough match)
        - "qwen3-coder:30b" only matches "qwen3-coder:30b" (exact match)
    
    Args:
        model_name: Name of the model to check (with or without tag)
        ollama_host: Ollama host URL, defaults to localhost:11434
        
    Returns:
        bool: True if model exists, False otherwise
    """
    available_models = get_all_ollama_models(ollama_host)
    
    if not available_models:
        return False
    
    # Check if model_name includes a tag (has ':')
    if ':' in model_name:
        # Exact match - model_name includes tag
        is_available = model_name in available_models
        if is_available:
            logger.info(f"Ollama model '{model_name}' is available (exact match)")
        else:
            logger.warning(f"Ollama model '{model_name}' is not available (exact match). Available models: {available_models}")
    else:
        # Rough match - check if any model starts with the base name
        model_base_name = model_name
        matching_models = [m for m in available_models if m.split(':')[0] == model_base_name]
        is_available = len(matching_models) > 0
        
        if is_available:
            logger.info(f"Ollama model '{model_name}' is available (rough match): {matching_models}")
        else:
            logger.warning(f"Ollama model '{model_name}' is not available. Available models: {available_models}")
    
    return is_available

def generate_db_name(folder_path: str) -> str:
    """Generate a deterministic database name from folder path.
    
    Creates a name combining:
    - Sanitized folder name (human-readable)
    - Short hash of full path (ensures uniqueness)
    
    Args:
        folder_path: Absolute path to the folder
    
    Returns:
        Database name like 'DiagWiki_a1b2c3d4'
    """
    # Normalize path (resolve symlinks, remove trailing slashes)
    normalized_path = os.path.normpath(os.path.abspath(folder_path))
    
    # Get folder name
    folder_name = os.path.basename(normalized_path)
    
    # Sanitize folder name: keep only alphanumeric, hyphens, underscores
    sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', folder_name)
    sanitized_name = re.sub(r'_+', '_', sanitized_name)  # Collapse multiple underscores
    sanitized_name = sanitized_name.strip('_')  # Remove leading/trailing underscores
    
    # Generate short hash of full path for uniqueness (first 8 chars)
    path_hash = hashlib.sha256(normalized_path.encode('utf-8')).hexdigest()[:8]
    
    # Combine: foldername_hash
    db_name = f"{sanitized_name}_{path_hash}"
    
    logger.info(f"Generated db_name '{db_name}' for folder '{normalized_path}'")
    return db_name

class OllamaDocumentProcessor(DataComponent):
    """
    Process documents for Ollama embeddings by processing one document at a time.
    Adalflow Ollama Client does not support batch embedding, so we need to process each document individually.
    """
    
    def __init__(self, embedder: adal.Embedder) -> None:
        super().__init__()
        self.embedder = embedder

    def __call__(self, documents: Sequence[Document]) -> Sequence[Document]:
        from utils.repoUtil import RepoUtil
        output = deepcopy(documents)
        logger.info(f"Processing {len(output)} documents individually for Ollama embeddings")

        successful_docs = []
        expected_embedding_size = None
        skipped_large_docs = 0

        for i, doc in enumerate(tqdm(output, desc="Processing documents for Ollama embeddings")):
            try:
                # Check token count before attempting to embed
                token_count = RepoUtil.token_count(doc.text)
                file_path = getattr(doc, 'meta_data', {}).get('file_path', f'document_{i}')
                
                logger.debug(f"Processing '{file_path}': {token_count} tokens, {len(doc.text)} chars")
                
                if token_count > Const.MAX_EMBEDDING_TOKENS:
                    logger.warning(f"Document '{file_path}' has {token_count} tokens which exceeds embedding model context limit ({Const.MAX_EMBEDDING_TOKENS}), skipping")
                    skipped_large_docs += 1
                    continue
                
                # Get embedding for a single document
                result = self.embedder(input=doc.text)
                if result.data and len(result.data) > 0:
                    embedding = result.data[0].embedding

                    # Validate embedding size consistency
                    if expected_embedding_size is None:
                        expected_embedding_size = len(embedding)
                        logger.info(f"Expected embedding size set to: {expected_embedding_size}")
                    elif len(embedding) != expected_embedding_size:
                        file_path = getattr(doc, 'meta_data', {}).get('file_path', f'document_{i}')
                        logger.warning(f"Document '{file_path}' has inconsistent embedding size {len(embedding)} != {expected_embedding_size}, skipping")
                        continue

                    # Assign the embedding to the document
                    output[i].vector = embedding
                    successful_docs.append(output[i])
                else:
                    file_path = getattr(doc, 'meta_data', {}).get('file_path', f'document_{i}')
                    logger.warning(f"Failed to get embedding for document '{file_path}', skipping")
            except Exception as e:
                file_path = getattr(doc, 'meta_data', {}).get('file_path', f'document_{i}')
                error_msg = str(e)
                
                # Check if it's a context length error
                if "context length" in error_msg.lower() or "input length" in error_msg.lower():
                    actual_token_count = RepoUtil.token_count(doc.text)
                    logger.error(f"Context length error for '{file_path}': {error_msg}")
                    logger.error(f"  - Actual token count: {actual_token_count}")
                    logger.error(f"  - Text length: {len(doc.text)} chars")
                    logger.error(f"  - First 200 chars: {doc.text[:200]}...")
                    skipped_large_docs += 1
                else:
                    logger.error(f"Error processing document '{file_path}': {e}, skipping")

        if skipped_large_docs > 0:
            logger.info(f"Skipped {skipped_large_docs} documents that exceeded token limit ({Const.MAX_EMBEDDING_TOKENS} tokens)")
        logger.info(f"Successfully processed {len(successful_docs)}/{len(output)} documents with consistent embeddings")
        return successful_docs

class DataPipeline:
    
    def __init__(self, db_name: str = None, embedder_model: str = None, text_splitter_config: dict = None):
        """Initialize DataPipeline with optional custom configuration.
        
        Args:
            db_name: Optional database name (for process_folder)
            embedder_model: Optional embedder model override
            text_splitter_config: Optional text splitter config override
        """
        self.db_name = db_name
        
        # Use provided config or fall back to defaults
        if embedder_model:
            embedder_kwargs = {
                "model_client": adal.OllamaClient(),
                "model_kwargs": {"model": embedder_model}
            }
        else:
            embedder_kwargs = {
                "model_client": Const.EMBEDDING_CONFIG.get("client", adal.OllamaClient()),
                "model_kwargs": Const.EMBEDDING_CONFIG['model_kwargs']
            }
        
        self.embedder = adal.Embedder(**embedder_kwargs)
        
        split_config = text_splitter_config if text_splitter_config else Const.TEXT_SPLIT_CONFIG
        self.splitter = TextSplitter(**split_config)
        
        self.embedder_transformer = OllamaDocumentProcessor(embedder=self.embedder)
        
        self.data_transformer = adal.Sequential(
            self.splitter,
            self.embedder_transformer
        )
    
    def process_folder(self, folder_path: str, allowed_extensions: list = None, data_dir: str = None):
        """Process all documents in a folder: collect, transform, and save to database.
        
        This is the main entry point that combines:
        1. Document collection from folder
        2. Text splitting and embedding
        3. Saving to LocalDB
        
        Args:
            folder_path: Path to folder containing documents
            allowed_extensions: Optional list of file extensions to filter (e.g., ['.py', '.md'])
            data_dir: Optional base directory for databases (defaults to ./data)
        
        Returns:
            dict: Statistics about the transformation process
        """
        from utils.repoUtil import RepoUtil
        
        logger.info(f"Processing folder: {folder_path}")
        
        # Validate folder
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        if not os.path.isdir(folder_path):
            raise ValueError(f"Path is not a directory: {folder_path}")
        
        # Collect documents
        logger.info("Collecting documents from folder...")
        documents = RepoUtil.collect_documents(folder_path, allowed_extensions)
        
        if not documents:
            raise ValueError("No documents found in folder")
        
        logger.info(f"Collected {len(documents)} documents")
        
        # Determine database directory
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        
        db_dir = os.path.join(data_dir, self.db_name)
        
        # Transform and save
        logger.info(f"Transforming documents (split + embed)...")
        db = self.transform_and_save(documents, db_dir)
        logger.info("Transformation completed")
        
        # Get statistics
        transformed_docs = db.get_transformed_data(key="split_and_embed")
        logger.info(f"Created {len(transformed_docs)} document chunks")
        
        # Calculate statistics
        stats = {
            "status": "success",
            "folder_path": folder_path,
            "database_name": self.db_name,
            "database_path": os.path.join(db_dir, "db.pkl"),
            "original_document_count": len(documents),
            "transformed_chunk_count": len(transformed_docs),
            "chunks_with_embeddings": 0,
            "embedding_sizes": {},
            "file_types": {}
        }
        
        # Analyze chunks
        for doc in transformed_docs:
            if hasattr(doc, 'vector') and doc.vector is not None:
                stats["chunks_with_embeddings"] += 1
                embedding_size = len(doc.vector)
                stats["embedding_sizes"][embedding_size] = \
                    stats["embedding_sizes"].get(embedding_size, 0) + 1
            
            # Count file types
            if hasattr(doc, 'meta_data') and 'extension' in doc.meta_data:
                ext = doc.meta_data['extension']
                stats["file_types"][ext] = stats["file_types"].get(ext, 0) + 1
        
        logger.info(f"Process completed: {stats['chunks_with_embeddings']}/{stats['transformed_chunk_count']} chunks with embeddings")
        return stats
    
    def transform_and_save(self, documents: Sequence[Document], persist_dir: str) -> LocalDB:
        """Transform documents and save to the specified directory"""
        db = LocalDB()
        db.register_transformer(transformer=self.data_transformer, key="split_and_embed")
        db.load(documents)
        db.transform(key="split_and_embed")
        
        # Create directory and save to db.pkl file
        os.makedirs(persist_dir, exist_ok=True)
        db_file = os.path.join(persist_dir, "db.pkl")
        db.save_state(filepath=db_file)
        logger.info(f"Saved database to {db_file}")
        return db