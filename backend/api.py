import os, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from utils.repoUtil import RepoUtil
from utils.dataPipeline import check_ollama_model_exists, get_all_ollama_models, DataPipeline, generate_db_name

from const.config import Config, APP_NAME, APP_VERSION
from const.const import Const


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for the FastAPI app"""
    # Startup
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    logger.info(f"Environment: {Config.ENVIRONMENT}")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {APP_NAME}")


# Create FastAPI app
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan,
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": APP_NAME,
        "version": APP_VERSION,
        "environment": Config.ENVIRONMENT
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": f"Welcome to {APP_NAME} API v{APP_VERSION}!"}


# Repo Tree Structure
# accept local path as query param
@app.get("/tree")
async def get_repo_tree(path: str = Query(None, description="Local path to generate repo tree structure")):
    """Get repository tree structure starting from the given local path"""
    import os

    if path is None:
        return {"error": "Path query parameter is required."}

    if not os.path.exists(path):
        return {"error": f"Path '{path}' does not exist."}

    repo_tree = RepoUtil.build_tree(path)
    return repo_tree


@app.get("/value_files")
async def get_valuable_files(path: str = Query(None, description="Local path to scan for valuable files")):
    """Get list of valuable files in the repository starting from the given local path"""

    if path is None:
        return {"error": "Path query parameter is required."}

    if not os.path.exists(path):
        return {"error": f"Path '{path}' does not exist."}

    valuable_files = RepoUtil.repo_filter(path)
    return {"root_path": path, "valuable_files": valuable_files}


@app.get("/file_content")
async def get_file_content(
    root: str = Query(None, description="Root path of the repository"),
    path: str = Query(None, description="File path relative to the root")
):
    """Get content of a specific file given its path relative to root"""

    if root is None or path is None:
        return {"error": "Both root and path query parameters are required."}

    if not os.path.exists(root):
        return {"error": f"Root path '{root}' does not exist."}

    full_path = os.path.join(root, path)
    if not os.path.exists(full_path):
        return {"error": f"File path '{full_path}' does not exist."}

    content = RepoUtil.file_content(root, path)
    if content is None:
        return {"error": f"Could not read content of file '{full_path}'."}

    return {"file_path": full_path, "content": content}

@app.get("/available_models")
async def list_available_models():
    """Get list of all available Ollama models"""
    models = get_all_ollama_models()
    embedding_model = Const.EMBEDDING_CONFIG['model_kwargs'].get('model', 'nomic-embed-text')
    generation_model = Const.GENERATION_MODEL
    
    return {
        "available_models": models,
        "current_embedding_model": embedding_model,
        "current_generation_model": generation_model,
        "embedding_model_available": check_ollama_model_exists(embedding_model),
        "generation_model_available": check_ollama_model_exists(generation_model)
    }

@app.post("/transform")
async def transform_documents(
    folder_path: str = Query(..., description="Path to folder containing documents to process"),
    extensions: str = Query(None, description="Comma-separated file extensions (e.g., '.py,.md')")
):
    """
    Transform documents from a folder: collect files, split text, generate embeddings, and save to LocalDB.
    
    Database name is automatically generated from the folder path for consistency.
    
    Args:
        folder_path: Path to folder containing documents
        extensions: Optional comma-separated file extensions to filter (default: all supported)
    
    Returns:
        Statistics about the transformation process including the generated database name
    """
    try:
        logger.info(f"Starting document transformation for folder: {folder_path}")
        
        # Validate folder exists
        if not os.path.exists(folder_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {folder_path}")
        
        if not os.path.isdir(folder_path):
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {folder_path}")
        
        # Generate database name from folder path
        db_name = generate_db_name(folder_path)
        
        # Validate folder exists
        if not os.path.exists(folder_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {folder_path}")
        
        if not os.path.isdir(folder_path):
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {folder_path}")
        
        # Parse extensions if provided
        allowed_extensions = None
        if extensions:
            allowed_extensions = [ext.strip() for ext in extensions.split(',')]
            logger.info(f"Filtering for extensions: {allowed_extensions}")
        
        # Step 1: Collect documents from folder using RepoUtil
        logger.info("Collecting documents from folder...")
        documents = RepoUtil.collect_documents(folder_path, allowed_extensions)
        
        if not documents:
            raise HTTPException(status_code=400, detail="No documents found in folder")
        
        # Step 2: Initialize pipeline and transform
        pipeline = DataPipeline()
        logger.info("Initialized DataPipeline")
        
        # Step 3: Create database directory
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        db_dir = os.path.join(data_dir, db_name)
        
        logger.info(f"Transforming documents (split + embed)...")
        db = pipeline.transform_and_save(documents, db_dir)
        logger.info("Transformation completed")
        
        # Step 4: Get statistics
        transformed_docs = db.get_transformed_data(key="split_and_embed")
        logger.info(f"Created {len(transformed_docs)} document chunks")
        
        # Calculate statistics
        stats = {
            "status": "success",
            "folder_path": folder_path,
            "database_name": db_name,
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
        
        logger.info(f"Transform completed: {stats['chunks_with_embeddings']}/{stats['transformed_chunk_count']} chunks with embeddings")
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during transformation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transformation failed: {str(e)}")