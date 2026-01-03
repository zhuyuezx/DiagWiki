"""
Wiki diagram generation utilities.

This module handles the two-step diagram generation process:
1. Identify diagram sections (what to visualize)
2. Generate diagrams with explanations (create visualizations)
"""

import os
import json
import logging
from typing import Dict, List
from adalflow.core.types import ModelType
from const.const import Const, get_llm_client
from const.prompts import (
    build_page_analysis_queries,
    build_diagram_sections_prompt,
    build_single_diagram_prompt
)
from utils.mermaid_parser import parse_mermaid_diagram, validate_mermaid_syntax

logger = logging.getLogger(__name__)


class WikiDiagramGenerator:
    """Handles diagram generation for wiki content."""
    
    def __init__(self, root_path: str, cache, rag_instance):
        """
        Initialize diagram generator.
        
        Args:
            root_path: Root path to the codebase
            cache: WikiCache instance for caching
            rag_instance: Initialized RAG instance for queries
        """
        self.root_path = root_path
        self.cache = cache
        self.rag = rag_instance
    
    def identify_diagram_sections(
        self,
        language: str = "en",
        use_cache: bool = True
    ) -> Dict:
        """
        Step 1: Identify diagram sections for the codebase (Diagram-First Wiki).
        
        This is for a DIAGRAM-FIRST WIKI - diagrams ARE the content, not supplements.
        Analyzes the codebase and identifies diagram sections that together explain it.
        The number of sections is determined by the LLM based on codebase complexity.
        
        Args:
            language: Target language code
            use_cache: Whether to use cached sections if available
        
        Returns:
            Dict with status and identified sections list
        """
        # Use repo name as page_id for caching
        repo_name = os.path.basename(self.root_path)
        page_id = repo_name.lower().replace(' ', '_').replace('/', '_')
        
        # Check cache first
        if use_cache:
            cache_file = os.path.join(self.cache.diagrams_dir, f"{page_id}_sections.json")
            if os.path.exists(cache_file):
                logger.info(f"✅ Using cached diagram sections from: {cache_file}")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    cached_data['cached'] = True
                    cached_data['cache_file'] = cache_file
                    return cached_data
        
        # Ensure RAG is initialized
        if self.rag is None:
            raise RuntimeError("RAG not initialized. Call initialize_rag() first.")
        
        # Generate RAG queries
        rag_queries = build_page_analysis_queries(repo_name, "Identify key components and workflows suitable for diagrammatic representation.")
        
        # Perform RAG queries
        logger.info(f"Performing {len(rag_queries)} RAG queries for: {repo_name}")
        rag_results = []
        
        for query in rag_queries:
            try:
                answer, retrieved_docs = self.rag.call(
                    query=query,
                    top_k=20,
                    use_reranking=True
                )
                rag_results.append({
                    "query": query,
                    "answer": answer.answer,
                    "rationale": answer.rationale
                })
                logger.info(f"RAG query completed: {query[:60]}...")
            except Exception as e:
                logger.warning(f"RAG query failed for '{query[:50]}...': {e}")
        
        # Build RAG context
        rag_context = "\n\n".join([
            f"Query: {r['query']}\nAnswer: {r['answer']}\nRationale: {r['rationale']}"
            for r in rag_results
        ])
        
        # Step 1: Identify diagram sections
        logger.info("Identifying diagram sections...")
        sections_prompt = build_diagram_sections_prompt(
            repo_name=repo_name,
            rag_context=rag_context,
            language=language
        )
        
        # Use get_llm_client() for proper timeout configuration
        model = get_llm_client()
        model_kwargs = {
            "model": Const.GENERATION_MODEL,
            "format": "json",
            "options": {
                "temperature": 0.7,
                "num_ctx": 8192
            },
            "keep_alive": Const.OLLAMA_KEEP_ALIVE  # Keep model loaded
        }
        
        api_kwargs = model.convert_inputs_to_api_kwargs(
            input=sections_prompt,
            model_kwargs=model_kwargs,
            model_type=ModelType.LLM
        )
        
        response = model.call(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        
        # Extract content
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            sections_json = response.message.content
        else:
            sections_json = str(response)
        
        try:
            sections_data = json.loads(sections_json)
            identified_sections = sections_data.get('sections', [])
            logger.info(f"Identified {len(identified_sections)} sections for diagrams")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse sections JSON: {e}")
            identified_sections = []
        
        # Cache the result
        cache_file = os.path.join(self.cache.diagrams_dir, f"{page_id}_sections.json")
        
        result = {
            "status": "success",
            "repo_name": repo_name,
            "language": language,
            "sections": identified_sections,
            "rag_queries_performed": len(rag_queries),
            "cached": False,
            "cache_file": cache_file
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Cached sections to: {cache_file}")
        
        return result
    
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
        Step 2: Generate diagram for a single section (Two-Step API - Part 2).
        
        Generates a comprehensive Mermaid diagram with node/edge explanations for one section.
        
        Args:
            section_id: ID of this section
            section_title: Title of this section
            section_description: Description of what this section covers
            diagram_type: Type of Mermaid diagram (flowchart, sequence, etc.)
            key_concepts: List of key concepts to include
            language: Target language code
            use_cache: Whether to use cached diagram if available
            reference_files: Optional list of file paths to use as reference (bypasses RAG)
        
        Returns:
            Dict with diagram, nodes with explanations, edges with explanations
        """
        # Check cache first
        if use_cache:
            cache_file = os.path.join(self.cache.diagrams_dir, f"diag_{section_id}.json")
            mermaid_file = os.path.join(self.cache.diagrams_dir, f"diag_{section_id}.mmd")
            if os.path.exists(cache_file):
                logger.info(f"✅ Using cached diagram from: {cache_file}")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    cached_data['cached'] = True
                    cached_data['cache_file'] = cache_file
                    cached_data['mermaid_file'] = mermaid_file if os.path.exists(mermaid_file) else None
                    return cached_data
        
        # Ensure RAG is initialized
        if self.rag is None:
            raise RuntimeError("RAG not initialized. Call initialize_rag() first.")
        
        # For custom diagrams (long prompts as titles), generate a concise title
        original_title = section_title
        if section_id.startswith('custom_') and len(section_title) > 60:
            logger.info(f"Generating concise title from prompt: {section_title[:100]}...")
            section_title = self._generate_concise_title(section_title, section_description)
            logger.info(f"Generated title: {section_title}")
        
        # Perform RAG queries or use manual reference files
        if reference_files:
            # Manual mode: read specified files directly
            logger.info(f"Using {len(reference_files)} manually selected reference files")
            rag_context, retrieved_sources, all_retrieved_docs = self._read_reference_files(reference_files)
        else:
            # Automatic mode: use RAG
            rag_context, retrieved_sources, all_retrieved_docs = self._perform_section_rag_queries(section_title if len(section_title) < 60 else section_description)
        
        # Build diagram prompt
        logger.info(f"Generating diagram for: {section_title}")
        diagram_prompt = build_single_diagram_prompt(
            section_title=section_title,
            section_description=section_description,
            diagram_type=diagram_type,
            key_concepts=key_concepts,
            rag_context=rag_context,
            retrieved_sources=retrieved_sources,
            language=language
        )
        
        # Call LLM for diagram
        diagram_data = self._generate_diagram_with_llm(diagram_prompt)
        
        # Extract unique source file paths from retrieved documents
        source_files = []
        seen_paths = set()
        for doc in all_retrieved_docs:
            if hasattr(doc, 'meta_data'):
                file_path = doc.meta_data.get('file_path', '')
                if file_path and file_path not in seen_paths:
                    seen_paths.add(file_path)
                    source_files.append({
                        "file": file_path,
                        "relevance": f"Used to generate {section_title}"
                    })
        
        # Process the diagram response
        result = self._process_diagram_response(
            diagram_data,
            section_id,
            section_title,
            section_description,
            language,
            len(rag_context.split('\n\n')),  # Approximate query count
            source_files  # Pass source files
        )
        
        # Cache and add to wiki RAG if successful
        if result.get("status") == "success":
            self._cache_diagram_result(result)
        
        return result
    
    def _generate_concise_title(self, prompt: str, description: str) -> str:
        """Generate a concise title from a user prompt for custom diagrams."""
        title_prompt = f"""Given this user request for a diagram:

"{prompt}"

Generate a concise, descriptive title (max 8 words) that captures the essence of what they want to visualize.

Requirements:
- Maximum 8 words
- Clear and specific
- Descriptive of the diagram content
- Professional tone

Return ONLY the title text, nothing else."""

        # Use get_llm_client() for proper timeout configuration
        model = get_llm_client()
        model_kwargs = {
            "model": Const.GENERATION_MODEL,
            "options": {
                "temperature": 0.3,
                "num_ctx": 4096
            },
            "keep_alive": Const.OLLAMA_KEEP_ALIVE  # Keep model loaded
        }
        
        api_kwargs = model.convert_inputs_to_api_kwargs(
            input=title_prompt,
            model_kwargs=model_kwargs,
            model_type=ModelType.LLM
        )
        
        response = model.call(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        
        # Extract title from response
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            title = response.message.content.strip()
        else:
            title = str(response).strip()
        
        # Clean up the title (remove quotes, extra whitespace)
        title = title.strip('"\'').strip()
        
        # Fallback if title is too long or empty
        if not title or len(title) > 100:
            # Extract first few words from prompt
            words = prompt.split()[:8]
            title = ' '.join(words)
            if len(prompt.split()) > 8:
                title += '...'
        
        return title
    
    def _perform_section_rag_queries(self, section_title: str) -> tuple:
        """Perform RAG queries for a specific section."""
        section_queries = [
            f"How does {section_title} work?",
            f"What are the components involved in {section_title}?",
            f"Explain the implementation of {section_title}"
        ]
        
        logger.info(f"Performing RAG queries for section: {section_title}")
        rag_results = []
        all_retrieved_docs = []
        
        for query in section_queries:
            try:
                answer, retrieved_docs = self.rag.call(
                    query=query,
                    top_k=20,
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
        
        # Build RAG context
        MAX_RAG_CONTEXT_CHARS = 100000
        
        rag_context_parts = []
        current_length = 0
        
        for r in rag_results:
            part = f"Query: {r['query']}\nAnswer: {r['answer']}\nRationale: {r['rationale']}"
            part_length = len(part)
            
            if current_length + part_length > MAX_RAG_CONTEXT_CHARS:
                # Truncate last part to fit
                remaining = MAX_RAG_CONTEXT_CHARS - current_length
                if remaining > 100:  # Only add if meaningful space left
                    truncated = part[:remaining] + "\n\n[... truncated for size limits ...]"
                    rag_context_parts.append(truncated)
                break
            
            rag_context_parts.append(part)
            current_length += part_length + 2  # +2 for "\n\n" separator
        
        rag_context = "\n\n".join(rag_context_parts)
        logger.info(f"RAG context size: {len(rag_context)} chars (~{len(rag_context)//4} tokens)")
        
        # Deduplicate documents for retrieval
        seen_paths = {}
        unique_docs = []
        for doc in all_retrieved_docs:
            file_path = doc.meta_data.get('file_path', 'unknown') if hasattr(doc, 'meta_data') else 'unknown'
            if file_path not in seen_paths:
                seen_paths[file_path] = doc
                unique_docs.append(doc)
        
        # Also limit retrieved sources to prevent overflow
        MAX_SOURCE_CHARS_EACH = 600  # Reduced from 800
        MAX_SOURCES = 15
        
        retrieved_sources = "\n\n".join([
            f"Source {i+1} ({doc.meta_data.get('file_path', 'unknown') if hasattr(doc, 'meta_data') else 'unknown'}):\n{doc.text[:MAX_SOURCE_CHARS_EACH]}"
            for i, doc in enumerate(unique_docs[:MAX_SOURCES])
        ])
        logger.info(f"Retrieved sources size: {len(retrieved_sources)} chars (~{len(retrieved_sources)//4} tokens)")
        
        return rag_context, retrieved_sources, all_retrieved_docs
    
    def _read_reference_files(self, file_paths: List[str]):
        """
        Read content directly from specified files (manual reference mode).
        
        Args:
            file_paths: List of file paths relative to the root_path
            
        Returns:
            Tuple of (rag_context, retrieved_sources, all_docs)
        """
        logger.info(f"Reading {len(file_paths)} manually selected reference files")
        
        # Create mock document objects for consistency
        from adalflow.core.types import Document
        
        all_docs = []
        rag_context_parts = []
        retrieved_sources_parts = []
        
        MAX_FILE_CHARS = 50000  # Limit per file to prevent overflow
        
        for i, file_path in enumerate(file_paths):
            # Construct full path
            full_path = os.path.join(self.root_path, file_path)
            
            if not os.path.exists(full_path):
                logger.warning(f"Reference file not found: {file_path}")
                continue
            
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Truncate if too large
                if len(content) > MAX_FILE_CHARS:
                    content = content[:MAX_FILE_CHARS] + "\n\n[... truncated for size limits ...]"
                
                # Create mock document
                doc = Document(
                    text=content,
                    meta_data={"file_path": file_path}
                )
                all_docs.append(doc)
                
                # Add to context
                rag_context_parts.append(f"File: {file_path}\n{content}")
                
                # Add to sources (with preview)
                preview_length = 600
                retrieved_sources_parts.append(
                    f"Source {i+1} ({file_path}):\n{content[:preview_length]}"
                )
                
                logger.info(f"Read reference file: {file_path} ({len(content)} chars)")
                
            except Exception as e:
                logger.error(f"Failed to read reference file {file_path}: {e}")
                continue
        
        rag_context = "\n\n".join(rag_context_parts)
        retrieved_sources = "\n\n".join(retrieved_sources_parts)
        
        logger.info(f"Manual reference context size: {len(rag_context)} chars from {len(all_docs)} files")
        
        return rag_context, retrieved_sources, all_docs
    
    def _generate_diagram_with_llm(self, diagram_prompt: str) -> str:
        """Generate diagram using LLM with size validation."""
        # Validate prompt size BEFORE calling LLM
        prompt_chars = len(diagram_prompt)
        estimated_tokens = prompt_chars // 4
        context_window = 16384
        usage_percentage = (estimated_tokens / context_window) * 100
        
        logger.info(f"Prompt size: {prompt_chars:,} chars (~{estimated_tokens:,} tokens, {usage_percentage:.1f}% of context)")
        
        if usage_percentage > 90:
            logger.warning(f"⚠️  Prompt exceeds 90% of context window! This may cause hanging.")
            logger.warning(f"⚠️  Consider reducing MAX_RAG_CONTEXT_CHARS if this takes >60 seconds.")
        elif usage_percentage > 75:
            logger.warning(f"⚠️  Prompt exceeds 75% of context window. Processing may be slow.")
        
        # Use get_llm_client() for proper timeout configuration
        model = get_llm_client()
        model_kwargs = {
            "model": Const.GENERATION_MODEL,
            "format": "json",
            "options": {
                "temperature": 0.7,
                "num_ctx": 16384
            },
            "keep_alive": Const.OLLAMA_KEEP_ALIVE  # Keep model loaded
        }
        
        api_kwargs = model.convert_inputs_to_api_kwargs(
            input=diagram_prompt,
            model_kwargs=model_kwargs,
            model_type=ModelType.LLM
        )
        
        diagram_response = model.call(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        
        # Extract diagram content
        if hasattr(diagram_response, 'message') and hasattr(diagram_response.message, 'content'):
            return diagram_response.message.content
        else:
            return str(diagram_response)
    
    def _process_diagram_response(
        self,
        diagram_json: str,
        section_id: str,
        section_title: str,
        section_description: str,
        language: str,
        rag_query_count: int,
        source_files: List[Dict] = None
    ) -> Dict:
        """Process the LLM diagram response and validate."""
        if source_files is None:
            source_files = []
        
        try:
            diagram_data = json.loads(diagram_json)
            mermaid_code = diagram_data.get('mermaid_code', '')
            diagram_description = diagram_data.get('diagram_description', '')
            node_explanations = diagram_data.get('node_explanations', {})
            edge_explanations = diagram_data.get('edge_explanations', {})
            
            # Validate and parse mermaid code
            is_valid, validation_msg = validate_mermaid_syntax(mermaid_code)
            
            if is_valid:
                parsed = parse_mermaid_diagram(mermaid_code)
                
                # Combine LLM explanations with parsed structure
                nodes = {}
                for node_id in parsed['node_list']:
                    node_data = parsed['nodes'][node_id]
                    nodes[node_id] = {
                        "label": node_data['label'],
                        "shape": node_data['shape'],
                        "explanation": node_explanations.get(node_id, "")
                    }
                
                edges = {}
                for edge in parsed['edges']:
                    edge_key = edge['key']
                    edges[edge_key] = {
                        "source": edge['source'],
                        "target": edge['target'],
                        "label": edge['label'],
                        "explanation": edge_explanations.get(edge_key, "")
                    }
                
                # Prepare cache file paths
                cache_file = os.path.join(self.cache.diagrams_dir, f"diag_{section_id}.json")
                mermaid_file = os.path.join(self.cache.diagrams_dir, f"diag_{section_id}.mmd")
                
                return {
                    "status": "success",
                    "section_id": section_id,
                    "section_title": section_title,
                    "section_description": section_description,
                    "language": language,
                    "diagram": {
                        "mermaid_code": mermaid_code,
                        "description": diagram_description,
                        "is_valid": True,
                        "diagram_type": parsed['diagram_type']
                    },
                    "nodes": nodes,
                    "edges": edges,
                    "rag_sources": source_files,
                    "rag_queries_performed": rag_query_count,
                    "cached": False,
                    "cache_file": cache_file,
                    "mermaid_file": mermaid_file
                }
            else:
                return {
                    "status": "error",
                    "section_id": section_id,
                    "section_title": section_title,
                    "error": f"Invalid Mermaid syntax: {validation_msg}",
                    "diagram": {
                        "mermaid_code": mermaid_code,
                        "description": diagram_description,
                        "is_valid": False,
                        "validation_error": validation_msg
                    },
                    "nodes": node_explanations,
                    "edges": edge_explanations
                }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse diagram JSON: {e}")
            return {
                "status": "error",
                "section_id": section_id,
                "section_title": section_title,
                "error": f"JSON parse error: {str(e)}",
                "raw_response": diagram_json[:500]
            }
    
    def _cache_diagram_result(self, result: Dict):
        """Cache the diagram result and add to wiki RAG."""
        if 'cache_file' in result:
            # Save JSON file
            with open(result['cache_file'], 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Cached diagram JSON to: {result['cache_file']}")
            
            # Save Mermaid code separately for easy inspection
            if 'mermaid_file' in result and result['diagram'].get('mermaid_code'):
                with open(result['mermaid_file'], 'w', encoding='utf-8') as f:
                    f.write(result['diagram']['mermaid_code'])
                logger.info(f"💾 Cached Mermaid code to: {result['mermaid_file']}")
            
            # If this is a custom section, add it to the sections cache
            if result.get('section_id', '').startswith('custom_'):
                self._add_custom_section_to_cache(result)
            
            # Add to wiki RAG database for /askWiki endpoint
            try:
                self.cache.add_wiki_content_to_rag(
                    content_type="diagram",
                    content_id=result['section_id'],
                    content_data=result
                )
                logger.info(f"📚 Added diagram to wiki RAG: {result['section_id']}")
            except Exception as e:
                logger.warning(f"Failed to add diagram to wiki RAG: {e}")
    
    def _add_custom_section_to_cache(self, result: Dict):
        """Add a custom section to the sections cache file."""
        try:
            repo_name = os.path.basename(self.root_path)
            page_id = repo_name.lower().replace(' ', '_').replace('/', '_')
            sections_file = os.path.join(self.cache.diagrams_dir, f"{page_id}_sections.json")
            
            # Create new section metadata
            new_section = {
                "section_id": result['section_id'],
                "section_title": result['section_title'],
                "section_description": result.get('section_description', result['section_title']),
                "diagram_type": result['diagram'].get('diagram_type', 'flowchart'),
                "key_concepts": []
            }
            
            # Load existing sections or create new file
            if os.path.exists(sections_file):
                with open(sections_file, 'r', encoding='utf-8') as f:
                    sections_data = json.load(f)
            else:
                sections_data = {
                    "status": "success",
                    "repo_name": repo_name,
                    "language": "en",
                    "sections": [],
                    "cached": False
                }
            
            # Check if this custom section already exists
            sections = sections_data.get('sections', [])
            existing_ids = [s['section_id'] for s in sections]
            
            if new_section['section_id'] not in existing_ids:
                sections.append(new_section)
                sections_data['sections'] = sections
                
                # Save updated sections
                with open(sections_file, 'w', encoding='utf-8') as f:
                    json.dump(sections_data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"✅ Added custom section to cache: {new_section['section_id']}")
            else:
                logger.info(f"ℹ️  Custom section already in cache: {new_section['section_id']}")
                
        except Exception as e:
            logger.error(f"Failed to add custom section to cache: {e}", exc_info=True)

