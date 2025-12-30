import os, logging, json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from utils.repoUtil import RepoUtil
from utils.dataPipeline import check_ollama_model_exists, get_all_ollama_models, DataPipeline, generate_db_name
from utils.wiki_generator import WikiGenerator

from const.config import Config, APP_NAME, APP_VERSION
from const.const import Const


logger = logging.getLogger(__name__)

# Create a thread pool executor for blocking operations
executor = ThreadPoolExecutor(max_workers=4)


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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:4173"],  # Vite/SvelteKit dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    root_path: str = Body(..., embed=True, description="Root path to the folder for wiki initialization")
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
    use_reranking: bool = Query(True, description="Whether to use hybrid retrieval (semantic + BM25)"),
    include_wiki: bool = Query(False, description="Whether to include generated wiki content in the search")
):
    """
    Query the codebase using RAG, optionally including generated wiki content.
    
    This endpoint:
    1. Loads the RAG system for the specified folder
    2. Retrieves relevant document chunks from codebase
    3. Optionally retrieves from generated wiki database (if include_wiki=True)
    4. Generates an answer using the LLM with combined context
    5. Returns the answer with source documents from both sources
    
    Args:
        root_path: Absolute path to the wiki folder
        query: User's question
        top_k: Number of documents to retrieve from each source (default: 5)
        use_reranking: Enable hybrid retrieval for better results (default: True)
        include_wiki: Include generated wiki content in search (default: False)
        
    Returns:
        Generated answer with rationale and source documents
    """
    try:
        logger.info(f"Processing query for folder: {root_path}")
        logger.info(f"Query: {query}, include_wiki: {include_wiki}")
        
        # Validate folder exists
        if not os.path.exists(root_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {root_path}")
        
        # If include_wiki is requested, use WikiGenerator's dual-RAG query
        if include_wiki:
            data_dir = os.path.join(os.path.dirname(__file__), "data")
            wiki_gen = WikiGenerator(root_path=root_path, data_dir=data_dir)
            
            result = wiki_gen.query_wiki_rag(query=query, top_k=top_k)
            
            if result.get("status") == "error":
                raise HTTPException(status_code=400, detail=result.get("error"))
            
            return result
        
        # Otherwise, use standard codebase-only RAG
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
        
        # Run blocking operation in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            _identify_sections_sync,
            request.root_path,
            request.language
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error identifying diagram sections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to identify diagram sections: {str(e)}")


def _identify_sections_sync(root_path: str, language: str):
    """Synchronous function to run in thread pool."""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    wiki_gen = WikiGenerator(root_path=root_path, data_dir=data_dir)
    return wiki_gen.identify_diagram_sections(
        language=language,
        use_cache=True
    )


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
        
        # Run blocking operation in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            _generate_diagram_sync,
            request.root_path,
            request.section_id,
            request.section_title,
            request.section_description,
            request.diagram_type,
            request.key_concepts,
            request.language
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating section diagram: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate section diagram: {str(e)}")


def _generate_diagram_sync(
    root_path: str,
    section_id: str,
    section_title: str,
    section_description: str,
    diagram_type: str,
    key_concepts: list,
    language: str
):
    """Synchronous function to run in thread pool."""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    wiki_gen = WikiGenerator(root_path=root_path, data_dir=data_dir)
    return wiki_gen.generate_section_diagram(
        section_id=section_id,
        section_title=section_title,
        section_description=section_description,
        diagram_type=diagram_type,
        key_concepts=key_concepts,
        language=language,
        use_cache=True
    )


# Pydantic models for wiki problem analysis and modification
class WikiItem(BaseModel):
    wiki_name: str = Field(..., description="Name/ID of the wiki section")
    question: Optional[str] = Field(None, description="Optional question about this wiki section")


class WikiProblemRequest(BaseModel):
    root_path: str = Field(..., description="Root path to the folder")
    prompt: str = Field(..., description="User's request describing the problem or modification needed")
    wiki_items: Optional[List[WikiItem]] = Field(None, description="Optional list of wiki sections with questions")


class ModifyOrCreateWikiRequest(BaseModel):
    root_path: str = Field(..., description="Root path to the folder")
    next_step_prompt: str = Field(..., description="Detailed prompt for wiki generation/modification")
    wiki_name: str = Field(..., description="Name/ID of the wiki section to create or modify")
    is_new: bool = Field(..., description="Whether this is a new wiki section or modification of existing")


@app.post("/wikiProblem")
async def wiki_problem(request: WikiProblemRequest = Body(...)):
    """
    Analyze a user's wiki-related request and determine if modifications are needed.
    
    This endpoint:
    1. Retrieves relevant wiki content using RAG
    2. Analyzes the user's prompt to determine intent
    3. Decides if this is a question (answer directly) or modification request
    4. If modification needed, returns structured plan with next-step prompts
    
    Args:
        request: WikiProblemRequest with root_path, prompt, and optional wiki_items
        
    Returns:
        JSON with either:
        - answer: Direct answer to the question
        - plan: Structured modification plan with modify/create actions
    """
    try:
        logger.info(f"Analyzing wiki problem for: {request.root_path}")
        logger.info(f"User prompt: {request.prompt[:100]}...")
        
        # Validate folder
        if not os.path.exists(request.root_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {request.root_path}")
        
        # Use WikiGenerator to analyze the problem
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        wiki_gen = WikiGenerator(root_path=request.root_path, data_dir=data_dir)
        
        # Convert wiki_items to dict format
        wiki_items_dict = None
        if request.wiki_items:
            wiki_items_dict = {
                item.wiki_name: item.question 
                for item in request.wiki_items
            }
        
        result = wiki_gen.analyze_wiki_problem(
            user_prompt=request.prompt,
            wiki_items=wiki_items_dict
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing wiki problem: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze wiki problem: {str(e)}")


@app.post("/modifyOrCreateWiki")
async def modify_or_create_wiki(request: ModifyOrCreateWikiRequest = Body(...)):
    """
    Create a new wiki section or modify an existing one.
    
    This endpoint:
    1. If is_new=True: Generates a new diagram section
    2. If is_new=False: Modifies existing wiki content based on prompt
    
    Args:
        request: ModifyOrCreateWikiRequest with root_path, next_step_prompt, wiki_name, is_new
        
    Returns:
        JSON with the created/modified wiki section
    """
    try:
        logger.info(f"{'Creating new' if request.is_new else 'Modifying'} wiki section: {request.wiki_name}")
        
        # Validate folder
        if not os.path.exists(request.root_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {request.root_path}")
        
        # Use WikiGenerator to create or modify wiki
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        wiki_gen = WikiGenerator(root_path=request.root_path, data_dir=data_dir)
        
        if request.is_new:
            # Create new wiki section
            result = wiki_gen.create_wiki_section(
                wiki_name=request.wiki_name,
                prompt=request.next_step_prompt
            )
        else:
            # Modify existing wiki section
            result = wiki_gen.modify_wiki_section(
                wiki_name=request.wiki_name,
                modification_prompt=request.next_step_prompt
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating/modifying wiki: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create/modify wiki: {str(e)}")


# Pydantic models for new endpoints
class DiagramReferencesRequest(BaseModel):
    root_path: str = Field(..., description="Root path to the project")
    section_id: str = Field(..., description="Section ID to get references for")


class FolderTreeRequest(BaseModel):
    root_path: str = Field(..., description="Root path to the project folder")


@app.post("/getDiagramReferences")
async def get_diagram_references(request: DiagramReferencesRequest = Body(...)):
    """
    Get the source files (RAG references) used to generate a specific diagram.
    
    This endpoint retrieves the list of source files that were analyzed
    via RAG to generate the specified diagram section.
    
    Args:
        request: DiagramReferencesRequest with root_path and section_id
        
    Returns:
        JSON with rag_sources array containing file paths and relevance
    """
    try:
        # Validate folder
        if not os.path.exists(request.root_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {request.root_path}")
        
        # Load diagram data from cache
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        from utils.dataPipeline import generate_db_name
        db_name = generate_db_name(request.root_path)
        db_path = os.path.join(data_dir, db_name)
        diagrams_dir = os.path.join(db_path, "wiki", "diagrams")
        
        cache_file = os.path.join(diagrams_dir, f"diag_{request.section_id}.json")
        
        if not os.path.exists(cache_file):
            raise HTTPException(status_code=404, detail=f"Diagram section not found: {request.section_id}")
        
        with open(cache_file, 'r', encoding='utf-8') as f:
            diagram_data = json.load(f)
        
        # Extract rag_sources
        rag_sources = diagram_data.get('rag_sources', [])
        
        logger.info(f"Diagram {request.section_id} has {len(rag_sources)} RAG sources")
        
        return {
            "status": "success",
            "section_id": request.section_id,
            "rag_sources": rag_sources,
            "has_sources": len(rag_sources) > 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting diagram references: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get diagram references: {str(e)}")


@app.post("/getFolderTree")
async def get_folder_tree(request: FolderTreeRequest = Body(...)):
    """
    Get the folder structure for a project.
    
    This endpoint returns a hierarchical tree structure of the project's
    folders and files.
    
    Args:
        request: FolderTreeRequest with root_path
        
    Returns:
        JSON with folder tree structure
    """
    try:
        # Validate folder
        if not os.path.exists(request.root_path):
            raise HTTPException(status_code=404, detail=f"Folder not found: {request.root_path}")
        
        def build_tree(path: str, max_depth: int = 5, current_depth: int = 0) -> Dict:
            """Recursively build folder tree"""
            name = os.path.basename(path)
            
            # Skip hidden files and common ignore patterns
            if name.startswith('.') or name in ['node_modules', '__pycache__', 'dist', 'build', 'venv', '.git']:
                return None
            
            if current_depth >= max_depth:
                return None
            
            if os.path.isfile(path):
                return {
                    "name": name,
                    "type": "file",
                    "path": os.path.relpath(path, request.root_path)
                }
            elif os.path.isdir(path):
                children = []
                try:
                    for item in sorted(os.listdir(path)):
                        item_path = os.path.join(path, item)
                        child_tree = build_tree(item_path, max_depth, current_depth + 1)
                        if child_tree:
                            children.append(child_tree)
                except PermissionError:
                    pass
                
                return {
                    "name": name if name else os.path.basename(request.root_path),
                    "type": "folder",
                    "path": os.path.relpath(path, request.root_path) if path != request.root_path else ".",
                    "children": children
                }
            return None
        
        tree = build_tree(request.root_path)
        
        return {
            "status": "success",
            "root_path": request.root_path,
            "tree": tree
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting folder tree: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get folder tree: {str(e)}")