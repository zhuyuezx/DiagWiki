"""
Wiki generation utilities.

This module orchestrates wiki generation using specialized modules:
- WikiCache: File system caching
- WikiRAGQuery: Dual-RAG queries
- WikiDiagramGenerator: Diagram generation
"""

import os
import json
import logging
from typing import Optional, Dict, List

from utils.rag import RAG
from utils.repoUtil import RepoUtil
from utils.dataPipeline import DataPipeline, generate_db_name
from utils.wiki_cache import WikiCache
from utils.wiki_rag import WikiRAGQuery
from utils.wiki_diagram import WikiDiagramGenerator
from const.const import Const
from const.prompts import (
    build_wiki_structure_prompt,
    build_wiki_page_prompt,
    STRUCTURE_ANALYSIS_QUERIES,
    build_page_analysis_queries
)
from adalflow.core.types import ModelType
from const.const import get_llm_client

logger = logging.getLogger(__name__)


class WikiGenerator:
    """Main orchestrator for wiki generation using RAG."""
    
    def __init__(self, root_path: str, data_dir: str):
        """
        Initialize wiki generator.
        
        Args:
            root_path: Root path to the codebase
            data_dir: Base data directory for databases
        """
        self.root_path = root_path
        self.data_dir = data_dir
        self.db_name = generate_db_name(root_path)
        self.db_path = os.path.join(data_dir, self.db_name)
        self.cache = WikiCache(self.db_path)
        self.rag = None
        self.wiki_rag_query = None
        self.diagram_generator = None
    
    def ensure_database(self):
        """Ensure database exists, create if needed."""
        db_file = os.path.join(self.db_path, "db.pkl")
        if not os.path.exists(db_file):
            logger.info(f"Database file not found at {db_file}, creating...")
            pipeline = DataPipeline(
                db_name=self.db_name,
                embedder_model=Const.EMBEDDING_MODEL,
                text_splitter_config=Const.TEXT_SPLIT_CONFIG
            )
            result = pipeline.process_folder(
                folder_path=self.root_path,
                data_dir=self.data_dir
            )
            logger.info(f"Database created: {result}")
    
    def initialize_rag(self):
        """Initialize RAG system and specialized modules."""
        if self.rag is None:
            # Ensure database exists before loading
            self.ensure_database()
            
            self.rag = RAG()
            self.rag.load_database(self.db_path)
            logger.info(f"RAG initialized with {len(self.rag.transformed_docs)} documents")
            
            # Initialize specialized modules
            self.wiki_rag_query = WikiRAGQuery(self.cache.wiki_db_path, self.rag)
            self.diagram_generator = WikiDiagramGenerator(self.root_path, self.cache, self.rag)
    
    def query_wiki_rag(self, query: str, top_k: int = 20) -> Dict:
        """
        Query both wiki and codebase RAG for comprehensive answers.
        Delegates to WikiRAGQuery module.
        """
        self.initialize_rag()
        return self.wiki_rag_query.query_wiki_rag(query, top_k)
    
    def generate_structure(self, language: str = "en", comprehensive: bool = False, use_cache: bool = True) -> Dict:
        """
        Generate wiki structure using RAG analysis.
        
        Args:
            language: Target language code
            comprehensive: Whether to create comprehensive wiki
            use_cache: Whether to use cached structure if available
        
        Returns:
            Dict with status and structure
        """
        # Check cache first
        if use_cache:
            cached_structure = self.cache.load_structure()
            if cached_structure:
                logger.info("Using cached wiki structure")
                return {
                    "status": "success",
                    "root_path": self.root_path,
                    "comprehensive": comprehensive,
                    "language": language,
                    "wiki_structure": cached_structure,
                    "cached": True
                }
        
        # Ensure database and RAG are ready
        self.ensure_database()
        self.initialize_rag()
        
        # Generate file tree
        file_tree = RepoUtil.build_tree(self.root_path)
        logger.info("File tree generated")
        
        # Read README if exists
        readme_content = ""
        readme_paths = ["README.md", "README.MD", "readme.md", "README.txt", "README"]
        for readme_name in readme_paths:
            readme_path = os.path.join(self.root_path, readme_name)
            if os.path.exists(readme_path):
                try:
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        readme_content = f.read()
                    logger.info(f"README found: {readme_name}")
                    break
                except Exception as e:
                    logger.warning(f"Error reading README: {e}")
        
        # Perform RAG analysis
        logger.info("Querying RAG for codebase analysis...")
        rag_insights = []
        
        for query in STRUCTURE_ANALYSIS_QUERIES:
            try:
                answer, retrieved_docs = self.rag.call(
                    query=query,
                    top_k=Const.RAG_TOP_K,
                    use_reranking=True
                )
                rag_insights.append({
                    "query": query,
                    "answer": answer.answer,
                    "sources": [doc.text[:300] for doc in retrieved_docs[:3]]
                })
                logger.info(f"RAG query completed: {query[:50]}...")
            except Exception as e:
                logger.warning(f"RAG query failed: {e}")
        
        # Build prompt and call LLM
        folder_name = os.path.basename(self.root_path)
        prompt = build_wiki_structure_prompt(
            folder_name=folder_name,
            file_tree=file_tree,
            readme_content=readme_content,
            rag_insights=rag_insights,
            language=language,
            comprehensive=comprehensive
        )
        
        # Call LLM with timeout configuration
        model = get_llm_client()
        model_kwargs = {
            "model": Const.GENERATION_MODEL,
            "options": {
                "temperature": Const.DEFAULT_TEMPERATURE,
                "num_ctx": Const.LARGE_CONTEXT_WINDOW
            },
            "keep_alive": Const.OLLAMA_KEEP_ALIVE
        }
        
        api_kwargs = model.convert_inputs_to_api_kwargs(
            input=prompt,
            model_kwargs=model_kwargs,
            model_type=ModelType.LLM
        )
        
        logger.info("Calling LLM to generate wiki structure...")
        response = model.call(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        
        # Extract content from Ollama ChatResponse
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            wiki_structure = response.message.content
        elif hasattr(response, 'data'):
            wiki_structure = response.data
        elif isinstance(response, dict):
            wiki_structure = response.get('message', {}).get('content', '')
        else:
            logger.warning(f"Unexpected response type: {type(response)}")
            wiki_structure = str(response)
        
        logger.info(f"Wiki structure generated ({len(wiki_structure)} chars)")
        
        # Cache the structure
        self.cache.save_structure(wiki_structure)
        
        return {
            "status": "success",
            "root_path": self.root_path,
            "comprehensive": comprehensive,
            "language": language,
            "wiki_structure": wiki_structure,
            "cached": False
        }
    
    def generate_page(
        self,
        page_title: str,
        page_description: str,
        relevant_files: List[str],
        language: str = "en",
        page_id: str = None,
        use_cache: bool = True
    ) -> Dict:
        """
        Generate wiki page using RAG retrieval.
        
        Args:
            page_title: Title of the page
            page_description: Description of what the page should cover
            relevant_files: List of relevant file paths (hints)
            language: Target language code
            page_id: Optional page ID for caching
            use_cache: Whether to use cached page if available
        
        Returns:
            Dict with status and content
        """
        # Generate page_id if not provided
        if page_id is None:
            page_id = page_title.lower().replace(' ', '_')
        
        # Check cache first
        if use_cache:
            cached_page = self.cache.load_page(page_id)
            if cached_page:
                logger.info(f"Using cached wiki page: {page_title}")
                return {
                    "status": "success",
                    "page_title": page_title,
                    "language": language,
                    "content": cached_page,
                    "cached": True
                }
        
        # Ensure RAG is initialized
        self.initialize_rag()
        
        # Generate RAG queries
        rag_queries = build_page_analysis_queries(page_title, page_description)
        
        # Perform RAG queries
        logger.info(f"Performing {len(rag_queries)} RAG queries for: {page_title}")
        rag_results = []
        all_retrieved_docs = []
        
        for query in rag_queries:
            try:
                answer, retrieved_docs = self.rag.call(
                    query=query,
                    top_k=Const.RAG_TOP_K,
                    use_reranking=True
                )
                rag_results.append({
                    "query": query,
                    "answer": answer.answer,
                    "rationale": answer.rationale
                })
                all_retrieved_docs.extend(retrieved_docs)
                logger.info(f"RAG query completed: {query[:60]}...")
            except Exception as e:
                logger.warning(f"RAG query failed for '{query[:50]}...': {e}")
        
        # Deduplicate documents
        seen_paths = {}
        unique_docs = []
        for doc in all_retrieved_docs:
            file_path = doc.meta_data.get('file_path', 'unknown') if hasattr(doc, 'meta_data') else 'unknown'
            if file_path not in seen_paths:
                seen_paths[file_path] = doc
                unique_docs.append(doc)
        
        logger.info(f"Retrieved {len(unique_docs)} unique documents from {len(all_retrieved_docs)} total results")
        
        # Load explicit files
        file_contents = []
        for file_path in relevant_files[:20]:
            full_path = os.path.join(self.root_path, file_path) if not os.path.isabs(file_path) else file_path
            if os.path.exists(full_path) and os.path.isfile(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    file_contents.append({
                        "path": file_path,
                        "content": content[:3000]
                    })
                    logger.info(f"Loaded explicit file: {file_path}")
                except Exception as e:
                    logger.warning(f"Error reading file {file_path}: {e}")
        
        # Build context strings
        rag_context = "\n\n".join([
            f"Query: {r['query']}\nAnswer: {r['answer']}\nRationale: {r['rationale']}"
            for r in rag_results
        ])
        
        retrieved_sources = "\n\n".join([
            f"Source {i+1} ({doc.meta_data.get('file_path', 'unknown') if hasattr(doc, 'meta_data') else 'unknown'}):\n{doc.text[:800]}"
            for i, doc in enumerate(unique_docs[:15])
        ])
        
        # Build prompt
        prompt = build_wiki_page_prompt(
            page_title=page_title,
            page_description=page_description,
            rag_context=rag_context,
            retrieved_sources=retrieved_sources,
            file_contents=file_contents,
            unique_docs=unique_docs,
            language=language
        )
        
        # Call LLM with timeout configuration
        model = get_llm_client()
        model_kwargs = {
            "model": Const.GENERATION_MODEL,
            "options": {
                "temperature": Const.DEFAULT_TEMPERATURE,
                "num_ctx": Const.LARGE_CONTEXT_WINDOW
            },
            "keep_alive": Const.OLLAMA_KEEP_ALIVE
        }
        
        api_kwargs = model.convert_inputs_to_api_kwargs(
            input=prompt,
            model_kwargs=model_kwargs,
            model_type=ModelType.LLM
        )
        
        logger.info(f"Calling LLM to generate wiki page for: {page_title}")
        response = model.call(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        
        # Extract content from Ollama ChatResponse
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            page_content = response.message.content
        elif hasattr(response, 'data'):
            page_content = response.data
        elif isinstance(response, dict):
            page_content = response.get('message', {}).get('content', '')
        else:
            logger.warning(f"Unexpected response type: {type(response)}")
            page_content = str(response)
        
        logger.info(f"Wiki page generated ({len(page_content)} chars)")
        
        # Cache the page
        self.cache.save_page(
            page_id=page_id,
            page_title=page_title,
            content=page_content,
            metadata={
                "rag_queries_performed": len(rag_queries),
                "rag_results_count": len(rag_results),
                "unique_sources_retrieved": len(unique_docs),
                "explicit_files_loaded": len(file_contents),
                "language": language
            }
        )
        
        return {
            "status": "success",
            "page_title": page_title,
            "language": language,
            "rag_queries_performed": len(rag_queries),
            "rag_results_count": len(rag_results),
            "unique_sources_retrieved": len(unique_docs),
            "explicit_files_loaded": len(file_contents),
            "content": page_content,
            "cached": False,
            "cache_path": self.cache.pages_dir
        }
    
    def identify_diagram_sections(
        self,
        language: str = "en",
        use_cache: bool = True
    ) -> Dict:
        """
        Step 1: Identify diagram sections for the codebase.
        Delegates to WikiDiagramGenerator module.
        """
        self.initialize_rag()
        return self.diagram_generator.identify_diagram_sections(language, use_cache)
    
    def generate_section_diagram(
        self,
        section_id: str,
        section_title: str,
        section_description: str,
        diagram_type: str,
        key_concepts: List[str],
        language: str = "en",
        use_cache: bool = True,
        reference_files: List[str] = None
    ) -> Dict:
        """
        Step 2: Generate diagram for a single section.
        Delegates to WikiDiagramGenerator module.
        
        Args:
            reference_files: Optional list of file paths to use as reference (bypasses RAG)
        """
        self.initialize_rag()
        return self.diagram_generator.generate_section_diagram(
            section_id, section_title, section_description,
            diagram_type, key_concepts, language, use_cache, reference_files
        )
    
    def fix_corrupted_diagram(
        self,
        section_id: str,
        section_title: str,
        section_description: str,
        diagram_type: str,
        key_concepts: List[str],
        language: str,
        corrupted_diagram: str,
        error_message: str
    ) -> Dict:
        """
        Fix a corrupted Mermaid diagram that failed to render.
        
        Args:
            section_id: Section ID
            section_title: Title of the section
            section_description: Description of the section
            diagram_type: Type of diagram
            key_concepts: List of key concepts
            language: Language code
            corrupted_diagram: The corrupted Mermaid code
            error_message: The error message from Mermaid
        
        Returns:
            Dict with corrected diagram
        """
        self.initialize_rag()
        return self.diagram_generator.fix_corrupted_diagram(
            section_id, section_title, section_description,
            diagram_type, key_concepts, language,
            corrupted_diagram, error_message
        )
    
    def analyze_wiki_problem(
        self,
        user_prompt: str,
        wiki_items: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        Analyze a user's wiki-related request and determine if modifications are needed.
        
        Args:
            user_prompt: User's request describing the problem or question
            wiki_items: Optional dict of {wiki_name: question} pairs
        
        Returns:
            Dict with either answer (for questions) or modification plan
        """
        from const.prompts import build_wiki_problem_analysis_prompt
        from adalflow.core.db import LocalDB
        
        # Ensure RAG is initialized
        self.initialize_rag()
        
        # Retrieve existing wiki content from wiki database
        wiki_context = ""
        wiki_db_path = self.cache.wiki_db_path
        
        if os.path.exists(wiki_db_path):
            try:
                wiki_db = LocalDB.load_state(filepath=wiki_db_path)
                wiki_docs = wiki_db.get_transformed_data(key="wiki_content")
                
                if wiki_docs:
                    wiki_context = "\n\n".join([
                        f"[{doc.meta_data.get('content_id', 'unknown')}]\n{doc.text[:500]}"
                        for doc in wiki_docs[:10]
                    ])
                    logger.info(f"Retrieved {len(wiki_docs)} wiki documents")
            except Exception as e:
                logger.warning(f"Could not load wiki context: {e}")
        
        if not wiki_context:
            wiki_context = "No existing wiki content found."
        
        # Query codebase for relevant context
        try:
            rag_answer, codebase_docs = self.rag.call(
                query=user_prompt,
                top_k=Const.RAG_TOP_K,
                use_reranking=True
            )
            
            codebase_context = "\n\n".join([
                f"[{doc.meta_data.get('file_path', 'unknown')}]\n{doc.text[:500]}"
                for doc in codebase_docs[:20]
            ])
        except Exception as e:
            logger.warning(f"Could not query codebase: {e}")
            codebase_context = "Codebase context unavailable."
        
        # Build analysis prompt
        prompt = build_wiki_problem_analysis_prompt(
            user_prompt=user_prompt,
            wiki_context=wiki_context,
            codebase_context=codebase_context,
            wiki_items=wiki_items
        )
        
        # Call LLM with timeout configuration
        model = get_llm_client()
        model_kwargs = {
            "model": Const.GENERATION_MODEL,
            "format": "json",
            "options": {"temperature": Const.DEFAULT_TEMPERATURE, "num_ctx": Const.LARGE_CONTEXT_WINDOW},
            "keep_alive": Const.OLLAMA_KEEP_ALIVE
        }
        
        api_kwargs = model.convert_inputs_to_api_kwargs(
            input=prompt,
            model_kwargs=model_kwargs,
            model_type=ModelType.LLM
        )
        
        response = model.call(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        
        # Extract response
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            response_text = response.message.content
        else:
            response_text = str(response)
        
        try:
            result = json.loads(response_text)
            
            # Validate response format
            intent = result.get('intent')
            
            if intent == 'question':
                # For questions, must have 'answer' field and NOT have 'modify'/'create'
                if 'answer' not in result:
                    logger.error("Question intent but missing 'answer' field")
                    return {
                        "status": "error",
                        "error": "Invalid response: question intent requires 'answer' field",
                        "raw_response": response_text[:500]
                    }
                if 'modify' in result or 'create' in result:
                    logger.warning("Question intent should not have 'modify'/'create' fields, removing them")
                    result.pop('modify', None)
                    result.pop('create', None)
            
            elif intent == 'modification':
                # For modifications, must have 'modify'/'create' and NOT have 'answer'
                if 'modify' not in result or 'create' not in result:
                    logger.error("Modification intent but missing 'modify'/'create' fields")
                    return {
                        "status": "error",
                        "error": "Invalid response: modification intent requires 'modify' and 'create' fields",
                        "raw_response": response_text[:500]
                    }
                if 'answer' in result:
                    logger.warning("Modification intent should not have 'answer' field, removing it")
                    result.pop('answer', None)
            
            else:
                logger.error(f"Unknown intent: {intent}")
                return {
                    "status": "error",
                    "error": f"Invalid intent: {intent}. Must be 'question' or 'modification'",
                    "raw_response": response_text[:500]
                }
            
            result["status"] = "success"
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return {
                "status": "error",
                "error": "Failed to parse analysis",
                "raw_response": response_text[:500]
            }
    
    def create_wiki_section(
        self,
        wiki_name: str,
        prompt: str
    ) -> Dict:
        """
        Create a new wiki section based on a detailed prompt.
        
        Args:
            wiki_name: ID/name for the new section
            prompt: Detailed creation prompt from problem analysis
        
        Returns:
            Dict with the created wiki section
        """
        from const.prompts import build_wiki_creation_prompt
        from utils.mermaid_parser import parse_mermaid_diagram, validate_mermaid_syntax
        
        # Ensure RAG is initialized
        self.initialize_rag()
        
        # Query codebase for relevant context
        try:
            rag_answer, codebase_docs = self.rag.call(
                query=prompt,
                top_k=Const.RAG_TOP_K,
                use_reranking=True
            )
            
            codebase_context = "\n\n".join([
                f"[{doc.meta_data.get('file_path', 'unknown')}]\n{doc.text[:800]}"
                for doc in codebase_docs[:20]
            ])
        except Exception as e:
            logger.warning(f"Could not query codebase: {e}")
            codebase_context = "Codebase context unavailable."
        
        # Build creation prompt
        creation_prompt = build_wiki_creation_prompt(
            wiki_name=wiki_name,
            creation_prompt=prompt,
            codebase_context=codebase_context
        )
        
        # Call LLM with timeout configuration
        model = get_llm_client()
        model_kwargs = {
            "model": Const.GENERATION_MODEL,
            "format": "json",
            "options": {"temperature": Const.DEFAULT_TEMPERATURE, "num_ctx": Const.LARGE_CONTEXT_WINDOW},
            "keep_alive": Const.OLLAMA_KEEP_ALIVE
        }
        
        api_kwargs = model.convert_inputs_to_api_kwargs(
            input=creation_prompt,
            model_kwargs=model_kwargs,
            model_type=ModelType.LLM
        )
        
        response = model.call(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        
        # Extract response
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            response_text = response.message.content
        else:
            response_text = str(response)
        
        try:
            diagram_data = json.loads(response_text)
            
            # Validate and parse mermaid code
            mermaid_code = diagram_data.get('mermaid_code', '')
            is_valid, validation_msg = validate_mermaid_syntax(mermaid_code)
            
            if is_valid:
                parsed = parse_mermaid_diagram(mermaid_code)
                
                # Structure the result
                result = {
                    "status": "success",
                    "section_id": wiki_name,
                    "section_title": diagram_data.get('section_title', ''),
                    "section_description": diagram_data.get('section_description', ''),
                    "language": "en",
                    "diagram": {
                        "mermaid_code": mermaid_code,
                        "description": diagram_data.get('diagram_description', ''),
                        "is_valid": True,
                        "diagram_type": parsed['diagram_type']
                    },
                    "nodes": {},
                    "edges": {},
                    "cached": False
                }
                
                # Add node explanations
                node_explanations = diagram_data.get('node_explanations', {})
                for node_id in parsed['node_list']:
                    node_data = parsed['nodes'][node_id]
                    result['nodes'][node_id] = {
                        "label": node_data['label'],
                        "shape": node_data['shape'],
                        "explanation": node_explanations.get(node_id, "")
                    }
                
                # Add edge explanations
                edge_explanations = diagram_data.get('edge_explanations', {})
                for edge in parsed['edges']:
                    edge_key = edge['key']
                    result['edges'][edge_key] = {
                        "source": edge['source'],
                        "target": edge['target'],
                        "label": edge['label'],
                        "explanation": edge_explanations.get(edge_key, "")
                    }
                
                # Cache the result
                cache_file = os.path.join(self.cache.diagrams_dir, f"diag_{wiki_name}.json")
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                
                # Save Mermaid code separately
                mermaid_file = os.path.join(self.cache.diagrams_dir, f"diag_{wiki_name}.mmd")
                with open(mermaid_file, 'w', encoding='utf-8') as f:
                    f.write(mermaid_code)
                
                # Add to wiki RAG database
                try:
                    self.cache.add_wiki_content_to_rag(
                        content_type="diagram",
                        content_id=wiki_name,
                        content_data=result
                    )
                    logger.info(f"Added new wiki section to RAG: {wiki_name}")
                except Exception as e:
                    logger.warning(f"Failed to add to wiki RAG: {e}")
                
                return result
            else:
                return {
                    "status": "error",
                    "error": f"Invalid Mermaid syntax: {validation_msg}",
                    "diagram": diagram_data
                }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse creation response: {e}")
            return {
                "status": "error",
                "error": "Failed to parse diagram data",
                "raw_response": response_text[:500]
            }
    
    def modify_wiki_section(
        self,
        wiki_name: str,
        modification_prompt: str
    ) -> Dict:
        """
        Modify an existing wiki section.
        
        Args:
            wiki_name: ID/name of the section to modify
            modification_prompt: What to change
        
        Returns:
            Dict with the modified wiki section
        """
        from const.prompts import build_wiki_modification_prompt
        from utils.mermaid_parser import parse_mermaid_diagram, validate_mermaid_syntax
        
        # Ensure RAG is initialized
        self.initialize_rag()
        
        # Load existing content
        cache_file = os.path.join(self.cache.diagrams_dir, f"diag_{wiki_name}.json")
        if not os.path.exists(cache_file):
            return {
                "status": "error",
                "error": f"Wiki section '{wiki_name}' not found. Use create instead."
            }
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                existing_content = json.load(f)
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to load existing content: {e}"
            }
        
        # Query codebase for updated context
        try:
            rag_answer, codebase_docs = self.rag.call(
                query=f"{existing_content.get('section_title', '')} {modification_prompt}",
                top_k=Const.RAG_TOP_K,
                use_reranking=True
            )
            
            codebase_context = "\n\n".join([
                f"[{doc.meta_data.get('file_path', 'unknown')}]\n{doc.text[:800]}"
                for doc in codebase_docs[:20]
            ])
        except Exception as e:
            logger.warning(f"Could not query codebase: {e}")
            codebase_context = "Codebase context unavailable."
        
        # Build modification prompt
        mod_prompt = build_wiki_modification_prompt(
            wiki_name=wiki_name,
            existing_content=existing_content,
            modification_prompt=modification_prompt,
            codebase_context=codebase_context
        )
        
        # Call LLM with timeout configuration
        model = get_llm_client()
        model_kwargs = {
            "model": Const.GENERATION_MODEL,
            "format": "json",
            "options": {"temperature": Const.DEFAULT_TEMPERATURE, "num_ctx": Const.LARGE_CONTEXT_WINDOW},
            "keep_alive": Const.OLLAMA_KEEP_ALIVE
        }
        
        api_kwargs = model.convert_inputs_to_api_kwargs(
            input=mod_prompt,
            model_kwargs=model_kwargs,
            model_type=ModelType.LLM
        )
        
        response = model.call(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        
        # Extract response
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            response_text = response.message.content
        else:
            response_text = str(response)
        
        try:
            diagram_data = json.loads(response_text)
            
            # Validate and parse mermaid code
            mermaid_code = diagram_data.get('mermaid_code', '')
            is_valid, validation_msg = validate_mermaid_syntax(mermaid_code)
            
            if is_valid:
                parsed = parse_mermaid_diagram(mermaid_code)
                
                # Structure the result
                result = {
                    "status": "success",
                    "section_id": wiki_name,
                    "section_title": diagram_data.get('section_title', ''),
                    "section_description": diagram_data.get('section_description', ''),
                    "language": existing_content.get('language', 'en'),
                    "diagram": {
                        "mermaid_code": mermaid_code,
                        "description": diagram_data.get('diagram_description', ''),
                        "is_valid": True,
                        "diagram_type": parsed['diagram_type']
                    },
                    "nodes": {},
                    "edges": {},
                    "cached": False,
                    "modified": True
                }
                
                # Add node explanations
                node_explanations = diagram_data.get('node_explanations', {})
                for node_id in parsed['node_list']:
                    node_data = parsed['nodes'][node_id]
                    result['nodes'][node_id] = {
                        "label": node_data['label'],
                        "shape": node_data['shape'],
                        "explanation": node_explanations.get(node_id, "")
                    }
                
                # Add edge explanations
                edge_explanations = diagram_data.get('edge_explanations', {})
                for edge in parsed['edges']:
                    edge_key = edge['key']
                    result['edges'][edge_key] = {
                        "source": edge['source'],
                        "target": edge['target'],
                        "label": edge['label'],
                        "explanation": edge_explanations.get(edge_key, "")
                    }
                
                # Cache the modified result
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                
                # Save Mermaid code separately
                mermaid_file = os.path.join(self.cache.diagrams_dir, f"diag_{wiki_name}.mmd")
                with open(mermaid_file, 'w', encoding='utf-8') as f:
                    f.write(mermaid_code)
                
                # Update wiki RAG database
                try:
                    self.cache.add_wiki_content_to_rag(
                        content_type="diagram",
                        content_id=wiki_name,
                        content_data=result
                    )
                    logger.info(f"Updated wiki section in RAG: {wiki_name}")
                except Exception as e:
                    logger.warning(f"Failed to update wiki RAG: {e}")
                
                return result
            else:
                return {
                    "status": "error",
                    "error": f"Invalid Mermaid syntax: {validation_msg}",
                    "diagram": diagram_data
                }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse modification response: {e}")
            return {
                "status": "error",
                "error": "Failed to parse diagram data",
                "raw_response": response_text[:500]
            }