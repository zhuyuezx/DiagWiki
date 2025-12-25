import os, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from utils.repoUtil import RepoUtil
from utils.dataPipeline import check_ollama_model_exists, get_all_ollama_models
import requests

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