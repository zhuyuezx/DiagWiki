"""
Prompt templates for LLM interactions.

This module contains all prompt templates used for:
- Wiki structure generation
- Wiki page generation
- RAG queries
- Interactive diagram generation
"""

import json
from typing import Optional, Dict

# JSON Schemas for structured output enforcement

DIAGRAM_SECTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section_id": {
                        "type": "string",
                        "description": "Unique identifier for the section (lowercase, hyphenated)"
                    },
                    "section_title": {
                        "type": "string",
                        "description": "Clear, concise title for the section"
                    },
                    "section_description": {
                        "type": "string",
                        "description": "What this section explains (2-3 sentences)"
                    },
                    "diagram_type": {
                        "type": "string",
                        "enum": ["flowchart", "sequence", "class", "stateDiagram", "erDiagram"],
                        "description": "Type of Mermaid diagram"
                    },
                    "key_concepts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key concepts to include in the diagram"
                    },
                    "importance": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Importance level of this section"
                    }
                },
                "required": ["section_id", "section_title", "section_description", "diagram_type", "key_concepts", "importance"]
            }
        }
    },
    "required": ["sections"]
}

SINGLE_DIAGRAM_SCHEMA = {
    "type": "object",
    "properties": {
        "mermaid_code": {
            "type": "string",
            "description": "Complete Mermaid diagram code with proper syntax"
        },
        "diagram_description": {
            "type": "string",
            "description": "Brief 2-3 sentence explanation of what this diagram shows"
        },
        "node_explanations": {
            "type": "object",
            "description": "Map of node IDs to their explanations",
            "additionalProperties": {
                "type": "string"
            }
        },
        "edge_explanations": {
            "type": "object",
            "description": "Map of edge keys (Source->Target) to their explanations",
            "additionalProperties": {
                "type": "string"
            }
        }
    },
    "required": ["mermaid_code", "diagram_description", "node_explanations", "edge_explanations"]
}


def get_language_name(language_code: str) -> str:
    """Get full language name from language code."""
    language_names = {
        'en': 'English',
        'ja': 'Japanese (日本語)',
        'zh': 'Mandarin Chinese (中文)',
        'es': 'Spanish (Español)',
        'kr': 'Korean (한국어)',
        'vi': 'Vietnamese (Tiếng Việt)',
        'pt': 'Portuguese (Português)',
        'fr': 'Français (French)',
        'ru': 'Русский (Russian)'
    }
    return language_names.get(language_code, 'English')


def build_wiki_structure_prompt(
    folder_name: str,
    file_tree: str,
    readme_content: str,
    rag_insights: list,
    language: str,
    comprehensive: bool
) -> str:
    """
    Build prompt for wiki structure generation.
    
    Args:
        folder_name: Name of the folder/project
        file_tree: Complete file tree structure
        readme_content: README file content
        rag_insights: List of RAG analysis insights
        language: Target language code
        comprehensive: Whether to create comprehensive wiki
    
    Returns:
        Complete prompt string
    """
    language_name = get_language_name(language)
    
    # Build RAG insights section
    rag_insights_text = ""
    if rag_insights:
        rag_insights_text = "\n\n3. Codebase Analysis (from RAG retrieval):\n<rag_analysis>\n"
        for idx, insight in enumerate(rag_insights, 1):
            rag_insights_text += f"\nQuestion {idx}: {insight['query']}\n"
            rag_insights_text += f"Answer: {insight['answer']}\n"
            if insight.get('sources'):
                rag_insights_text += "Key code snippets:\n"
                for src in insight['sources']:
                    rag_insights_text += f"- {src}\n"
        rag_insights_text += "</rag_analysis>"
    
    # Determine structure format and page count
    if comprehensive:
        structure_instructions = """
Create a structured wiki with the following main sections:
- Overview (general information about the project)
- System Architecture (how the system is designed)
- Core Features (key functionality)
- Data Management/Flow: If applicable, how data is stored, processed, accessed, and managed
- Frontend Components (UI elements, if applicable)
- Backend Systems (server-side components)
- Model Integration (AI model connections, if applicable)
- Deployment/Infrastructure (how to deploy, infrastructure)
- Extensibility and Customization: If supported, explain how to extend or customize

Each section should contain relevant pages. Return XML with sections and pages.

<wiki_structure>
  <title>[Overall title for the wiki]</title>
  <description>[Brief description of the repository]</description>
  <sections>
    <section id="section-1">
      <title>[Section title]</title>
      <pages>
        <page_ref>page-1</page_ref>
        <page_ref>page-2</page_ref>
      </pages>
      <subsections>
        <section_ref>section-2</section_ref>
      </subsections>
    </section>
  </sections>
  <pages>
    <page id="page-1">
      <title>[Page title]</title>
      <description>[Brief description]</description>
      <importance>high|medium|low</importance>
      <relevant_files>
        <file_path>[Path to relevant file]</file_path>
      </relevant_files>
      <related_pages>
        <related>page-2</related>
      </related_pages>
      <parent_section>section-1</parent_section>
    </page>
  </pages>
</wiki_structure>"""
        page_count = "8-12"
    else:
        structure_instructions = """
Return your analysis in the following XML format:

<wiki_structure>
  <title>[Overall title for the wiki]</title>
  <description>[Brief description of the repository]</description>
  <pages>
    <page id="page-1">
      <title>[Page title]</title>
      <description>[Brief description]</description>
      <importance>high|medium|low</importance>
      <relevant_files>
        <file_path>[Path to relevant file]</file_path>
      </relevant_files>
      <related_pages>
        <related>page-2</related>
      </related_pages>
    </page>
  </pages>
</wiki_structure>"""
        page_count = "4-6"
    
    prompt = f"""Analyze this folder {folder_name} and create a wiki structure for it.

1. The complete file tree of the project:
<file_tree>
{file_tree}
</file_tree>

2. The README file of the project:
<readme>
{readme_content if readme_content else "No README found"}
</readme>{rag_insights_text}

I want to create a wiki for this codebase. Determine the most logical structure for a wiki based on the content.

IMPORTANT: Use the RAG analysis insights above to understand the codebase's actual components, architecture, and features. The relevant_files in your structure should reference the actual source files mentioned in the RAG analysis.

IMPORTANT: The wiki content will be generated in {language_name} language.

When designing the wiki structure, include pages that would benefit from visual diagrams, such as:
- Architecture overviews
- Data flow descriptions
- Component relationships
- Process workflows
- State machines
- Class hierarchies

{structure_instructions}

IMPORTANT FORMATTING INSTRUCTIONS:
- Return ONLY the valid XML structure specified above
- DO NOT wrap the XML in markdown code blocks (no ``` or ```xml)
- DO NOT include any explanation text before or after the XML
- Ensure the XML is properly formatted and valid
- Start directly with <wiki_structure> and end with </wiki_structure>

IMPORTANT:
1. Create {page_count} pages that would make a {'comprehensive' if comprehensive else 'concise'} wiki for this codebase
2. Each page should focus on a specific aspect (e.g., architecture, key features, setup)
3. The relevant_files should be actual files from the codebase that would be used to generate that page
4. Return ONLY valid XML with the structure specified above, with no markdown code block delimiters"""
    
    return prompt


def build_wiki_page_prompt(
    page_title: str,
    page_description: str,
    rag_context: str,
    retrieved_sources: str,
    file_contents: list,
    unique_docs: list,
    language: str
) -> str:
    """
    Build prompt for wiki page generation.
    
    Args:
        page_title: Title of the page
        page_description: Description of what the page should cover
        rag_context: RAG-retrieved context (answers + rationales)
        retrieved_sources: Retrieved source code snippets
        file_contents: List of explicit file contents
        unique_docs: List of unique documents for citation
        language: Target language code
    
    Returns:
        Complete prompt string
    """
    language_name = get_language_name(language)
    
    file_list = '\n'.join([f"- {fc['path']}" for fc in file_contents]) if file_contents else "(Retrieved via RAG)"
    
    prompt = f"""You are an expert technical writer and software architect.
Your task is to generate a comprehensive and accurate technical wiki page in Markdown format.

TOPIC: {page_title}
DESCRIPTION: {page_description}

=== RAG-RETRIEVED CONTEXT (Primary Source) ===

The following information was retrieved using semantic search and hybrid ranking (BM25+RRF) from the codebase:

{rag_context}

=== RETRIEVED SOURCE CODE SNIPPETS ===

{retrieved_sources}

=== ADDITIONAL EXPLICIT FILES ===
{file_list}

CRITICAL STARTING INSTRUCTION:
The very first thing on the page MUST be a <details> block listing the relevant source files.
Format it exactly like this:
<details>
<summary>Relevant source files</summary>

The following files were used as context (retrieved via RAG and hybrid ranking):

{chr(10).join([f"- {doc.meta_data.get('file_path', 'unknown')}" for doc in unique_docs[:10] if hasattr(doc, 'meta_data')])}
</details>

Immediately after the <details> block, the main title should be: # {page_title}

Based on the RAG-retrieved context and source code snippets above:

1. **Introduction:** Start with 1-2 paragraphs explaining the purpose and overview.

2. **Detailed Sections:** Break down into logical sections using ## and ### headings:
   - Explain architecture, components, data flow, logic
   - Identify key functions, classes, APIs, configurations

3. **Mermaid Diagrams:**
   - EXTENSIVELY use Mermaid diagrams (flowchart TD, sequenceDiagram, classDiagram, etc.)
   - All diagrams MUST use vertical orientation
   - For sequence diagrams:
     * Define participants at beginning
     * Use ->> for solid arrow (requests/calls)
     * Use -->> for dotted arrow (responses/returns)
     * Use activation boxes with +/- suffix
     * Use structural elements: loop, alt/else, opt, par, critical, break
   - Provide brief explanation before/after each diagram

4. **Tables:**
   - Summarize features, components, API parameters, config options, data models

5. **Code Snippets (optional):**
   - Include short relevant snippets from source files
   - Well-formatted with language identifiers

6. **Source Citations (CRITICAL):**
   - For EVERY significant piece of information, cite the source file from RAG results
   - Format: Sources: [filename.ext]() (line numbers may not be available from RAG)
   - Reference the retrieved sources provided above
   - Multiple files: Sources: [file1.ext](), [file2.ext]()

7. **Technical Accuracy:** All information must be from RAG-retrieved context and source code snippets only.

8. **Clarity:** Use clear, professional, concise technical language.

9. **Conclusion:** End with brief summary if appropriate.

IMPORTANT: Generate the content in {language_name} language.
"""
    
    # Add any explicit file contents if provided
    if file_contents:
        prompt += "\n\n=== EXPLICIT FILE CONTENTS ===\n"
        for fc in file_contents:
            prompt += f"\n{'='*60}\n"
            prompt += f"File: {fc['path']}\n"
            prompt += f"{'='*60}\n"
            prompt += fc['content']
            prompt += f"\n{'='*60}\n\n"
    
    prompt += """\n\nNow generate the comprehensive wiki page in markdown format.

REMEMBER: Base your content primarily on the RAG-retrieved context and source code snippets provided above. 
These have been intelligently retrieved using semantic search and hybrid ranking (BM25+RRF) to find the most relevant information.
The RAG system has already analyzed the query and found the best matching code sections.

Generate the wiki page now:"""
    
    return prompt


# Analysis queries for wiki structure generation
STRUCTURE_ANALYSIS_QUERIES = [
    "What are the main components, modules, and their purposes in this codebase?",
    "What is the system architecture and how are different parts connected?",
    "What are the key features and core functionality provided?",
    "What APIs, endpoints, or interfaces are exposed?",
    "What data models, schemas, or data structures are used?"
]


# Page generation queries template
def build_page_analysis_queries(page_title: str, page_description: str) -> list:
    """
    Build RAG queries for page content generation.
    
    Args:
        page_title: Title of the page
        page_description: Description of the page
    
    Returns:
        List of query strings with instructions for detailed file/component names
    """
    return [
        f"What is {page_title}? {page_description} Provide specific file names and component names.",
        f"How does {page_title} work? Explain the implementation details. Include specific file paths, class names, function names, and module names.",
        f"What are the key components and functions related to {page_title}? List specific file names (e.g., backend/utils/file.py), class names, and function names.",
        f"What are the data structures, classes, or APIs for {page_title}? Reference specific files and component names.",
        f"Show code examples and usage patterns for {page_title}. Include the source file paths where these examples are found."
    ]


def build_diagram_sections_prompt_iteration1(
    repo_name: str,
    rag_context: str,
    language: str
) -> str:
    """
    Build prompt for ITERATION 1: Identify rough diagram sections from RAG context.
    
    This is the first pass to understand the codebase structure and identify
    major aspects that should be visualized. No detailed file assignments yet.
    
    IMPORTANT: This is for a diagram-first wiki where diagrams ARE the main representation.
    The wiki is composed of interactive diagrams that explain the codebase visually.
    
    Args:
        repo_name: Name of the repository/codebase
        rag_context: RAG-retrieved context (rationale and content only, no raw code)
        language: Target language code
    
    Returns:
        Prompt string for LLM to identify rough diagram sections
    """
    language_name = get_language_name(language)
    
    prompt = f"""You are an expert technical writer creating a DIAGRAM-FIRST wiki for the "{repo_name}" codebase.

🎯 ITERATION 1: ROUGH SECTION IDENTIFICATION

This is the first pass to understand the codebase structure. You will identify major aspects
that should be visualized, without worrying about detailed file assignments yet.

🎯 CRITICAL CONCEPT: This wiki is MADE OF DIAGRAMS. Diagrams are the PRIMARY REPRESENTATION, not supplements.

CODEBASE CONTEXT (from RAG analysis):
{rag_context}

Your task is to identify distinct diagram sections that together provide a complete visual understanding of this codebase.

IMPORTANT GUIDELINES:
1. Analyze the COMPLEXITY and SCOPE to determine appropriate number of diagrams
   - Simple projects (single module, <5 files): 2~3 diagrams
   - Medium projects (multiple modules, 5-20 files): 3~6 diagrams  
   - Complex projects (layered architecture, >20 files): 6~12 diagrams
   - Let the codebase structure guide you - don't force a fixed number

2. Each diagram section represents ONE focused aspect that MUST be visualized
   - System architecture / component relationships / module dependencies → flowchart
   - Data flow / process workflows → flowchart
   - Class hierarchies / inheritance → classDiagram
   - API call sequences / request-response patterns → sequence diagram
   - State machines / lifecycle → stateDiagram
   - Database relationships → erDiagram
   - Interaction patterns between components → sequence or flowchart

3. Each section should be:
   - Self-contained and focused on ONE aspect
   - Fully expressible as a single Mermaid diagram
   - Essential for understanding this codebase

4. 🎯 Use SPECIFIC component/class/function names from the CODEBASE CONTEXT
   - BAD: "API calls between client and server" (too generic)
   - GOOD: "FastAPI requests through WikiGenerator to Ollama LLM" (specific to this codebase)
   - Include actual class names, module names, function names from the context

5. Together, these diagrams should fully explain "{repo_name}" - no additional text needed

Return your analysis in the following JSON format:

{{
  "sections": [
    {{
      "section_id": "unique-identifier",
      "section_title": "Clear, concise title",
      "section_description": "What this section explains, using SPECIFIC component names from the codebase (2-3 sentences)",
      "diagram_type": "flowchart|sequence|class|stateDiagram|erDiagram"
    }}
  ]
}}

NOTE: This is iteration 1 - focus on identifying major sections. File assignments come later.

⚠️ CRITICAL JSON REQUIREMENTS:
1. Return ONLY valid JSON - no markdown code blocks, no extra text
2. ALL fields are REQUIRED: section_id, section_title, section_description, diagram_type
3. Do NOT omit any fields - every section must have all 4 fields
4. Use proper JSON syntax with double quotes and correct commas
5. diagram_type must be one of: flowchart, sequence, class, stateDiagram, erDiagram

Generate the analysis in {language_name} language.

Analyze now:"""
    
    return prompt


def build_diagram_sections_prompt_iteration2(
    repo_name: str,
    rough_sections: list,
    code_files_content: str,
    language: str
) -> str:
    """
    Build prompt for ITERATION 2: Refine sections with detailed code file analysis.
    
    Takes rough sections from iteration 1 and refines them based on actual code files.
    The LLM can merge, split, or reorganize sections based on actual implementation.
    
    Args:
        repo_name: Name of the repository/codebase
        rough_sections: List of rough sections from iteration 1
        code_files_content: Detailed code files filtered through RAG
        language: Target language code
    
    Returns:
        Prompt string for LLM to refine diagram sections
    """
    language_name = get_language_name(language)
    
    # Format rough sections for display
    sections_text = "\n".join([
        f"{i+1}. {s['section_title']} ({s['diagram_type']})\n   {s['section_description']}"
        for i, s in enumerate(rough_sections)
    ])
    
    prompt = f"""You are refining the diagram structure for the "{repo_name}" codebase.

🎯 ITERATION 2: REFINE SECTIONS WITH CODE FILES

In iteration 1, we identified these rough sections:

{sections_text}

Now you have access to COMPREHENSIVE ACTUAL CODE FILES to refine these sections.
This is a large collection of the most relevant code files from the codebase:

{code_files_content}

Your task is to REFINE the sections based on actual implementation:

REFINEMENT GUIDELINES:
1. Review each rough section against the actual code
2. Merge sections if they're too granular or overlapping
3. Split sections if they cover too many disparate concepts
4. If there are important aspects missing when you read source code, ADD new sections
5. Adjust diagram types if the code structure suggests a better visualization
7. Ensure section_id uses kebab-case and reflects actual component names

QUALITY CRITERIA:
- Each section should map cleanly to code structures you see
- Diagram type should match the code patterns (classes→classDiagram, flows→flowchart, etc.)
- Descriptions should reference actual classes/functions/modules from the code
- Always think: "Are these sections enough for a perfect visual interpretation of the codebase?"

Return refined sections in the following JSON format:

{{
  "sections": [
    {{
      "section_id": "specific-identifier-from-code",
      "section_title": "Clear title reflecting actual code",
      "section_description": "What this section explains, referencing actual code components (2-3 sentences)",
      "diagram_type": "flowchart|sequence|class|stateDiagram|erDiagram"
    }}
  ],
  "refinement_notes": "Brief explanation of major changes from iteration 1 (optional)"
}}

⚠️ CRITICAL JSON REQUIREMENTS:
1. Return ONLY valid JSON - no markdown code blocks, no extra text
2. ALL fields are REQUIRED for each section: section_id, section_title, section_description, diagram_type
3. Do NOT omit any fields - every section MUST have all 4 fields
4. Use proper JSON syntax with double quotes and correct commas
5. diagram_type must be one of: flowchart, sequence, class, stateDiagram, erDiagram
Generate the refined analysis in {language_name} language.

Refine now:"""
    
    return prompt


def build_diagram_sections_prompt_iteration3(
    repo_name: str,
    refined_sections: list,
    all_code_files: list,
    language: str
) -> str:
    """
    Build prompt for ITERATION 3: Assign code files to each section.
    
    Takes refined sections from iteration 2 and assigns relevant code files to each.
    One file can be assigned to multiple sections. Adds file_references field.
    
    Args:
        repo_name: Name of the repository/codebase
        refined_sections: List of refined sections from iteration 2
        all_code_files: List of available code file paths with brief descriptions
        language: Target language code
    
    Returns:
        Prompt string for LLM to assign files to sections
    """
    language_name = get_language_name(language)
    
    # Format refined sections for display
    sections_text = "\n".join([
        f"{i+1}. [{s['section_id']}] {s['section_title']} ({s['diagram_type']})\n   {s['section_description']}"
        for i, s in enumerate(refined_sections)
    ])
    
    # Format available files
    files_text = "\n".join([f"- {f}" for f in all_code_files])
    
    prompt = f"""⚠️⚠️⚠️ CRITICAL SECTION COUNT REQUIREMENT ⚠️⚠️⚠️
YOU MUST RETURN EXACTLY {len(refined_sections)} SECTIONS IN YOUR JSON RESPONSE.
DO NOT MERGE, COMBINE, OR OMIT ANY SECTIONS.
THIS IS A STRICT REQUIREMENT - COUNT YOUR SECTIONS BEFORE SUBMITTING!
⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️

You are finalizing the diagram structure for the "{repo_name}" codebase.

🎯 ITERATION 3: ASSIGN CODE FILES TO SECTIONS (DO NOT MODIFY SECTION STRUCTURE!)

INPUT: {len(refined_sections)} refined sections from iteration 2:

{sections_text}

Available code files in the repository:

{files_text}

🚨 YOUR ONLY TASK: Add file_references field to EACH existing section.
   - DO NOT change section_id, section_title, section_description, or diagram_type
   - DO NOT merge similar sections
   - DO NOT consolidate sections
   - DO NOT remove any sections
   - ONLY add file_references field to existing sections

EXPECTED OUTPUT COUNT: {len(refined_sections)} sections
REQUIRED: Each section MUST have EXACTLY these 5 fields:
1. section_id (from iteration 2)
2. section_title (from iteration 2)
3. section_description (from iteration 2)
4. diagram_type (from iteration 2)
5. file_references (NEW - you add this)

ASSIGNMENT GUIDELINES:
1. For each section, identify which code files are relevant for creating that diagram
2. A file can be assigned to MULTIPLE sections if it's relevant to multiple aspects
3. Focus on files that contain the key components/logic for that section
4. For each file assignment, explain the relationship:
   - What key concepts/components does this file provide?
   - How does it connect to other files in this section?
   - Why is it important for this diagram?
5. **PRESERVE ALL SECTIONS**: Return exactly {len(refined_sections)} sections - one for each input section

FILE_REFERENCES FORMAT:
For each section, provide a file_references string that:
- Lists relevant files with brief analysis of their role
- Explains key concepts and connections between files
- Highlights what should be visualized from these files
- Include as much detail & file names for referernce and this would help later RAG queries

Example file_references:
"backend/api.py (defines FastAPI endpoints), backend/utils/wiki_generator.py (core wiki generation logic), backend/utils/rag.py (RAG system integration). These files form the request-response pipeline: API receives requests → WikiGenerator orchestrates → RAG retrieves context. Key concepts: endpoint routing, generation workflow, context retrieval."

🎯 CRITICAL: If input has {len(refined_sections)} sections, output MUST have {len(refined_sections)} sections!

EXAMPLE JSON FORMAT (showing preservation of multiple sections):
If iteration 2 gave you these 3 sections:
1. api-flow → YOU KEEP: api-flow
2. data-pipeline → YOU KEEP: data-pipeline  
3. ui-components → YOU KEEP: ui-components

Your output MUST be:
{{
  "sections": [
    {{
      "section_id": "api-flow",
      "section_title": "API Request Flow",
      "section_description": "How requests are processed",
      "diagram_type": "sequence",
      "file_references": "backend/api.py (endpoints), utils/handler.py (processing)..."
    }},
    {{
      "section_id": "data-pipeline",
      "section_title": "Data Processing Pipeline",
      "section_description": "How data flows through system",
      "diagram_type": "flowchart",
      "file_references": "utils/data.py (transformation), db/models.py (storage)..."
    }},
    {{
      "section_id": "ui-components",
      "section_title": "Frontend Components",
      "section_description": "UI component structure",
      "diagram_type": "class",
      "file_references": "src/components/*.svelte (UI elements), lib/stores.ts (state)..."
    }}
  ]
}}

⚠️ Notice: 3 input sections → 3 output sections. SAME COUNT. SAME IDs. SAME TITLES.
           ONLY the file_references field is new!

⚠️ CRITICAL JSON REQUIREMENTS:
1. Return ONLY valid JSON - no markdown code blocks, no extra text
2. Keep ALL fields from iteration 2: section_id, section_title, section_description, diagram_type
3. Add file_references field for each section (STRING, not array)
4. ALL 5 fields are REQUIRED: section_id, section_title, section_description, diagram_type, file_references
5. Do NOT omit any fields - every section MUST have all 5 fields
6. Use proper JSON syntax with double quotes and correct commas
7. diagram_type must be one of: flowchart, sequence, class, stateDiagram, erDiagram
8. **RETURN ALL {len(refined_sections)} SECTIONS** - do not merge, combine, or omit any sections

Generate the final analysis in {language_name} language.

⚠️⚠️⚠️ MANDATORY PRE-SUBMISSION CHECKLIST ⚠️⚠️⚠️
Before you return your JSON, count the sections in your response:
Step 1: Count sections in my JSON: [ ??? ]
Step 2: Required count: {len(refined_sections)}
Step 3: Do they match? If NO, FIX IT NOW!

❌ FAILING EXAMPLE (WRONG - section count mismatch):
Input: 8 sections → Output: 2 sections ← YOU FAILED!

✅ CORRECT EXAMPLE (RIGHT - section count matches):
Input: 8 sections → Output: 8 sections ← CORRECT!

🚨 IF YOUR SECTION COUNT ≠ {len(refined_sections)}, YOUR RESPONSE IS INVALID!

Assign files now:"""
    
    return prompt


# Legacy function name for backwards compatibility
def build_diagram_sections_prompt(
    repo_name: str,
    rag_context: str,
    language: str
) -> str:
    """
    Legacy function - calls iteration 1 for backwards compatibility.
    
    NEW CODE SHOULD USE: build_diagram_sections_prompt_iteration1/2/3
    
    Args:
        repo_name: Name of the repository/codebase
        rag_context: RAG-retrieved context from codebase analysis
        language: Target language code
    
    Returns:
        Prompt string for LLM to identify diagram sections
    """
    return build_diagram_sections_prompt_iteration1(repo_name, rag_context, language)


def build_single_diagram_prompt(
    section_title: str,
    section_description: str,
    diagram_type: str,
    key_concepts: list = None,
    file_references: str = None,
    rag_context: str = "",
    retrieved_sources: str = "",
    language: str = "en"
) -> str:
    """
    Build prompt to generate a single focused Mermaid diagram for a specific section.
    
    This is Step 2: Generate one diagram for an identified section.
    
    IMPORTANT: This diagram is part of a diagram-first wiki where diagrams ARE the main content.
    The diagram + explanations should be comprehensive enough to fully explain this section.
    
    Args:
        section_title: Title of this specific section
        section_description: Description of what this section covers
        diagram_type: Type of Mermaid diagram to generate
        key_concepts: (Optional) List of key concepts to include (legacy format)
        file_references: (Optional) Detailed file analysis string (new format from iteration 3)
        rag_context: RAG-retrieved context
        retrieved_sources: Retrieved source code snippets
        language: Target language code
    
    Returns:
        Prompt string for LLM to generate diagram
    """
    language_name = get_language_name(language)
    
    # Build key concepts text (prefer file_references if available)
    concepts_text = ""
    if file_references:
        # New format: use detailed file analysis
        concepts_text = f"File references and key analysis:\n{file_references}"
    elif key_concepts and len(key_concepts) > 0:
        # Legacy format: use key_concepts list
        concepts_text = f"Key concepts to include: {', '.join(key_concepts)}"
    else:
        concepts_text = "No specific concepts provided - infer from context"
    
    # Diagram-specific instructions
    diagram_instructions = {
        "flowchart": """
- MUST start with: flowchart TD (top-down) or flowchart LR (left-right)
- Start with entry points, show decision nodes, end with outcomes
- Use rectangles for processes, diamonds for decisions, rounded for start/end
- Keep node labels concise (3-5 words max)
- Every node must represent a real component/concept from the codebase, no vague concepts or placeholders
- Can use subgraphs to group related nodes if this adds clarity

⚠️ CRITICAL MERMAID SYNTAX RULES - PARSER WILL FAIL WITHOUT THESE:

🚫 PARENTHESES () ARE FORBIDDEN IN UNQUOTED LABELS:
   ❌ WRONG: Node[Add Token()]      ← PARSER ERROR - "got 'PS'"
   ❌ WRONG: Node[Function()]        ← PARSER ERROR - () is node shape syntax
   ❌ WRONG: Node[Process (async)]   ← PARSER ERROR - () breaks parsing
   ✅ RIGHT: Node["Add Token()"]     ← ALWAYS quote when using ()
   ✅ RIGHT: Node["Function()"]      ← Quotes make () literal text
   ✅ RIGHT: Node["Process (async)"] ← Quotes prevent shape interpretation

🚫 BRACKETS [] FORBIDDEN IN UNQUOTED LABELS:
   ❌ WRONG: Node[Page /app/[id]/page.tsx]  ← PARSER ERROR
   ❌ WRONG: Node[Route [owner]/[repo]]     ← PARSER ERROR
   ✅ RIGHT: Node["Page /app/[id]/page.tsx"] ← Quote the entire label
   ✅ RIGHT: Node["Route [owner]/[repo]"]    ← Brackets safe in quotes

📋 ALL SPECIAL CHARACTERS REQUIRE QUOTES:
   * Special chars: ( ) [ ] / - @ : . + * ? ! # $ % & = , ; ' " ` ~
   * Examples that MUST use quotes:
     - Node["src/app/page.tsx"]      ← paths with /
     - Node["User-Service-API"]      ← hyphens/dashes
     - Node["Config: production"]    ← colons
     - Node["Precision@10"]          ← @ symbols
     - Node["get_user_data()"]       ← underscores OK, but () needs quotes
   
✅ SAFE WITHOUT QUOTES (simple text only):
   - Node[Simple Text]     ← spaces OK
   - Node[User Service]    ← spaces OK
   - Node[Process Data]    ← spaces OK
   
💎 GOLDEN RULE: If label has ANY special char, USE QUOTES: Node["Your Label"]

🚫 LABELED EDGES - CRITICAL SYNTAX ERROR TO AVOID:
   ❌ WRONG: A -->|Label| --> B    ← DOUBLE ARROW ERROR - Parser fails!
   ❌ WRONG: A --|Label| -- B      ← DOUBLE DASH ERROR
   ❌ WRONG: A ==>|Label| ==> B    ← DOUBLE THICK ERROR
   ✅ RIGHT: A -->|Label| B        ← Single arrow with label
   ✅ RIGHT: A --|Label| B         ← Single dash with label
   ✅ RIGHT: A ==>|Label| B        ← Single thick arrow with label
   
   EXPLANATION: The -->|Label| syntax ALREADY creates the arrow.
   Adding another --> is redundant and causes "syntax error" in Mermaid.
   
   EXAMPLES OF CORRECT USAGE:
   - Decision branches: Decision{Question?} -->|Yes| ActionA
   - Conditional flow: Check -->|Valid| Process
   - Labeled steps: Step1 -->|Success| Step2

- STYLING RULES (Premium Professional Style):
  * Use MINIMAL and SELECTIVE coloring - most nodes should use default styling
  * Apply colors ONLY to emphasize critical nodes (entry points, error states, key decision points)
  * Use a consistent, muted color palette:
    - Entry/Start points: style X fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    - Error/Critical states: style Y fill:#ffebee,stroke:#c62828,stroke-width:2px
    - Success/End states: style Z fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    - Key decision points: style W fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
  * NO random rainbow colors (avoid #f9f, #bbf, #bfb, #fbb, #bff, #ffb, etc.)
  * Leave most nodes unstyled for a clean, professional appearance
  * Apply styling to at most 3-5 critical nodes per diagram, never to every node""",
        
        "sequence": """
- MUST start with: sequenceDiagram
- Define participants: participant Name as Display Label (or just use participant Name)
- CRITICAL: Do NOT use Name[Label] syntax - that's for flowcharts only!
- Use ->> for synchronous calls (solid arrows)
- Use -->> for responses/returns (dashed arrows)
- Add activation boxes with +/- where appropriate
- Show the temporal sequence of interactions
- Include alt/else for conditional flows, loop for iterations

⚠️ CRITICAL: ACTIVATE/DEACTIVATE MUST BE BALANCED!
  * Each participant: activate count MUST EQUAL deactivate count
  * Common error: Deactivating inside alt/else branches AND after end (MULTIPLE DEACTIVATES)
  
  ❌ WRONG - Multiple deactivates for same participant:
  activate LLMService
  alt Branch A
    LLMService->>X: call
    deactivate LLMService  ← WRONG: deactivate in branch
  else Branch B
    LLMService->>Y: call
    deactivate LLMService  ← WRONG: deactivate in branch
  end
  deactivate LLMService  ← WRONG: trying to deactivate already inactive!
  
  ✅ RIGHT - Only deactivate ONCE after all alt/else blocks:
  activate LLMService
  alt Branch A
    LLMService->>X: call
  else Branch B
    LLMService->>Y: call
  end
  deactivate LLMService  ← CORRECT: Only ONE deactivate at the end
  
  🎯 RULE: If participant is active BEFORE alt/else, stay active THROUGH ALL BRANCHES.
          Only deactivate ONCE after ALL alt/else blocks complete.

- Example:
  sequenceDiagram
      participant Client
      participant API as API Gateway
      Client->>API: Request
      API-->>Client: Response""",
        
        "class": """
- MUST start with: classDiagram
- Define each class ONLY ONCE: class ClassName { +method() -attribute }
- CRITICAL: Can ONLY use defined classes in relationships/notes
  * If class X uses class Y, BOTH X and Y MUST be defined with 'class' keyword first
  * WRONG: class A {...} then A --> "SomeType" (SomeType never defined!)
  * RIGHT: class A {...} class B {...} then A --> B
- Generic types: Use ~~ syntax, NOT <>
  * WRONG: function<bool(T, T)> or vector<int>
  * RIGHT: function~bool, T, T~ or vector~int~
  * Or create actual class: class function_bool_T_T {...}
- Complex types that need relationships: Define them as classes
  * If you need A --> FunctionType, define class FunctionType first
  * Example: class function_bool_T_T { +bool operator_call(T a, T b) }
- NEVER define same class multiple times or mix syntax styles
- NO circular inheritance: Don't make A <|-- B AND B <|-- A
- Relationships: <|-- (inherit), *-- (compose), o-- (aggregate), --> (associate)
- Notes at end: note for ClassName "description"
- Example:
  classDiagram
    class Tree {
      -Node root
      +insert(val)
    }
    class Node {
      -int val
      -Node left
    }
    Tree o-- Node
    note for Tree "Container class"
""",
        
        "stateDiagram": """
- MUST start with: stateDiagram-v2
- Show all important states
- Clearly mark initial state with [*]
- CRITICAL: Use state diagram syntax for labeled transitions: State1 --> State2 : label
  * The label comes AFTER the arrow with a colon (:)
  * Example: CheckUserAuth --> LoadWorkshopPage : User Authenticated
- Include conditional transitions where relevant
- Mark final states""",
        
        "erDiagram": """
- MUST start with: erDiagram
- Define entities with attributes using this EXACT syntax:
  EntityName {
      type attribute
      type attribute
  }
- CRITICAL: Do NOT use 'class EntityName {' - that's for class diagrams!
- Use only: EntityName { ... } without the 'class' keyword
- CRITICAL: ONLY use cardinality relationship syntax (||--o{, }o--o{, ||--||, etc.)
- NEVER use arrow syntax (-->, --->, etc.) - that's for flowcharts, NOT ER diagrams!
- Show relationships: EntityA ||--o{ EntityB : relationship_name
- Relationship cardinality: ||--o{ (one-to-many), }o--o{ (many-to-many), ||--|| (one-to-one)
- Example:
  erDiagram
      CUSTOMER {
          int id PK
          string name
      }
      ORDER {
          int id PK
          int customer_id FK
      }
      CUSTOMER ||--o{ ORDER : places"""
    }
    
    # Map diagram types to their required Mermaid syntax prefixes
    diagram_syntax = {
        "flowchart": "flowchart TD",
        "sequence": "sequenceDiagram",
        "class": "classDiagram",
        "stateDiagram": "stateDiagram-v2",
        "erDiagram": "erDiagram"
    }
    
    specific_instructions = diagram_instructions.get(diagram_type, diagram_instructions["flowchart"])
    required_syntax = diagram_syntax.get(diagram_type, "flowchart")
    
    prompt = f"""⚠️ LANGUAGE REQUIREMENT: Generate ALL content in {language_name} language ({language}).
This includes: diagram descriptions, node explanations, edge explanations, and all text.

You are an expert at creating clear, informative Mermaid diagrams for a DIAGRAM-FIRST WIKI.

🎯 CRITICAL: This diagram is the PRIMARY CONTENT for this section, not a supplement.
The wiki is composed of interactive diagrams with explanations - the diagrams ARE the documentation.

CONTEXT:
- Section: {section_title}
- Section focus: {section_description}
- Diagram type: {diagram_type}
- {concepts_text}

CODEBASE CONTEXT:
{rag_context}

SOURCE CODE SNIPPETS:
{retrieved_sources}

Your task is to create a COMPREHENSIVE Mermaid {diagram_type} diagram that FULLY EXPLAINS this section.
This is not just a visual aid - it's the main content!

DIAGRAM SYNTAX REQUIREMENT:
CRITICAL: Your mermaid_code MUST start with: {required_syntax}

DIAGRAM REQUIREMENTS:
{specific_instructions}

CRITICAL RULES:
1. Node IDs must be simple alphanumeric (e.g., API, Client, UserService, validateInput)
2. IMPORTANT: Use descriptive, meaningful node/participant IDs that reflect their purpose
   - Good: API, Client, Database, UserService, validateInput, processRequest
   - Bad: A, B, C, Node1, Node2, temp, xyz
3. SPECIAL CHARACTERS IN NODE LABELS:
   - NEVER use @ symbol directly in labels (e.g., "Recall@10" will BREAK)
   - Instead wrap in quotes: NodeID["Recall@10"] or use alternative text: NodeID[Recall at 10]
   - AVOID: parentheses (), brackets [], braces {{}}, @ in unquoted labels
   - If special chars needed: use quoted syntax NodeID["Label with @"] or replace with words
4. Make the diagram COMPREHENSIVE - it must fully explain {section_title}
5. Add meaningful edge labels where it adds clarity
6. Ensure the diagram is syntactically correct Mermaid code for {diagram_type}
7. Since this is the primary content, be detailed and complete

IMPORTANT DIAGRAM QUALITY (CRITICAL FOR DIAGRAM-FIRST WIKI):
- Every node should represent a real component/concept from the codebase
- Relationships should accurately reflect the actual code structure
- Use the RAG context and source snippets as your primary source of truth
- The diagram MUST be comprehensive enough to understand the section WITHOUT additional text
- Think: "Can someone understand this topic fully just from this diagram and explanations?"
- Think: "In addition to structure design, what node styles, edge styles, and layout choices add clarity?"

⚠️ CRITICAL LANGUAGE REQUIREMENT:
- ALL text fields must be in {language_name} language
- diagram_description → in {language_name}
- node_explanations → in {language_name}
- edge_explanations → in {language_name}
- Node labels in Mermaid code → in {language_name} (but keep node IDs in English)

Return your response in the following JSON format:

{{
  "mermaid_code": "{required_syntax}\\n  Client[Client Request]\\n  API[API Layer]\\n  ...",
  "diagram_description": "Brief 2-3 sentence explanation in {language_name}",
  "node_explanations": {{
    "Client": "Explanation of what this node represents and its role",
    "API": "Explanation of the API layer's responsibilities"
  }},
  "edge_explanations": {{
    "Client->API": "Explanation of this relationship/interaction",
    "API->Database": "Explanation of this connection"
  }}
}}

CRITICAL FORMATTING:
- Return ONLY valid JSON (no markdown code blocks like ```json)
- Escape newlines in mermaid_code as \\n
- Ensure all quotes are properly escaped
- Use the node IDs exactly as they appear in mermaid_code for explanations
- For edge explanations, use the format: "SourceNode->TargetNode" or "SourceNode-->TargetNode"

🌐 FINAL LANGUAGE CHECK BEFORE SUBMITTING:
✓ Is diagram_description in {language_name}? ({language})
✓ Are all node_explanations in {language_name}? ({language})
✓ Are all edge_explanations in {language_name}? ({language})
✓ Are Mermaid node labels in {language_name}? ({language})

If ANY field is in the wrong language, FIX IT NOW before returning!

Create the diagram now:"""
    
    return prompt

def build_diagram_correction_prompt(
    section_title: str,
    section_description: str,
    diagram_type: str,
    key_concepts: list = None,
    file_references: str = None,
    rag_context: str = "",
    retrieved_sources: str = "",
    corrupted_diagram: str = "",
    error_message: str = "",
    language: str = "en"
) -> str:
    """
    Build prompt to fix a corrupted Mermaid diagram that failed to render.
    
    This prompt provides explicit error correction context to help the LLM
    understand what went wrong and generate a valid diagram.
    
    Args:
        section_title: Title of the section
        section_description: Description of the section
        diagram_type: Type of diagram
        key_concepts: (Optional) Key concepts to include (legacy format)
        file_references: (Optional) Detailed file analysis string (new format from iteration 3)
        rag_context: RAG-retrieved context
        retrieved_sources: Retrieved source code snippets
        corrupted_diagram: The broken Mermaid code
        error_message: The error from Mermaid renderer
        language: Target language code
    
    Returns:
        Prompt string for LLM to fix the diagram
    """
    language_name = get_language_name(language)
    
    # Build key concepts text (prefer file_references if available)
    if file_references:
        key_concepts_str = f"File references:\n{file_references}"
    elif key_concepts and len(key_concepts) > 0:
        key_concepts_str = "\n".join([f"  - {concept}" for concept in key_concepts])
    else:
        key_concepts_str = "  (No specific concepts provided)"
    
    # Use the same diagram instructions from build_single_diagram_prompt
    diagram_instructions = {
        "flowchart": """- MUST start with: flowchart TD (top-down) or flowchart LR (left-right)
- Use rectangles for processes, diamonds for decisions, rounded for start/end
- Keep node labels concise (3-5 words max)

⚠️ CRITICAL: PARENTHESES () FORBIDDEN IN UNQUOTED LABELS:
   ❌ WRONG: Node[Add Token()]      ← PARSER ERROR: "got 'PS'"
   ❌ WRONG: Node[Process (async)]   ← PARSER ERROR: () is node shape
   ✅ RIGHT: Node["Add Token()"]     ← Quote when using ()
   ✅ RIGHT: Node["Process (async)"] ← Always quote ()

⚠️ CRITICAL: BRACKETS [] FORBIDDEN IN UNQUOTED LABELS:
   ❌ WRONG: Node[Route [owner]]     ← PARSER ERROR
   ✅ RIGHT: Node["Route [owner]"]   ← Quote the label

📋 ALL SPECIAL CHARS NEED QUOTES: ( ) [ ] / - @ : . + * etc.
   Safe without quotes: Node[Simple Text] or Node[Process Data]
   GOLDEN RULE: If ANY special char → USE QUOTES: Node["Your Label"]

- STYLING: Use minimal coloring - only emphasize critical nodes""",
        "sequence": """- MUST start with: sequenceDiagram
- Format: participant Name
- Show message flow: Actor->>Target: message
- Use activate/deactivate for lifelines
- CRITICAL: "return" is NOT valid syntax in Mermaid! Instead use Actor-->>Target: message or Note
- If ending early, just use deactivate Actor (NO bare "return" statement!)""",
        "class": """- MUST start with: classDiagram
- Define each class ONLY ONCE with members inside: class ClassName { -attribute +method() }
- CRITICAL: Can ONLY reference classes that are defined - no undefined types in relationships/notes
- Generic types: Use ~~ not <>. Example: vector~int~ not vector<int>
- Complex types needing relationships: Define as classes (e.g., class function_bool_T {...})
- NEVER duplicate class definitions or mix definition styles
- Relationships: Parent <|-- Child (inheritance), Whole o-- Part (aggregation)
- Put notes AFTER all class definitions: note for ClassName "description"
- NO circular inheritance (A <|-- B AND B <|-- A)""",
        "stateDiagram": """- MUST start with: stateDiagram-v2
- Define states: state "Name" as id
- Show transitions: id1 --> id2: event""",
        "erDiagram": """- MUST start with: erDiagram
- Define entities: EntityName { type attribute }
- CRITICAL: Do NOT use 'class' keyword (that's for class diagrams!)
- CRITICAL: ONLY use cardinality syntax (||--o{, }o--o{, ||--||)
- NEVER use arrow syntax (-->, --->) - that's for flowcharts!
- Use ||--o{ for relationship types
- Example: CUSTOMER { int id } \nCUSTOMER ||--o{ ORDER : places"""
    }
    
    required_syntax = {
        "flowchart": "flowchart TD",
        "sequence": "sequenceDiagram",
        "class": "classDiagram",
        "stateDiagram": "stateDiagram-v2",
        "erDiagram": "erDiagram"
    }.get(diagram_type, "flowchart TD")
    
    instructions = diagram_instructions.get(diagram_type, diagram_instructions["flowchart"])
    
    # Define diagram-type-specific common errors
    common_errors_generic = [
        "**Special characters in labels** → Wrap in quotes: A[\"Recall@10\"]",
        "**Missing diagram type declaration** → Start with: {required_syntax}",
        "**Invalid node IDs** → Use alphanumeric IDs (no spaces/special chars)",
        "**Invalid characters** → Remove or escape @, #, %, etc. in labels"
    ]
    
    common_errors_flowchart = [
        """**@ symbol in node labels** → CRITICAL! The @ character BREAKS Mermaid parsing
   - ERROR: `D[Recall@10]` causes "Parse error... got 'LINK_ID'"
   - FIX: Wrap label in quotes: `D["Recall@10"]`
   - OR: Replace @ with words: `D[Recall at 10]`
   - This applies to ALL special chars: @, #, %, $, &, etc.
   - ALWAYS check for @ symbols and quote them!""",
        "**Syntax errors in arrows** → Use --> or ->> correctly",
        "**Unclosed subgraphs** → Ensure every subgraph has \"end\"",
        "**Invalid style syntax** → Check color codes and property names",
        "**Duplicate node IDs** → Make all IDs unique",
        """In Mermaid, the syntax -->|Label| already creates the arrow. 
        You do not need to add another --> after the label
        For example A -->|Yes| --> B is WRONG and you should use A -->|Yes| B"""
    ]
    
    common_errors_sequence = [
        """**"return" keyword NOT supported** → Mermaid does NOT support bare "return"!
   - WRONG: `return` (causes parse error)
   - RIGHT: Remove it entirely, or use `Actor-->>Target: return_value`
   - If ending flow early: just use `deactivate Actor` without "return\"""",
        """**Deactivate without activate** → "Trying to inactivate an inactive participant"
   - ERROR: Calling `deactivate Actor` for a participant never activated OR already deactivated
   - COMMON CAUSES:
     a) `deactivate` inside alt/else branch AND after `end`
     b) `deactivate` without matching `activate`
     c) Calling `deactivate` twice for the same participant
   
   ⚠️ MANDATORY FIX ALGORITHM - FOLLOW THESE STEPS EXACTLY:
   
   STEP 1: Extract ALL participants from the diagram
     - List every participant name (A, B, Client, Server, etc.)
   
   STEP 2: For EACH participant, create a checklist:
     Participant: [Name]
       - Count of `activate [Name]`: [number]
       - Count of `deactivate [Name]`: [number]
       - Status: [EQUAL or MISMATCH]
   
   STEP 3: For each MISMATCH, identify the fix:
     - If more deactivate than activate → Remove extra deactivate statements
       * Common pattern: deactivate inside alt/else branch AND after end
       * Fix: Keep only the deactivate AFTER the end block
     - If more activate than deactivate → Add missing deactivate statements
       * Add deactivate at the end of the participant's lifecycle
   
   STEP 4: Common wrong patterns and their fixes:
     
     ❌ PATTERN 1: Deactivate inside alt/else branches + after end (DOUBLE DEACTIVATE)
     ```
     activate A
     alt Valid
       A->>B: success
       deactivate A  ← WRONG: inside alt
     else Invalid
       A->>B: error
       deactivate A  ← WRONG: inside else
     end
     deactivate A  ← WRONG: after end (now it's TRIPLE!)
     ```
     
     ✅ FIX: Only deactivate ONCE, AFTER the alt/else/end block
     ```
     activate A
     alt Valid
       A->>B: success
     else Invalid
       A->>B: error
     end
     deactivate A  ← CORRECT: Only ONE deactivate after end
     ```
     
     ❌ PATTERN 2: Multiple alt blocks with deactivates (MULTIPLE DEACTIVATES)
     ```
     activate LLMService
     alt Provider is OpenAI
       LLMService->>OpenAI: request
       deactivate LLMService  ← WRONG: deactivate in first branch
     else Provider is HuggingFace
       LLMService->>HF: request
       deactivate LLMService  ← WRONG: deactivate in second branch
     end
     alt Request Fails
       LLMService->>ErrorHandler: handle
       deactivate LLMService  ← WRONG: trying to deactivate already inactive
     end
     ```
     
     ✅ FIX: Only deactivate ONCE, after ALL alt/else blocks complete
     ```
     activate LLMService
     alt Provider is OpenAI
       LLMService->>OpenAI: request
       # NO deactivate here
     else Provider is HuggingFace
       LLMService->>HF: request
       # NO deactivate here
     end
     alt Request Fails
       LLMService->>ErrorHandler: handle
       # NO deactivate here
     end
     deactivate LLMService  ← CORRECT: Only ONE deactivate at the very end
     ```
     
     🎯 GOLDEN RULE FOR ALT/ELSE BLOCKS:
     - If a participant is active BEFORE alt/else, it stays active THROUGH ALL BRANCHES
     - NEVER deactivate inside alt/else branches
     - ONLY deactivate ONCE after ALL alt/else blocks complete
   
   STEP 5: VERIFY BEFORE RETURNING - For each participant:
     - Count ALL activates: [ ??? ]
     - Count ALL deactivates: [ ??? ]
     - Must be EQUAL!
     - If not equal, go back to STEP 3 and fix it
     
   ⚠️ CRITICAL: IF YOU RETURN CODE WHERE COUNTS ARE NOT EQUAL, YOU HAVE FAILED!
   DO NOT RETURN THE SAME BROKEN CODE. YOUR FIXED CODE MUST HAVE EQUAL COUNTS FOR ALL PARTICIPANTS."""
    ]
    
    common_errors_class = [
        """**Using undefined class in relationship/note** → "Cannot read properties of undefined (reading 'startsWith')"
   - CRITICAL: All classes in relationships and notes MUST be defined first
   - WRONG: class A {...} then A --> "SomeType" (SomeType not defined!)
   - WRONG: note for "function<bool>" "..." (function<bool> not defined!)
   - RIGHT: Define ALL classes first, then add relationships/notes
   - For complex types: Create a class like class function_bool_T_T {...}""",
        """**Using <> for generics** → Breaks Mermaid parsing
   - WRONG: function<bool(T)> or vector<int>
   - RIGHT: Use ~~ syntax: function~bool, T~ or vector~int~""",
        """**Duplicate class definitions** → Parse error "got 'DEPENDENCY'"
   - Define each class ONLY ONCE
   - WRONG: class A {...} then class A {...} again
   - RIGHT: class A { all members here }""",
        """**Mixed syntax styles** → Causes parsing errors
   - Pick ONE: Either class A { members } OR class A followed by A : member lines
   - NEVER mix both styles for same class""",
        """**Circular inheritance** → A <|-- B AND B <|-- A breaks rendering
   - Remove bidirectional inheritance""",
        "**Invalid relationship syntax** → Use <|-- (inherit), *-- (compose), o-- (aggregate)"
    ]
    
    common_errors_state = [
        """**CRITICAL: Using flowchart label syntax '-- text -->'** → Parse error: got 'INVALID'
   - State diagrams do NOT use flowchart's '-- text -->' syntax!
   - WRONG: `StateA -- Label Text --> StateB` (flowchart syntax)
   - RIGHT: `StateA --> StateB : Label Text` (state diagram syntax)
   - In state diagrams, the label comes AFTER the arrow with a colon
   - Example error: "CheckUserAuth -- User Authenticated --> LoadWorkshopPage"
   - Correct fix: "CheckUserAuth --> LoadWorkshopPage : User Authenticated\"""",
        "**Invalid state transitions** → Use --> for transitions with optional labels",
        "**Unclosed state blocks** → Ensure composite states have proper nesting"
    ]
    
    common_errors_er = [
        "**CRITICAL: Using '-->' arrow syntax** → Parse error: ER diagrams do NOT support arrow syntax!",
        "   - WRONG: Entity1 --> Entity2 : relationship",
        "   - RIGHT: Entity1 ||--o{ Entity2 : relationship",
        "   - Arrow syntax (-->, --->, etc.) is ONLY for flowcharts!",
        "   - ER diagrams require cardinality syntax: ||--o{, }o--o{, ||--||, etc.",
        "**CRITICAL: Using 'class' keyword** → Parse error on line X: got 'BLOCK_START'",
        "   - WRONG: class User { string id ... }",
        "   - RIGHT: User { string id ... }",
        "   - The 'class' keyword is for CLASS DIAGRAMS only!",
        "   - ER diagrams use: EntityName { type attribute }",
        "**Invalid relationship cardinality** → Use ||--o{ , |o--o| , etc.",
        "**Missing entity definition** → Define entities before relationships",
        "**Syntax error in attribute definition** → Use: EntityName { type attribute } not class EntityName { }"
    ]
    
    # Select errors based on diagram type
    type_specific_errors = {
        "flowchart": common_errors_generic + common_errors_flowchart,
        "sequence": common_errors_generic + common_errors_sequence,
        "class": common_errors_generic + common_errors_class,
        "stateDiagram": common_errors_generic + common_errors_state,
        "erDiagram": common_errors_generic + common_errors_er
    }
    
    selected_errors = type_specific_errors.get(diagram_type, common_errors_generic + common_errors_flowchart)
    errors_text = "\n".join([f"{i+1}. {err}" for i, err in enumerate(selected_errors)])
    
    # Add detailed examples only for sequence diagrams (since they're most problematic)
    examples_section = ""
    if diagram_type == "sequence":
        examples_section = """
DETAILED EXAMPLES FOR SEQUENCE DIAGRAMS:

EXAMPLE #1 - Double deactivate (inside branch + after end):
❌ BROKEN:
```
alt Valid
  Actor->>Target: success
else Invalid  
  Actor->>Target: error
  deactivate Actor  ← deactivate inside branch
end
deactivate Actor  ← deactivate after end (ERROR!)
```

✅ FIXED:
```
alt Valid
  Actor->>Target: success
else Invalid  
  Actor->>Target: error
end
deactivate Actor  ← Only ONE deactivate after end
```

EXAMPLE #2 - Deactivate without activate:
❌ BROKEN:
```
A->>B: call function
activate B
B-->>A: return result
deactivate B
A-->>C: forward result
deactivate A  ← ERROR: A was never activated!
```

✅ FIXED (Option 1 - Add activate):
```
A->>B: call function
activate A  ← Add missing activate
activate B
B-->>A: return result
deactivate B
A-->>C: forward result
deactivate A  ← Now this matches the activate above
```

✅ FIXED (Option 2 - Remove deactivate):
```
A->>B: call function
activate B
B-->>A: return result
deactivate B
A-->>C: forward result
← Simply remove the unmatched deactivate
```
"""
    
    # Type-specific verification steps
    verification_steps_generic = [
        "Analyze the error message and identify the EXACT issue",
        "**FIX the syntax error** - do NOT return the same broken code!",
        "If you're unsure how to fix it: RECONSTRUCT the diagram with correct syntax",
        "Ensure the diagram is valid Mermaid syntax",
        "Keep the same key concepts and structure",
        "Add comprehensive node and edge explanations"
    ]
    
    verification_steps_sequence = [
        "**SEQUENCE DIAGRAM SPECIFIC VERIFICATION**:",
        "  - Search for EVERY `deactivate ParticipantName` in the diagram",
        "  - Count how many `activate ParticipantName` exist for each participant",
        "  - If counts don't match: either add missing `activate` or remove extra `deactivate`",
        "  - Count all `activate X` statements for each participant",
        "  - Count all `deactivate X` statements for each participant",
        "  - Ensure counts are EQUAL for each participant",
        "  - If not equal: FIX IT BEFORE RETURNING!"
    ]
    
    if diagram_type == "sequence":
        verification_steps = verification_steps_generic + verification_steps_sequence
    else:
        verification_steps = verification_steps_generic
    
    verification_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(verification_steps)])
    
    prompt = f"""You are an expert at creating Mermaid diagrams for codebase visualization.

A diagram you generated has a RENDERING ERROR. Your task is to FIX IT.

SECTION INFORMATION:
Title: {section_title}
Description: {section_description}
Diagram Type: {diagram_type}
Key Concepts:
{key_concepts_str}

❌ ERROR THAT OCCURRED (MOST IMPORTANT!!!):
{error_message}

🔴 CORRUPTED DIAGRAM CODE:
```mermaid
{corrupted_diagram}
```

CODEBASE CONTEXT (from RAG):
{rag_context}

RETRIEVED SOURCE CODE:
{retrieved_sources}

YOUR TASK: Fix the diagram to make it render correctly in Mermaid.

⚠️ CRITICAL: You MUST fix the syntax error. DO NOT return the same broken code!

COMMON MERMAID ERRORS FOR {diagram_type.upper()} DIAGRAMS:
{errors_text}
{examples_section}

DIAGRAM-SPECIFIC SYNTAX:
{instructions}

INSTRUCTIONS:
{verification_text}

Return your response in JSON format:

{{
  "mermaid_code": "{required_syntax}\\n  ...",
  "diagram_description": "Brief explanation of the fixed diagram",
  "node_explanations": {{
    "NodeID": "What this node represents"
  }},
  "edge_explanations": {{
    "Source->Target": "What this connection means"
  }}
}}

CRITICAL:
- Return ONLY valid JSON (no markdown code blocks)
- Escape newlines as \\n
- Test the syntax mentally before returning
- Make sure it starts with: {required_syntax}

Generate in {language_name} language. Fix the diagram now:"""
    
    return prompt

def build_wiki_question_prompt(
    question: str,
    wiki_context: str,
    codebase_context: str
) -> str:
    """
    Build prompt for answering questions about the wiki using both wiki and codebase context.
    
    This combines generated wiki content (diagram explanations) with relevant codebase snippets
    to provide comprehensive answers without information loss.
    
    Args:
        question: User's question about the wiki
        wiki_context: Context from generated wiki (diagrams, explanations)
        codebase_context: Context from actual source code
    
    Returns:
        Prompt string for LLM to answer the question
    """
    prompt = f"""You are a helpful technical assistant answering questions about a codebase wiki.

You have access to TWO sources of information:

1. GENERATED WIKI CONTENT (high-level explanations and diagrams):
{wiki_context}

2. SOURCE CODE CONTEXT (actual implementation details):
{codebase_context}

USER QUESTION: {question}

Instructions:
- Use the WIKI CONTENT for high-level understanding and structure
- Use the SOURCE CODE for implementation details and specifics
- Combine both sources to give a complete, accurate answer
- If the wiki and code contradict, trust the code (wiki may be outdated)
- If information is missing from both sources, clearly state what you don't know
- Be clear, concise, and technical

Answer:"""
    
    return prompt


def build_wiki_problem_analysis_prompt(
    user_prompt: str,
    wiki_context: str,
    codebase_context: str,
    wiki_items: Optional[Dict[str, str]] = None,
    language: str = "en"
) -> str:
    """
    Build prompt for analyzing whether a user's request is a question or modification request.
    
    Args:
        user_prompt: User's request
        wiki_context: Existing wiki content from RAG
        codebase_context: Relevant codebase snippets
        wiki_items: Optional dict of {wiki_name: question} pairs
        language: Target language code for response
    
    Returns:
        Prompt string for LLM to analyze the request
    """
    wiki_items_section = ""
    if wiki_items:
        wiki_items_section = "\n\nSPECIFIC WIKI SECTIONS MENTIONED:\n"
        for wiki_name, question in wiki_items.items():
            q_text = f" - Question: {question}" if question else ""
            wiki_items_section += f"- {wiki_name}{q_text}\n"
    
    prompt = f"""You are a technical documentation analyst. Analyze the user's request and determine if it's a QUESTION or a MODIFICATION REQUEST.

EXISTING WIKI CONTENT:
{wiki_context}

CODEBASE CONTEXT:
{codebase_context}
{wiki_items_section}

USER REQUEST:
{user_prompt}

IMPORTANT LANGUAGE REQUIREMENT:
If intent is "question", generate the "answer" field in {get_language_name(language)} language.
If intent is "modification", keep field names (intent, reasoning, modify, create, wiki_name, reason, next_step_prompt) in English, but write the text VALUES (reasoning, reason, next_step_prompt) in {get_language_name(language)} language.

CRITICAL DECISION RULES:
1. If user asks "how", "what", "why", "explain", "tell me" → QUESTION (provide direct answer)
2. If user says "add", "create", "update", "modify", "show me with diagram", "I need a diagram" → MODIFICATION (plan changes)
3. If user says "I'm curious about X" or "I want to understand Y" → QUESTION (they want to learn, not create docs)
4. If user explicitly requests documentation/diagram creation → MODIFICATION

RESPONSE FORMAT - MUST FOLLOW EXACTLY:

For QUESTION (user wants to learn):
{{
    "intent": "question",
    "answer": "Your comprehensive answer using the wiki and codebase context"
}}
NOTE: If intent is "question", you MUST include "answer" field and MUST NOT include "modify" or "create" fields.

For MODIFICATION REQUEST (user wants to add/change documentation):
{{
    "intent": "modification",
    "reasoning": "Why this modification is appropriate",
    "modify": [
        {{
            "wiki_name": "existing-section-id",
            "reason": "Why this section needs modification",
            "next_step_prompt": "Update the [section] to include [specific details from user request]..."
        }}
    ],
    "create": [
        {{
            "wiki_name": "new-section-id",
            "reason": "Why a new section is needed",
            "next_step_prompt": "Create a diagram showing [specific requirements from user request]..."
        }}
    ]
}}
NOTE: If intent is "modification", you MUST include "reasoning", "modify", and "create" fields (arrays can be empty). You MUST NOT include "answer" field.

EXAMPLES:

Example 1 - QUESTION:
User: "How does adalflow work with the localDB?"
→ {{"intent": "question", "answer": "Adalflow integrates with localDB by..."}}

Example 2 - MODIFICATION:
User: "I need a diagram showing how adalflow works with localDB"
→ {{"intent": "modification", "reasoning": "User wants visual documentation", "modify": [], "create": [{{"wiki_name": "adalflow-localdb-integration", "reason": "No existing diagram covers this", "next_step_prompt": "Create a flowchart showing adalflow's interaction with localDB..."}}]}}

Example 3 - QUESTION (even with "curious"):
User: "I'm curious about how the RAG system works"
→ {{"intent": "question", "answer": "The RAG system uses..."}}

Example 4 - MODIFICATION:
User: "Add WikiCache to the architecture diagram"
→ {{"intent": "modification", "reasoning": "Need to update existing diagram", "modify": [{{"wiki_name": "system-architecture", "reason": "WikiCache component missing", "next_step_prompt": "Update diagram to show WikiCache and its connections..."}}], "create": []}}

Guidelines:
- Default to QUESTION unless user explicitly requests documentation/diagram creation
- Use kebab-case for wiki_name (e.g., "data-flow-diagram")
- Provide detailed next_step_prompt that can be used directly for diagram generation
- NEVER mix formats - question must not have modify/create, modification must not have answer

Respond with valid JSON only:"""
    
    return prompt


def build_wiki_creation_prompt(
    wiki_name: str,
    creation_prompt: str,
    codebase_context: str,
    diagram_type: str = None,
    language: str = "en"
) -> str:
    """
    Build prompt for creating a new wiki section.
    
    Args:
        wiki_name: Name/ID of the new section
        creation_prompt: Detailed requirements from problem analysis
        codebase_context: Relevant code snippets
        diagram_type: Optional diagram type ('auto' or specific type)
        language: Target language code
    
    Returns:
        Prompt string for creating new wiki content
    """
    language_name = get_language_name(language)
    # Determine diagram type instruction
    if diagram_type and diagram_type != 'auto':
        diagram_type_instruction = f'You MUST use diagram type: {diagram_type}'
        diagram_type_field = f'"diagram_type": "{diagram_type}",'
    else:
        diagram_type_instruction = 'Choose the most appropriate diagram type for the content'
        diagram_type_field = '"diagram_type": "flowchart|sequence|class|stateDiagram|erDiagram",'
    
    prompt = f"""You are an expert technical documentation architect creating a COMPREHENSIVE diagram for a professional codebase wiki.

🎯 CRITICAL CONTEXT: This diagram will be the PRIMARY DOCUMENTATION for this section.
Users will rely on it to understand complex system architecture, data flows, and component relationships.
Your diagram must be thorough, detailed, and production-grade - not a simplified overview.

SECTION DETAILS:
• Section Name: {wiki_name}
• Requirements: {creation_prompt}

═══════════════════════════════════════════════════════════════════════════════

CODEBASE ANALYSIS (Your Primary Source of Truth):
{codebase_context}

🚨 CRITICAL QUALITY REQUIREMENTS:

1. COMPREHENSIVE COVERAGE
   ✓ Map out ALL major components and their relationships found in the codebase
   ✓ Show parallel paths, alternative flows, and edge cases - not just the happy path
   ✓ Include error handling, validation steps, and side effects
   ✓ Represent the ACTUAL complexity of the system (10-25+ nodes for complex systems)
   ✓ Think: "Does this diagram show everything a developer needs to understand this system?"

2. DEPTH OVER SIMPLICITY
   ✓ Don't reduce complex architectures to 5-7 nodes - that's oversimplification
   ✓ Show internal component structure, not just high-level boxes
   ✓ Include data transformations, processing steps, and intermediate states
   ✓ Reveal the layered architecture and component hierarchies
   ✓ Use subgraphs to organize related components when beneficial

3. REAL COMPONENT NAMES
   ✓ Extract actual class names, function names, and module names from the codebase
   ✓ Use specific identifiers (e.g., "UserAuthService", "validateRequest()") not generic labels ("Service", "Process")
   ✓ Reference real file paths, API endpoints, and database tables
   ✓ Every node should be traceable back to concrete code elements

4. COMPLETE RELATIONSHIP MAPPING
   ✓ Show all significant dependencies, not just main flow
   ✓ Include conditional branches and decision points with clear conditions
   ✓ Document data flow directions and transformation steps
   ✓ Add meaningful edge labels that explain WHY connections exist
   ✓ Capture asynchronous operations, callbacks, and event-driven patterns

5. PRODUCTION-QUALITY DETAILS
   ✓ Add explanatory notes for complex subsystems
   ✓ Use appropriate diagram features (subgraphs, annotations, groupings)
   ✓ Ensure logical layout that guides understanding (left-to-right or top-to-bottom flow)
   ✓ Balance detail density - pack information without cluttering

═══════════════════════════════════════════════════════════════════════════════

TECHNICAL SPECIFICATIONS:

Output JSON Structure:
{{
    "section_id": "{wiki_name}",
    "section_title": "Precise, descriptive title reflecting scope",
    "section_description": "2-3 sentences explaining what this diagram documents and why it matters",
    {diagram_type_field}
    "key_concepts": ["concept1", "concept2", "concept3", "concept4", "concept5"],
    "mermaid_code": "Comprehensive Mermaid diagram with 10-25+ nodes for complex systems",
    "diagram_description": "Detailed explanation of diagram structure and what it reveals",
    "node_explanations": {{
        "nodeId": "Clear explanation of component purpose, responsibilities, and role in system"
    }},
    "edge_explanations": {{
        "source->target": "Precise description of relationship, data flow, or interaction"
    }}
}}

Diagram Type: {diagram_type_instruction}

STYLING GUIDELINES:
• Use MINIMAL, SELECTIVE coloring - most nodes default-styled for clarity
• Apply color ONLY to emphasize critical nodes:
  - Entry/Start: style X fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
  - Error/Critical: style Y fill:#ffebee,stroke:#c62828,stroke-width:2px  
  - Success/End: style Z fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
  - Key Decisions: style W fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
• Avoid random rainbow colors (#f0f8ff, #ffe4b5, #98fb98, etc.)
• Style at most 3-5 critical nodes per diagram for professional appearance

═══════════════════════════════════════════════════════════════════════════════

⚠️ ANTI-PATTERNS TO AVOID:
✗ Linear single-path diagrams (A→B→C→D) for complex systems
✗ Generic node labels ("Process", "Handler", "Service") instead of actual names
✗ Omitting error handling, validation, or alternative flows
✗ Oversimplifying 50+ component systems into 5 nodes
✗ Missing conditional logic and branching paths
✗ Vague edge labels or unlabeled critical connections

🚫 MERMAID PARSER ERRORS (WILL CRASH):
✗ Parentheses unquoted: C[Add Token()] ← ERROR: "got 'PS'"
✗ Brackets unquoted: C[Route [id]] ← ERROR: parser fails
✗ File paths unquoted: Node[/app/page.tsx] ← ERROR: / breaks parsing
✓ ALWAYS QUOTE SPECIAL CHARS: Node["Add Token()"] Node["Route [id]"] Node["/app/page.tsx"]

✓ SUCCESS INDICATORS:
✓ Diagram has appropriate complexity matching the actual system
✓ A developer could implement the system from this diagram alone
✓ All major code elements from codebase context are represented
✓ Edge cases, errors, and alternative paths are documented
✓ Component relationships accurately reflect code dependencies

═══════════════════════════════════════════════════════════════════════════════

IMPORTANT: Generate all content in {language_name} language.

Respond with valid JSON only (no markdown code blocks):"""
    
    return prompt


def build_wiki_modification_prompt(
    wiki_name: str,
    existing_content: Dict,
    modification_prompt: str,
    codebase_context: str,
    language: str = "en"
) -> str:
    """
    Build prompt for modifying existing wiki content.
    
    Args:
        wiki_name: Name/ID of the section to modify
        existing_content: Current wiki section content
        modification_prompt: What to change
        codebase_context: Updated code snippets
        language: Target language code
    
    Returns:
        Prompt string for modifying wiki content
    """
    language_name = get_language_name(language)
    # Extract existing diagram info
    existing_diagram = existing_content.get('diagram', {})
    existing_mermaid = existing_diagram.get('mermaid_code', '')
    existing_type = existing_diagram.get('diagram_type', 'flowchart')
    
    # Extract first line to preserve diagram type
    first_line = existing_mermaid.split('\n')[0].strip() if existing_mermaid else f"{existing_type} TD"
    
    prompt = f"""⚠️ LANGUAGE REQUIREMENT: Generate ALL content in {language_name} language ({language}).
This includes: section descriptions, mermaid node labels, diagram descriptions, node explanations, edge explanations.

You are modifying an existing wiki section for a codebase documentation system.

SECTION NAME: {wiki_name}

CURRENT CONTENT:
- Title: {existing_content.get('section_title', '')}
- Description: {existing_content.get('section_description', '')}
- Diagram Type: {existing_type}
- Number of nodes: {len(existing_content.get('nodes', {}))}
- Number of edges: {len(existing_content.get('edges', {}))}

EXISTING MERMAID DIAGRAM:
{existing_mermaid}

MODIFICATION REQUESTED:
{modification_prompt}

UPDATED CODEBASE CONTEXT:
{codebase_context}

Generate the MODIFIED version. IMPORTANT: Keep the diagram type and structure, only update as requested.

REQUIRED JSON FORMAT:
{{
    "section_id": "{wiki_name}",
    "section_title": "{existing_content.get('section_title', 'Architecture Diagram')}",
    "section_description": "Updated description incorporating the requested changes",
    "diagram_type": "{existing_type}",
    "key_concepts": ["updated", "concepts", "list"],
    "mermaid_code": "MUST start with: {first_line}\\n...rest of diagram...",
    "diagram_description": "Description of changes made",
    "node_explanations": {{
        "nodeId": "Explanation for this node"
    }},
    "edge_explanations": {{
        "nodeA->nodeB": "Explanation for this connection"
    }}
}}

CRITICAL RULES:
1. The mermaid_code MUST start with "{first_line}" to maintain diagram type
2. Preserve existing structure - only add/modify based on the request
3. Ensure all new nodes have explanations
4. Ensure all new edges have explanations
5. Keep valid Mermaid syntax (proper node IDs, edge formats)
6. Use same node naming style as existing diagram

🌐 CRITICAL LANGUAGE REQUIREMENT:
⚠️ ALL content MUST be in {language_name} language ({language}):
- section_description → {language_name}
- diagram_description → {language_name}  
- node_explanations values → {language_name}
- edge_explanations values → {language_name}
- Mermaid node labels → {language_name}

✓ FINAL CHECK: Is EVERYTHING in {language_name}? If not, FIX IT NOW!

Respond with valid JSON only:"""
    
    return prompt


def build_section_rag_query(
    repo_name: str,
    section_title: str,
    section_description: str,
    key_concepts: list = None,
    file_references: str = None,
    diagram_type: str = "flowchart"
) -> str:
    """
    Build a comprehensive RAG query for retrieving section-relevant code.
    
    This query is designed to retrieve the most relevant code files for diagram generation.
    It includes project context, section focus, and specific concepts to look for.
    
    Args:
        repo_name: Name of the repository/project
        section_title: Title of the section being generated
        section_description: Detailed description of what the section covers
        key_concepts: (Optional) List of key concepts that should be included (legacy format)
        file_references: (Optional) Detailed file analysis string (new format from iteration 3)
        diagram_type: Type of diagram being generated (flowchart, sequence, etc.)
    
    Returns:
        Comprehensive RAG query string
    """
    # Build key concepts emphasis (prefer file_references if available)
    concepts_text = ""
    if file_references:
        # New format: use file_references which contains detailed analysis
        # Extract key insights from file_references for focused RAG query
        concepts_text = f" File analysis: {file_references[:300]}..." if len(file_references) > 300 else f" File analysis: {file_references}"
    elif key_concepts and len(key_concepts) > 0:
        # Legacy format: use key_concepts list
        concepts_list = ", ".join(key_concepts[:5])  # Limit to top 5
        concepts_text = f" Focus on these concepts: {concepts_list}."
    
    # Diagram type specific hints for what to look for
    diagram_hints = {
        "flowchart": "Look for process flows, workflows, data transformations, and control logic.",
        "sequence": "Look for interactions between components, API calls, function call sequences, and message passing.",
        "class": "Look for class definitions, inheritance relationships, interfaces, and object structures.",
        "stateDiagram": "Look for state transitions, lifecycle management, state handling, and event flows.",
        "erDiagram": "Look for data models, database schemas, entity relationships, and data structures."
    }
    diagram_hint = diagram_hints.get(diagram_type, "Look for relevant code structures and patterns.")
    
    # Build comprehensive query
    query = (
        f"In the {repo_name} project, explain {section_title}: "
        f"{section_description} "
        f"What are the main components involved? How do they work together? "
        f"What is the implementation? {diagram_hint}"
        f"{concepts_text}"
    )
    
    return query
