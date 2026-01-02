"""
Wiki RAG query utilities.

This module handles dual-RAG queries that combine wiki database (generated diagrams)
with codebase database (source code) for comprehensive answers.
"""

import os
import logging
from typing import Dict, List
from adalflow.core.db import LocalDB
from adalflow.core.types import ModelType, Document
from const.const import Const, get_llm_client
from const.prompts import build_wiki_question_prompt

logger = logging.getLogger(__name__)


class WikiRAGQuery:
    """Handles RAG queries for wiki content."""
    
    def __init__(self, wiki_db_path: str, rag_instance):
        """
        Initialize wiki RAG query handler.
        
        Args:
            wiki_db_path: Path to wiki database file
            rag_instance: Initialized RAG instance for codebase queries
        """
        self.wiki_db_path = wiki_db_path
        self.rag = rag_instance
    
    def query_wiki_rag(self, query: str, top_k: int = 5) -> Dict:
        """
        Query both wiki and codebase RAG for comprehensive answers.
        
        This queries BOTH:
        1. Wiki database (generated diagrams and explanations)
        2. Codebase database (actual source code)
        
        Combining both sources prevents information loss and provides complete answers.
        
        Args:
            query: User's question about the wiki
            top_k: Number of results to retrieve from each source
        
        Returns:
            Dict with answer combining both wiki and codebase context
        """
        # Check if wiki database exists
        if not os.path.exists(self.wiki_db_path):
            return {
                "status": "error",
                "error": "No wiki content has been generated yet. Generate diagrams first using /identifyDiagramSections and /generateSectionDiagram.",
                "wiki_db_path": self.wiki_db_path
            }
        
        # Load wiki database
        wiki_db = LocalDB.load_state(filepath=self.wiki_db_path)
        
        try:
            wiki_docs = wiki_db.get_transformed_data(key="wiki_content")
        except (ValueError, KeyError):
            wiki_docs = []
        
        if wiki_docs is None:
            wiki_docs = []
        
        if not wiki_docs:
            return {
                "status": "error",
                "error": "Wiki database is empty. Generate some diagrams first.",
                "wiki_db_path": self.wiki_db_path
            }
        
        logger.info(f"Querying wiki RAG with {len(wiki_docs)} wiki documents")
        
        # 1. Retrieve from wiki database (simple keyword matching)
        wiki_retrieved_docs = self._retrieve_wiki_docs(query, wiki_docs, top_k)
        
        # Build wiki context
        wiki_context = self._build_wiki_context(wiki_retrieved_docs)
        
        # 2. Retrieve from codebase RAG using the full RAG system
        codebase_docs, codebase_context = self._retrieve_codebase_docs(query, top_k)
        
        # 3. Generate answer using BOTH contexts
        answer = self._generate_answer(query, wiki_context, codebase_context)
        
        # Format sources from both wiki and codebase
        sources = self._format_sources(wiki_retrieved_docs, codebase_docs, top_k)
        
        return {
            "status": "success",
            "query": query,
            "answer": answer,
            "sources": sources,
            "wiki_doc_count": len(wiki_docs),
            "wiki_retrieved": len(wiki_retrieved_docs),
            "codebase_retrieved": len(codebase_docs[:top_k])
        }
    
    def _retrieve_wiki_docs(self, query: str, wiki_docs: List[Document], top_k: int) -> List[Document]:
        """Retrieve relevant wiki documents using simple keyword matching."""
        query_lower = query.lower()
        scored_wiki_docs = []
        
        for doc in wiki_docs:
            score = 0
            doc_text_lower = doc.text.lower()
            
            # Simple keyword scoring
            for word in query_lower.split():
                if len(word) > 3:  # Skip short words
                    score += doc_text_lower.count(word)
            
            if score > 0:
                scored_wiki_docs.append((score, doc))
        
        # Sort by score and get top_k
        scored_wiki_docs.sort(reverse=True, key=lambda x: x[0])
        return [doc for score, doc in scored_wiki_docs[:top_k]]
    
    def _build_wiki_context(self, wiki_docs: List[Document]) -> str:
        """Build context string from wiki documents."""
        if not wiki_docs:
            return "No relevant wiki content found."
        
        return "\n\n".join([
            f"[{doc.meta_data.get('content_type', 'unknown')} - {doc.meta_data.get('content_id', 'unknown')}]\n{doc.text}"
            for doc in wiki_docs
        ])
    
    def _retrieve_codebase_docs(self, query: str, top_k: int) -> tuple:
        """Retrieve relevant codebase documents using RAG."""
        try:
            # RAG.call() returns (RAGAnswer, List[Document])
            rag_answer, codebase_docs = self.rag.call(
                query=query,
                top_k=top_k,
                use_reranking=True
            )
            
            # Build codebase context
            codebase_context = "\n\n".join([
                f"[{doc.meta_data.get('file_path', 'unknown') if hasattr(doc, 'meta_data') else 'unknown'}]\n{doc.text[:500]}"
                for doc in codebase_docs[:top_k]
            ]) if codebase_docs else "No relevant codebase snippets found."
            
            return codebase_docs, codebase_context
            
        except Exception as e:
            logger.warning(f"Failed to query codebase RAG: {e}")
            return [], "Codebase context unavailable."
    
    def _generate_answer(self, query: str, wiki_context: str, codebase_context: str) -> str:
        """Generate answer using both wiki and codebase contexts."""
        prompt = build_wiki_question_prompt(
            question=query,
            wiki_context=wiki_context,
            codebase_context=codebase_context
        )
        
        # Use get_llm_client() for proper timeout configuration
        model = get_llm_client()
        model_kwargs = {
            "model": Const.GENERATION_MODEL,
            "options": {"temperature": 0.7},
            "keep_alive": Const.OLLAMA_KEEP_ALIVE
        }
        
        api_kwargs = model.convert_inputs_to_api_kwargs(
            input=prompt,
            model_kwargs=model_kwargs,
            model_type=ModelType.LLM
        )
        
        response = model.call(api_kwargs=api_kwargs, model_type=ModelType.LLM)
        
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            return response.message.content
        else:
            return str(response)
    
    def _format_sources(self, wiki_docs: List[Document], codebase_docs: List[Document], top_k: int) -> Dict:
        """Format sources from both wiki and codebase."""
        sources = {
            "wiki": [],
            "codebase": []
        }
        
        for i, doc in enumerate(wiki_docs, 1):
            sources["wiki"].append({
                "rank": i,
                "content_type": doc.meta_data.get('content_type', 'unknown'),
                "content_id": doc.meta_data.get('content_id', 'unknown'),
                "section_id": doc.meta_data.get('section_id', ''),
                "text_preview": doc.text[:200] + "..." if len(doc.text) > 200 else doc.text
            })
        
        for i, doc in enumerate(codebase_docs[:top_k], 1):
            file_path = doc.meta_data.get('file_path', 'unknown') if hasattr(doc, 'meta_data') else 'unknown'
            sources["codebase"].append({
                "rank": i,
                "file_path": file_path,
                "text_preview": doc.text[:200] + "..." if len(doc.text) > 200 else doc.text
            })
        
        return sources
