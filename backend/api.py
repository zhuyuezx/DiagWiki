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


@app.post("/initWiki")
async def init_wiki(
    root_path: str = Query(..., description="Root path to the folder for wiki initialization")
):
    """
    Initialize wiki from a local folder.
    
    This endpoint:
    1. Validates the folder exists
    2. Processes documents (transform) if not already done
    3. Initializes RAG system with the database
    4. Returns initialization status
    
    Args:
        root_path: Absolute path to the folder containing documents
        
    Returns:
        Initialization status including RAG readiness and database info
    """
    try:
        logger.info(f"Initializing wiki for folder: {root_path}")
        
        # Validate folder exists
        if not os.path.exists(root_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {root_path}")
        
        if not os.path.isdir(root_path):
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {root_path}")
        
        # Generate database name
        db_name = generate_db_name(root_path)
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        db_dir = os.path.join(data_dir, db_name)
        db_path = os.path.join(db_dir, "db.pkl")
        
        # Check if database already exists
        db_exists = os.path.exists(db_path)
        
        if not db_exists:
            logger.info("Database not found, processing documents...")
            
            # Collect and process documents
            documents = RepoUtil.collect_documents(root_path, None)
            
            if not documents:
                raise HTTPException(status_code=400, detail="No documents found in folder")
            
            logger.info(f"Collected {len(documents)} documents")
            
            # Transform and save
            pipeline = DataPipeline()
            db = pipeline.transform_and_save(documents, db_dir)
            
            transformed_docs = db.get_transformed_data(key="split_and_embed")
            logger.info(f"Processed {len(transformed_docs)} chunks with embeddings")
        else:
            logger.info(f"Database already exists at: {db_path}")
            # Load existing database to get stats
            from adalflow.core.db import LocalDB
            db = LocalDB.load_state(filepath=db_path)
            transformed_docs = db.get_transformed_data(key="split_and_embed")
        
        # Initialize RAG system
        from utils.rag import RAG
        rag = RAG()
        rag.load_database(db_path)
        
        logger.info(f"RAG system initialized with {len(rag.transformed_docs)} documents")
        
        # Gather statistics
        file_types = {}
        for doc in rag.transformed_docs:
            if hasattr(doc, 'meta_data'):
                ext = doc.meta_data.get('extension', 'unknown')
                file_types[ext] = file_types.get(ext, 0) + 1
        
        return {
            "status": "success",
            "message": "Wiki initialized successfully" if not db_exists else "Wiki loaded from existing database",
            "root_path": root_path,
            "database_name": db_name,
            "database_path": db_path,
            "database_existed": db_exists,
            "rag_ready": True,
            "document_count": len(rag.transformed_docs),
            "embedding_model": Const.EMBEDDING_CONFIG['model_kwargs']['model'],
            "generation_model": Const.GENERATION_MODEL,
            "file_types": file_types
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing wiki: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initialize wiki: {str(e)}")


@app.post("/query")
async def query_wiki(
    root_path: str = Query(..., description="Root path to the wiki folder"),
    query: str = Query(..., description="Question to ask about the codebase"),
    top_k: int = Query(5, description="Number of documents to retrieve"),
    use_reranking: bool = Query(True, description="Whether to use hybrid retrieval (semantic + BM25)")
):
    """
    Query the wiki using RAG.
    
    This endpoint:
    1. Loads the RAG system for the specified folder
    2. Retrieves relevant document chunks
    3. Generates an answer using the LLM
    4. Returns the answer with source documents
    
    Args:
        root_path: Absolute path to the wiki folder
        query: User's question
        top_k: Number of documents to retrieve (default: 5)
        use_reranking: Enable hybrid retrieval for better results (default: True)
        
    Returns:
        Generated answer with rationale and source documents
    """
    try:
        logger.info(f"Processing query for folder: {root_path}")
        logger.info(f"Query: {query}")
        
        # Validate folder exists
        if not os.path.exists(root_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {root_path}")
        
        # Generate database name and check if it exists
        db_name = generate_db_name(root_path)
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        db_path = os.path.join(data_dir, db_name, "db.pkl")
        
        if not os.path.exists(db_path):
            raise HTTPException(
                status_code=400, 
                detail=f"Wiki not initialized for this folder. Please call /initWiki first."
            )
        
        # Initialize RAG
        from utils.rag import RAG
        rag = RAG()
        rag.load_database(db_path)
        
        logger.info(f"RAG loaded with {len(rag.transformed_docs)} documents")
        
        # Perform RAG query
        answer, retrieved_docs = rag(query, top_k=top_k, use_reranking=use_reranking)
        
        # Format retrieved documents info
        sources = []
        for i, doc in enumerate(retrieved_docs, 1):
            file_path = doc.meta_data.get('file_path', 'unknown') if hasattr(doc, 'meta_data') else 'unknown'
            sources.append({
                "rank": i,
                "file_path": file_path,
                "text_preview": doc.text[:200] + "..." if len(doc.text) > 200 else doc.text,
                "text_length": len(doc.text)
            })
        
        logger.info(f"Query answered successfully, retrieved {len(sources)} sources")
        
        return {
            "status": "success",
            "query": query,
            "answer": {
                "rationale": answer.rationale,
                "content": answer.answer
            },
            "sources": sources,
            "retrieval_method": "hybrid (semantic + BM25)" if use_reranking else "semantic only",
            "model": {
                "embedding": Const.EMBEDDING_CONFIG['model_kwargs']['model'],
                "generation": Const.GENERATION_MODEL
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")