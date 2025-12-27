import os, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Optional, List
from utils.repoUtil import RepoUtil
from utils.dataPipeline import check_ollama_model_exists, get_all_ollama_models, DataPipeline, generate_db_name
from utils.wiki_generator import WikiGenerator

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


# Pydantic models for wiki generation
class WikiStructureRequest(BaseModel):
    root_path: str = Field(..., description="Root path to the folder")
    comprehensive: bool = Field(False, description="Whether to create comprehensive wiki (8-12 pages) or concise (4-6 pages)")
    language: str = Field("en", description="Language code (en, ja, zh, es, kr, vi, etc.)")


class WikiPageRequest(BaseModel):
    root_path: str = Field(..., description="Root path to the folder")
    page_title: str = Field(..., description="Title of the page to generate")
    page_description: str = Field(..., description="Description of what the page should cover")
    relevant_files: List[str] = Field(..., description="List of relevant file paths for this page")
    language: str = Field("en", description="Language code")
    page_id: Optional[str] = Field(None, description="Optional page ID for caching (defaults to sanitized page_title)")


@app.post("/generateWikiStructure")
async def generate_wiki_structure(request: WikiStructureRequest = Body(...)):
    """
    Generate wiki structure by analyzing the codebase using RAG.
    
    This endpoint:
    1. Initializes RAG for the codebase
    2. Generates file tree structure
    3. Reads README if exists
    4. Uses RAG queries to understand codebase components
    5. Uses LLM to analyze and create wiki structure
    6. Returns structured pages and sections in XML format
    
    Args:
        request: WikiStructureRequest with root_path, comprehensive flag, and language
        
    Returns:
        XML structure defining wiki pages and sections with cache information
    """
    try:
        logger.info(f"Generating wiki structure for: {request.root_path}")
        
        # Validate folder
        if not os.path.exists(request.root_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {request.root_path}")
        
        # Use WikiGenerator for all wiki generation logic
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        wiki_gen = WikiGenerator(root_path=request.root_path, data_dir=data_dir)
        
        result = wiki_gen.generate_structure(
            language=request.language,
            comprehensive=request.comprehensive,
            use_cache=True
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating wiki structure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate wiki structure: {str(e)}")


@app.post("/generateWikiPage")
async def generate_wiki_page(request: WikiPageRequest = Body(...)):
    """
    Generate detailed wiki page content using RAG-based retrieval.
    
    This endpoint:
    1. Initializes RAG for the codebase
    2. Generates targeted queries from page topic
    3. Uses RAG with hybrid retrieval to get relevant context
    4. Generates comprehensive markdown with diagrams
    5. Returns formatted wiki page content
    
    Args:
        request: WikiPageRequest with page details and relevant files
        
    Returns:
        Markdown content for the wiki page with cache information
    """
    try:
        logger.info(f"Generating wiki page: {request.page_title}")
        
        # Validate folder
        if not os.path.exists(request.root_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {request.root_path}")
        
        # Use WikiGenerator for all wiki page generation logic
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        wiki_gen = WikiGenerator(root_path=request.root_path, data_dir=data_dir)
        
        # Generate page_id from request if available (for better caching)
        page_id = getattr(request, 'page_id', None)
        
        result = wiki_gen.generate_page(
            page_title=request.page_title,
            page_description=request.page_description,
            relevant_files=request.relevant_files,
            language=request.language,
            page_id=page_id,
            use_cache=True
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating wiki page: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate wiki page: {str(e)}")


# Pydantic models for two-step diagram API
class DiagramSectionsRequest(BaseModel):
    root_path: str = Field(..., description="Root path to the folder")
    language: str = Field("en", description="Language code")


class SectionDiagramRequest(BaseModel):
    root_path: str = Field(..., description="Root path to the folder")
    section_id: str = Field(..., description="Section ID (from step 1)")
    section_title: str = Field(..., description="Title of this section")
    section_description: str = Field(..., description="Description of what this section covers")
    diagram_type: str = Field(..., description="Type of Mermaid diagram (flowchart, sequence, class, etc.)")
    key_concepts: List[str] = Field(..., description="List of key concepts to include in the diagram")
    language: str = Field("en", description="Language code")


@app.post("/identifyDiagramSections")
async def identify_diagram_sections(request: DiagramSectionsRequest = Body(...)):
    """
    Step 1 of Diagram-First Wiki API: Identify diagram sections for the codebase.
    
    This is for a DIAGRAM-FIRST WIKI where the wiki IS MADE OF DIAGRAMS.
    Diagrams are NOT supplements to text - they ARE the primary content.
    
    The system automatically analyzes the codebase and identifies 2-5 key aspects
    that should be visualized as interactive diagrams.
    
    The endpoint:
    1. Analyzes the codebase structure using RAG
    2. Identifies 2-5 distinct aspects that should each be a diagram
    3. Returns section metadata (id, title, description, diagram_type, key_concepts)
    
    Each section becomes an interactive diagram that explains one focused aspect.
    Together, these diagrams form a complete visual overview of the codebase.
    
    Frontend workflow:
    1. Call this endpoint → get back 2-5 diagram sections
    2. Call /generateSectionDiagram for each section → get interactive diagrams
    3. Display all diagrams as a "diagram page" - that's the wiki!
    
    Args:
        request: DiagramSectionsRequest with root_path and language
        
    Returns:
        JSON with status and list of 2-5 diagram sections to generate
    """
    try:
        logger.info(f"Identifying diagram sections for codebase: {request.root_path}")
        
        # Validate folder
        if not os.path.exists(request.root_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {request.root_path}")
        
        # Use WikiGenerator for diagram section identification
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        wiki_gen = WikiGenerator(root_path=request.root_path, data_dir=data_dir)
        
        result = wiki_gen.identify_diagram_sections(
            language=request.language,
            use_cache=True
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error identifying diagram sections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to identify diagram sections: {str(e)}")


@app.post("/generateSectionDiagram")
async def generate_section_diagram(request: SectionDiagramRequest = Body(...)):
    """
    Step 2 of Two-Step Diagram API: Generate diagram for a single section.
    
    This endpoint generates a comprehensive Mermaid diagram with node/edge explanations
    for one specific section. This is for a DIAGRAM-FIRST wiki where the diagram + explanations
    should fully explain the section without additional text.
    
    The endpoint:
    1. Performs focused RAG queries for this section
    2. Uses LLM to generate Mermaid diagram + node/edge explanations
    3. Algorithmically parses the Mermaid code to extract structure
    4. Combines LLM explanations with parsed nodes/edges
    5. Returns interactive diagram data
    
    Frontend should:
    1. Render the Mermaid diagram
    2. Make nodes/edges clickable
    3. Display explanations in tooltips/modals when clicked
    
    Args:
        request: SectionDiagramRequest with section details from step 1
        
    Returns:
        JSON with diagram (mermaid_code, description), nodes (with explanations), edges (with explanations)
    """
    try:
        logger.info(f"Generating diagram for section: {request.section_title}")
        
        # Validate folder
        if not os.path.exists(request.root_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {request.root_path}")
        
        # Use WikiGenerator for diagram generation
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        wiki_gen = WikiGenerator(root_path=request.root_path, data_dir=data_dir)
        
        result = wiki_gen.generate_section_diagram(
            section_id=request.section_id,
            section_title=request.section_title,
            section_description=request.section_description,
            diagram_type=request.diagram_type,
            key_concepts=request.key_concepts,
            language=request.language,
            use_cache=True
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating section diagram: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate section diagram: {str(e)}")


@app.get("/askWiki")
async def ask_wiki(
    root_path: str = Query(..., description="Root path to the folder"),
    question: str = Query(..., description="Question to ask about the generated wiki"),
    top_k: int = Query(5, description="Number of wiki documents to retrieve")
):
    """
    Ask questions about the generated wiki content.
    
    This endpoint queries a separate RAG database that contains ONLY the generated wiki content
    (diagram explanations, section descriptions, node/edge explanations, etc.).
    
    Use this endpoint to:
    - Ask follow-up questions about diagrams
    - Clarify relationships shown in diagrams
    - Get explanations of specific components
    - Understand the connections between different sections
    
    This is separate from /query which searches the original codebase.
    
    Prerequisites:
    - Must have generated some diagrams first using /generateSectionDiagram
    - Each generated diagram is automatically added to the wiki RAG database
    
    Args:
        root_path: Absolute path to the folder
        question: User's question about the wiki
        top_k: Number of wiki documents to retrieve (default: 5)
        
    Returns:
        Answer based on generated wiki content with source documents
    """
    try:
        logger.info(f"Processing wiki question for folder: {root_path}")
        logger.info(f"Question: {question}")
        
        # Validate folder
        if not os.path.exists(root_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {root_path}")
        
        # Use WikiGenerator to query wiki RAG
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        wiki_gen = WikiGenerator(root_path=root_path, data_dir=data_dir)
        
        result = wiki_gen.query_wiki_rag(query=question, top_k=top_k)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying wiki: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to query wiki: {str(e)}")