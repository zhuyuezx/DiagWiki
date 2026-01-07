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
    build_diagram_sections_prompt_iteration1,
    build_diagram_sections_prompt_iteration2,
    build_diagram_sections_prompt_iteration3,
    build_single_diagram_prompt,
    build_section_rag_query
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
        
        Uses 3-iteration approach:
        1. Rough section identification from RAG context
        2. Refinement with detailed code files
        3. File assignment to each section
        
        This is for a DIAGRAM-FIRST WIKI - diagrams ARE the content, not supplements.
        Analyzes the codebase and identifies diagram sections that together explain it.
        The number of sections is determined by the LLM based on codebase complexity.
        
        Args:
            language: Target language code
            use_cache: Whether to use cached sections if available
        
        Returns:
            Dict with status and identified sections list (with file_references)
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
                    
                    # Validate cached sections
                    if 'sections' in cached_data:
                        valid_sections = []
                        invalid_count = 0
                        for section in cached_data['sections']:
                            if self._validate_section(section, "cached data"):
                                valid_sections.append(section)
                            else:
                                invalid_count += 1
                        
                        if invalid_count > 0:
                            logger.warning(f"⚠️  Found {invalid_count} invalid sections in cache, keeping {len(valid_sections)} valid ones")
                            cached_data['sections'] = valid_sections
                    
                    cached_data['cached'] = True
                    cached_data['cache_file'] = cache_file
                    return cached_data
        
        # Ensure RAG is initialized
        if self.rag is None:
            raise RuntimeError("RAG not initialized. Call initialize_rag() first.")
        
        # ==================== ITERATION 1: ROUGH SECTION IDENTIFICATION ====================
        logger.info("🎯 ITERATION 1: Identifying rough sections from RAG context...")
        
        # Generate RAG queries
        rag_queries = build_page_analysis_queries(repo_name, "Identify key components and workflows suitable for diagrammatic representation.")
        
        # Perform RAG queries
        logger.info(f"Performing {len(rag_queries)} RAG queries for: {repo_name}")
        rag_results = []
        all_retrieved_docs = []
        
        for query in rag_queries:
            try:
                answer, retrieved_docs = self.rag.call(
                    query=query,
                    top_k=Const.RAG_SECTION_ITERATION_TOP_K,  # Use higher top_k for section identification
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
        
        # Build RAG context (rationale and content only, no raw code)
        rag_context = "\n\n".join([
            f"Query: {r['query']}\nAnswer: {r['answer']}\nRationale: {r['rationale']}"
            for r in rag_results
        ])
        
        # Call iteration 1
        iteration1_prompt = build_diagram_sections_prompt_iteration1(
            repo_name=repo_name,
            rag_context=rag_context,
            language=language
        )
        
        rough_sections = self._call_llm_for_sections(iteration1_prompt, "iteration 1")
        if not rough_sections:
            logger.error("Iteration 1 failed to identify sections")
            return {"status": "error", "error": "Failed to identify rough sections"}
        
        logger.info(f"Iteration 1 complete: {len(rough_sections)} rough sections identified")
        
        # ==================== ITERATION 2: REFINE WITH CODE FILES ====================
        logger.info("🎯 ITERATION 2: Refining sections with detailed code files...")
        
        # Do additional comprehensive RAG query specifically for iteration 2
        # This gives the LLM access to more source code for better refinement
        comprehensive_query = f"Provide a comprehensive overview of the {repo_name} codebase structure, main components, architecture, and key files."
        try:
            logger.info(f"Performing comprehensive RAG query for iteration 2 with top_k={Const.RAG_SECTION_ITERATION_TOP_K}")
            answer, comprehensive_docs = self.rag.call(
                query=comprehensive_query,
                top_k=Const.RAG_SECTION_ITERATION_TOP_K,  # Higher top_k for comprehensive view
                use_reranking=True
            )
            all_retrieved_docs.extend(comprehensive_docs)
            logger.info(f"Comprehensive RAG query retrieved {len(comprehensive_docs)} additional documents")
        except Exception as e:
            logger.warning(f"Comprehensive RAG query failed: {e}")
        
        # Extract unique file paths and collect code snippets
        code_files_map = {}
        for doc in all_retrieved_docs:
            if hasattr(doc, 'meta_data'):
                file_path = doc.meta_data.get('file_path', '')
                if file_path and file_path not in code_files_map:
                    # Get text content with longer preview for better understanding
                    doc_text = doc.text if hasattr(doc, 'text') else str(doc)
                    code_files_map[file_path] = doc_text[:1000]  # Increased to 1000 chars
        
        logger.info(f"Collected {len(code_files_map)} unique code files for iteration 2")
        
        # Format code files content - include more files (top 40)
        code_files_content = "\n\n".join([
            f"File: {path}\n{content}..."
            for path, content in list(code_files_map.items())[:40]  # Increased to top 40 files
        ])
        
        # Call iteration 2
        iteration2_prompt = build_diagram_sections_prompt_iteration2(
            repo_name=repo_name,
            rough_sections=rough_sections,
            code_files_content=code_files_content,
            language=language
        )
        
        iteration2_response = self._call_llm_for_sections(iteration2_prompt, "iteration 2", return_full=True)
        if not iteration2_response or 'sections' not in iteration2_response:
            logger.error("Iteration 2 failed to refine sections")
            return {"status": "error", "error": "Failed to refine sections"}
        
        refined_sections = iteration2_response['sections']
        refinement_notes = iteration2_response.get('refinement_notes', '')
        
        logger.info(f"Iteration 2 complete: {len(refined_sections)} refined sections")
        if refinement_notes:
            logger.info(f"Refinement notes: {refinement_notes[:200]}...")
        
        # ==================== ITERATION 3: ASSIGN FILES TO SECTIONS ====================
        logger.info("🎯 ITERATION 3: Assigning code files to sections...")
        
        # Get all available file paths
        all_code_files = list(code_files_map.keys())
        
        # Call iteration 3
        iteration3_prompt = build_diagram_sections_prompt_iteration3(
            repo_name=repo_name,
            refined_sections=refined_sections,
            all_code_files=all_code_files,
            language=language
        )
        
        final_response = self._call_llm_for_sections(iteration3_prompt, "iteration 3", return_full=True)
        if not final_response or 'sections' not in final_response:
            logger.error("Iteration 3 failed to assign files")
            return {"status": "error", "error": "Failed to assign files to sections"}
        
        final_sections = final_response['sections']
        
        logger.info(f"Iteration 3 complete: {len(final_sections)} final sections with file assignments")
        
        # Cache the result
        cache_file = os.path.join(self.cache.diagrams_dir, f"{page_id}_sections.json")
        
        result = {
            "status": "success",
            "repo_name": repo_name,
            "language": language,
            "sections": final_sections,
            "rag_queries_performed": len(rag_queries),
            "iteration_notes": {
                "iteration1_count": len(rough_sections),
                "iteration2_count": len(refined_sections),
                "iteration3_count": len(final_sections),
                "refinement_notes": refinement_notes
            },
            "cached": False,
            "cache_file": cache_file
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Cached sections to: {cache_file}")
        
        return result
    
    def _validate_section(self, section: Dict, iteration_name: str) -> bool:
        """Validate that a section has all required fields.
        
        Args:
            section: Section dictionary to validate
            iteration_name: Name of iteration for logging
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['section_id', 'section_title', 'section_description', 'diagram_type']
        
        for field in required_fields:
            if field not in section or not section[field]:
                logger.warning(f"❌ {iteration_name}: Section missing required field '{field}': {section.get('section_id', 'unknown')}")
                return False
        
        # Validate diagram_type is valid
        valid_types = ['flowchart', 'sequence', 'class', 'stateDiagram', 'erDiagram']
        if section['diagram_type'] not in valid_types:
            logger.warning(f"❌ {iteration_name}: Invalid diagram_type '{section['diagram_type']}' for section {section['section_id']}")
            return False
            
        return True
    
    def _call_llm_for_sections(self, prompt: str, iteration_name: str, return_full: bool = False) -> any:
        """Helper method to call LLM for section identification iterations."""
        model = get_llm_client()
        model_kwargs = {
            "model": Const.GENERATION_MODEL,
            "format": "json",
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
        
        response = model.call(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        
        # Extract content
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            sections_json = response.message.content
        else:
            sections_json = str(response)
        
        try:
            sections_data = json.loads(sections_json)
            
            # Validate sections if present
            if 'sections' in sections_data:
                valid_sections = []
                invalid_count = 0
                
                for section in sections_data['sections']:
                    if self._validate_section(section, iteration_name):
                        valid_sections.append(section)
                    else:
                        invalid_count += 1
                
                if invalid_count > 0:
                    logger.warning(f"⚠️  {iteration_name}: Filtered out {invalid_count} invalid sections, kept {len(valid_sections)} valid ones")
                
                # If ALL sections are invalid, return error
                if len(valid_sections) == 0 and len(sections_data['sections']) > 0:
                    logger.error(f"❌ {iteration_name}: All {len(sections_data['sections'])} sections were invalid!")
                    return None if return_full else []
                
                sections_data['sections'] = valid_sections
            
            if return_full:
                return sections_data
            else:
                return sections_data.get('sections', [])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {iteration_name} JSON: {e}")
            logger.error(f"Raw response: {sections_json[:500]}...")
            return None if return_full else []
    
    def generate_section_diagram(
        self,
        section_id: str,
        section_title: str,
        section_description: str,
        diagram_type: str,
        key_concepts: List[str] = None,
        file_references: str = None,
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
            key_concepts: (Optional) List of key concepts to include (legacy format)
            file_references: (Optional) Detailed file analysis string (new format from iteration 3)
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
            # Automatic mode: use RAG with full context
            repo_name = os.path.basename(self.root_path)
            rag_context, retrieved_sources, all_retrieved_docs = self._perform_section_rag_queries(
                repo_name=repo_name,
                section_title=section_title,
                section_description=section_description,
                key_concepts=key_concepts,
                file_references=file_references,
                diagram_type=diagram_type
            )
        
        # Build diagram prompt
        logger.info(f"Generating diagram for: {section_title}")
        diagram_prompt = build_single_diagram_prompt(
            section_title=section_title,
            section_description=section_description,
            diagram_type=diagram_type,
            key_concepts=key_concepts,
            file_references=file_references,
            rag_context=rag_context,
            retrieved_sources=retrieved_sources,
            language=language
        )
        
        # Call LLM for diagram
        diagram_data = self._generate_diagram_with_llm(diagram_prompt)
        
        # Aggregate source files by filename with segments
        from utils.wiki_generator import _aggregate_sources_by_file
        source_files = _aggregate_sources_by_file(
            all_retrieved_docs,
            self.root_path,
            f"Used to generate {section_title}"
        )
        logger.info(f"Aggregated {len(source_files)} source files from {len(all_retrieved_docs)} chunks")
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
    
    def fix_corrupted_diagram(
        self,
        section_id: str,
        section_title: str,
        section_description: str,
        diagram_type: str,
        key_concepts: List[str] = None,
        file_references: str = None,
        language: str = "en",
        corrupted_diagram: str = "",
        error_message: str = ""
    ) -> Dict:
        """
        Fix a corrupted Mermaid diagram that failed to render.
        
        This method regenerates the diagram with explicit error correction context.
        It does NOT use cache since we're fixing a broken diagram.
        
        Args:
            section_id: Section ID
            section_title: Title of the section
            section_description: Description of the section
            diagram_type: Type of diagram
            key_concepts: (Optional) List of key concepts (legacy format)
            file_references: (Optional) Detailed file analysis string (new format from iteration 3)
            language: Language code
            corrupted_diagram: The corrupted Mermaid code
            error_message: The error message from Mermaid renderer
        
        Returns:
            Dict with corrected diagram
        """
        logger.info(f"Fixing corrupted diagram for: {section_title}")
        logger.info(f"Mermaid error: {error_message[:200]}...")
        
        # Ensure RAG is initialized
        if self.rag is None:
            raise RuntimeError("RAG not initialized. Call initialize_rag() first.")
        
        # Perform RAG queries with full context (same as normal generation)
        repo_name = os.path.basename(self.root_path)
        rag_context, retrieved_sources, all_retrieved_docs = self._perform_section_rag_queries(
            repo_name=repo_name,
            section_title=section_title,
            section_description=section_description,
            key_concepts=key_concepts,
            file_references=file_references,
            diagram_type=diagram_type
        )
        
        # Build error correction prompt
        from const.prompts import build_diagram_correction_prompt
        correction_prompt = build_diagram_correction_prompt(
            section_title=section_title,
            section_description=section_description,
            diagram_type=diagram_type,
            key_concepts=key_concepts,
            file_references=file_references,
            rag_context=rag_context,
            retrieved_sources=retrieved_sources,
            corrupted_diagram=corrupted_diagram,
            error_message=error_message,
            language=language
        )
        
        # Call LLM to fix the diagram
        diagram_data = self._generate_diagram_with_llm(correction_prompt)
        
        # Aggregate source files by filename with segments
        from utils.wiki_generator import _aggregate_sources_by_file
        source_files = _aggregate_sources_by_file(
            all_retrieved_docs,
            self.root_path,
            f"Used to fix {section_title}"
        )
        
        # Process the corrected diagram
        result = self._process_diagram_response(
            diagram_data,
            section_id,
            section_title,
            section_description,
            language,
            len(rag_context.split('\n\n')),
            source_files
        )
        
        # Cache the corrected diagram if successful
        if result.get("status") == "success":
            self._cache_diagram_result(result)
            logger.info(f"✅ Successfully fixed and cached diagram for: {section_title}")
        
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
                "temperature": Const.FOCUSED_TEMPERATURE,
                "num_ctx": Const.LARGE_CONTEXT_WINDOW
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
    
    def _perform_section_rag_queries(
        self,
        repo_name: str,
        section_title: str,
        section_description: str,
        key_concepts: list = None,
        file_references: str = None,
        diagram_type: str = "flowchart"
    ) -> tuple:
        """Perform RAG queries for a specific section.
        
        Uses a comprehensive query built with project context, section details,
        and diagram-type-specific hints to retrieve the most relevant code.
        
        Args:
            repo_name: Name of the repository/project
            section_title: Title of the section being generated
            section_description: Detailed description of what the section covers
            key_concepts: (Optional) List of key concepts that should be included (legacy)
            file_references: (Optional) Detailed file analysis string (new format from iteration 3)
            diagram_type: Type of diagram being generated (flowchart, sequence, etc.)
        
        Returns:
            Tuple of (rag_context, retrieved_sources, all_retrieved_docs)
        """
        # Build comprehensive RAG query with full context
        comprehensive_query = build_section_rag_query(
            repo_name=repo_name,
            section_title=section_title,
            section_description=section_description,
            key_concepts=key_concepts,
            file_references=file_references,
            diagram_type=diagram_type
        )
        
        logger.info(f"RAG query for '{section_title}': {comprehensive_query[:100]}...")
        rag_results = []
        all_retrieved_docs = []
        
        try:
            answer, retrieved_docs = self.rag.call(
                query=comprehensive_query,
                top_k=Const.RAG_TOP_K,
                use_reranking=True
            )
            # Validate answer is not None
            if answer is None:
                logger.warning(f"RAG query returned None for '{comprehensive_query[:50]}...'")
            else:
                rag_results.append({
                    "query": comprehensive_query,
                    "answer": answer.answer if hasattr(answer, 'answer') else str(answer),
                    "rationale": answer.rationale if hasattr(answer, 'rationale') else ""
                })
                all_retrieved_docs.extend(retrieved_docs)
                logger.info(f"✅ Retrieved {len(retrieved_docs)} unique files for: {section_title}")
        except Exception as e:
            logger.warning(f"RAG query failed for '{comprehensive_query[:50]}...': {e}")
        
        # Build RAG context
        rag_context_parts = []
        current_length = 0
        
        for r in rag_results:
            part = f"Query: {r['query']}\nAnswer: {r['answer']}\nRationale: {r['rationale']}"
            part_length = len(part)
            
            if current_length + part_length > Const.MAX_RAG_CONTEXT_CHARS:
                # Truncate last part to fit
                remaining = Const.MAX_RAG_CONTEXT_CHARS - current_length
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
        retrieved_sources = "\n\n".join([
            f"Source {i+1} ({doc.meta_data.get('file_path', 'unknown') if hasattr(doc, 'meta_data') else 'unknown'}):\n{doc.text[:Const.SOURCE_PREVIEW_LENGTH]}"
            for i, doc in enumerate(unique_docs[:Const.MAX_SOURCES])
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
                if len(content) > Const.MAX_FILE_CHARS:
                    content = content[:Const.MAX_FILE_CHARS] + "\n\n[... truncated for size limits ...]"
                
                # Create mock document
                doc = Document(
                    text=content,
                    meta_data={"file_path": file_path}
                )
                all_docs.append(doc)
                
                # Add to context
                rag_context_parts.append(f"File: {file_path}\n{content}")
                
                # Add to sources (with preview)
                retrieved_sources_parts.append(
                    f"Source {i+1} ({file_path}):\n{content[:Const.SOURCE_PREVIEW_LENGTH]}"
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
                "temperature": Const.DEFAULT_TEMPERATURE,
                "num_ctx": Const.LARGE_CONTEXT_WINDOW
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
            
            # Strip markdown code fences if present (LLM sometimes adds them despite instructions)
            mermaid_code = mermaid_code.strip()
            if mermaid_code.startswith('```'):
                # Remove opening fence (e.g., ```mermaid or ```mermaid.erDiagram or just ```)
                lines = mermaid_code.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]  # Skip first line
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]  # Skip last line
                mermaid_code = '\n'.join(lines).strip()
            
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
            if self._is_custom_section(result.get('section_id', '')):
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
    
    def _is_custom_section(self, section_id: str) -> bool:
        """Check if a section is custom (not from /identifyDiagramSections).
        
        A section is custom if:
        1. It starts with 'custom_' (legacy format), OR
        2. It doesn't exist in the sections cache file from /identifyDiagramSections
        
        Returns:
            True if section is custom, False if it's a predefined section
        """
        # Legacy check: old custom sections used custom_ prefix
        if section_id.startswith('custom_'):
            return True
        
        # Check if section exists in the cached sections from /identifyDiagramSections
        try:
            repo_name = os.path.basename(self.root_path)
            page_id = repo_name.lower().replace(' ', '_').replace('/', '_')
            sections_file = os.path.join(self.cache.diagrams_dir, f"{page_id}_sections.json")
            
            if not os.path.exists(sections_file):
                # No sections file exists yet, so this is definitely custom
                return True
            
            with open(sections_file, 'r', encoding='utf-8') as f:
                sections_data = json.load(f)
            
            sections = sections_data.get('sections', [])
            existing_ids = [s['section_id'] for s in sections]
            
            # If section_id not in predefined sections, it's custom
            return section_id not in existing_ids
            
        except Exception as e:
            logger.warning(f"Error checking if section is custom: {e}")
            # On error, assume it's custom to be safe
            return True

