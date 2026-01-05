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
        'zh-tw': 'Traditional Chinese (繁體中文)',
        'es': 'Spanish (Español)',
        'kr': 'Korean (한국어)',
        'vi': 'Vietnamese (Tiếng Việt)',
        'pt-br': 'Brazilian Portuguese (Português Brasileiro)',
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
        List of query strings
    """
    return [
        f"What is {page_title}? {page_description}",
        f"How does {page_title} work? Explain the implementation details.",
        f"What are the key components and functions related to {page_title}?",
        f"What are the data structures, classes, or APIs for {page_title}?",
        f"Show code examples and usage patterns for {page_title}."
    ]


def build_diagram_sections_prompt(
    repo_name: str,
    rag_context: str,
    language: str
) -> str:
    """
    Build prompt to identify diagram sections for a codebase.
    
    This is Step 1: Analyze codebase and identify diagram-worthy sections.
    
    IMPORTANT: This is for a diagram-first wiki where diagrams ARE the main representation.
    The wiki is composed of interactive diagrams that explain the codebase visually.
    
    Args:
        repo_name: Name of the repository/codebase
        rag_context: RAG-retrieved context from codebase analysis
        language: Target language code
    
    Returns:
        Prompt string for LLM to identify diagram sections
    """
    language_name = get_language_name(language)
    
    prompt = f"""You are an expert technical writer creating a DIAGRAM-FIRST wiki for the "{repo_name}" codebase.

🎯 CRITICAL CONCEPT: This wiki is MADE OF DIAGRAMS. Diagrams are the PRIMARY REPRESENTATION, not supplements.
You will analyze this codebase and identify the key aspects that should be visualized as interactive diagrams.

CODEBASE CONTEXT:
{rag_context}

Your task is to identify distinct diagram sections that together provide a complete visual understanding of this codebase.

IMPORTANT GUIDELINES:
1. Analyze the COMPLEXITY and SCOPE of the codebase to determine the appropriate number of diagrams
   - Simple projects (single module, <5 files): 2-3 diagrams
   - Medium projects (multiple modules, 5-20 files): 3-5 diagrams  
   - Complex projects (layered architecture, >20 files): 5-8 diagrams
   - Let the codebase structure guide you - don't force a fixed number

2. Each diagram section represents ONE focused aspect that MUST be visualized
   - System architecture / component relationships/ moudle dependencies → flowchart
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

4. 🎯 CRITICAL: Use SPECIFIC component/class/function names from the CODEBASE CONTEXT above
   - BAD: "API calls between client and server" (too generic)
   - GOOD: "FastAPI requests through WikiGenerator to Ollama LLM" (specific to this codebase)
   - Include actual class names, module names, function names from the context
   - Make section_description reference concrete components, not abstract concepts

5. Together, these diagrams should fully explain "{repo_name}" - no additional text needed

Return your analysis in the following JSON format:

{{
  "sections": [
    {{
      "section_id": "unique-identifier",
      "section_title": "Clear, concise title",
      "section_description": "What this section explains, using SPECIFIC component names from the codebase (2-3 sentences)",
      "diagram_type": "flowchart|sequence|class|stateDiagram|erDiagram",
      "key_concepts": ["concept1", "concept2", "concept3"],
      "importance": "high|medium|low"
    }}
  ]
}}

IMPORTANT: Return ONLY valid JSON, no markdown code blocks, no explanations.
Generate the analysis in {language_name} language.

Analyze now:"""
    
    return prompt


def build_single_diagram_prompt(
    section_title: str,
    section_description: str,
    diagram_type: str,
    key_concepts: list,
    rag_context: str,
    retrieved_sources: str,
    language: str
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
        key_concepts: List of key concepts to include
        rag_context: RAG-retrieved context
        retrieved_sources: Retrieved source code snippets
        language: Target language code
    
    Returns:
        Prompt string for LLM to generate diagram
    """
    language_name = get_language_name(language)
    
    # Diagram-specific instructions
    diagram_instructions = {
        "flowchart": """
- MUST start with: flowchart TD (top-down) or flowchart LR (left-right)
- Start with entry points, show decision nodes, end with outcomes
- Use rectangles for processes, diamonds for decisions, rounded for start/end
- Keep node labels concise (3-5 words max)
- Every node must represent a real component/concept from the codebase, no vague concepts or placeholders
- Can use subgraphs to group related nodes if this adds clarity
- Critical! Wrap labels with special chars in quotes!
  * No A[Recall@10] (run into syntax errors), use A["Recall@10"] instead
  * Alternative: Replace special chars with words: A[Recall at 10] (also correct)
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
- Example:
  sequenceDiagram
      participant Client
      participant API as API Gateway
      Client->>API: Request
      API-->>Client: Response""",
        
        "class": """
- MUST start with: classDiagram
- Show main classes and their relationships
- Include key methods and properties
- Use inheritance (--|>) and composition (--o) correctly
- Keep class definitions focused on important members
- Show interfaces and abstract classes clearly
- If you want to add notes, they must be single-line using: note for MyClass \"This is a note for a class\"
- DON'T use multi-line notes as they break Mermaid syntax!""",
        
        "stateDiagram": """
- MUST start with: stateDiagram-v2
- Show all important states
- Clearly mark initial state with [*]
- Show transitions with labeled arrows
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
    
    prompt = f"""You are an expert at creating clear, informative Mermaid diagrams for a DIAGRAM-FIRST WIKI.

🎯 CRITICAL: This diagram is the PRIMARY CONTENT for this section, not a supplement.
The wiki is composed of interactive diagrams with explanations - the diagrams ARE the documentation.

CONTEXT:
- Section: {section_title}
- Section focus: {section_description}
- Diagram type: {diagram_type}
- Key concepts to include: {', '.join(key_concepts)}

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

Return your response in the following JSON format:

{{
  "mermaid_code": "{required_syntax}\\n  Client[Client Request]\\n  API[API Layer]\\n  ...",
  "diagram_description": "Brief 2-3 sentence explanation of what this diagram shows",
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

Generate the diagram in {language_name} language.

Create the diagram now:"""
    
    return prompt

def build_diagram_correction_prompt(
    section_title: str,
    section_description: str,
    diagram_type: str,
    key_concepts: list,
    rag_context: str,
    retrieved_sources: str,
    corrupted_diagram: str,
    error_message: str,
    language: str
) -> str:
    """
    Build prompt to fix a corrupted Mermaid diagram that failed to render.
    
    This prompt provides explicit error correction context to help the LLM
    understand what went wrong and generate a valid diagram.
    
    Args:
        section_title: Title of the section
        section_description: Description of the section
        diagram_type: Type of diagram
        key_concepts: Key concepts to include
        rag_context: RAG-retrieved context
        retrieved_sources: Retrieved source code snippets
        corrupted_diagram: The broken Mermaid code
        error_message: The error from Mermaid renderer
        language: Target language code
    
    Returns:
        Prompt string for LLM to fix the diagram
    """
    language_name = get_language_name(language)
    key_concepts_str = "\n".join([f"  - {concept}" for concept in key_concepts])
    
    # Use the same diagram instructions from build_single_diagram_prompt
    diagram_instructions = {
        "flowchart": """- MUST start with: flowchart TD (top-down) or flowchart LR (left-right)
- Use rectangles for processes, diamonds for decisions, rounded for start/end
- Keep node labels concise (3-5 words max)
- Critical! Wrap labels with special chars in quotes: A["Recall@10"] not A[Recall@10]
- Or replace special chars with words: A[Recall at 10]
- STYLING: Use minimal coloring - only emphasize critical nodes""",
        "sequence": """- MUST start with: sequenceDiagram
- Format: participant Name
- Show message flow: Actor->>Target: message
- Use activate/deactivate for lifelines
- CRITICAL: "return" is NOT valid syntax in Mermaid! Instead use Actor-->>Target: message or Note
- If ending early, just use deactivate Actor (NO bare "return" statement!)""",
        "class": """- MUST start with: classDiagram
- Define classes: class ClassName { +method() }
- Show relationships: Parent <|-- Child""",
        "stateDiagram": """- MUST start with: stateDiagram-v2
- Define states: state "Name" as id
- Show transitions: id1 --> id2: event""",
        "erDiagram": """- MUST start with: erDiagram
- Define entities: EntityName { type attribute }
- CRITICAL: Do NOT use 'class' keyword (that's for class diagrams!)
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
        "**Duplicate node IDs** → Make all IDs unique"
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
     ❌ WRONG:
     ```
     alt Valid
       A->>B: success
     else Invalid
       A->>B: error
       deactivate A  ← inside else block
     end
     deactivate A  ← after end (DOUBLE!)
     ```
     
     ✅ RIGHT:
     ```
     alt Valid
       A->>B: success
     else Invalid
       A->>B: error
     end
     deactivate A  ← Only ONE, after end
     ```
   
   STEP 5: VERIFY BEFORE RETURNING - For each participant:
     - activate count MUST EQUAL deactivate count
     - If not equal, go back to STEP 3 and fix it
     
   ⚠️ CRITICAL: IF YOU RETURN CODE WHERE COUNTS ARE NOT EQUAL, YOU HAVE FAILED!
   DO NOT RETURN THE SAME BROKEN CODE. YOUR FIXED CODE MUST HAVE EQUAL COUNTS FOR ALL PARTICIPANTS."""
    ]
    
    common_errors_class = [
        "**Invalid relationship syntax** → Use <|-- for inheritance, *-- for composition",
        "**Missing class definition** → Define class before using: class ClassName",
        "**Invalid method syntax** → Use +publicMethod() or -privateMethod()"
    ]
    
    common_errors_state = [
        "**Invalid state transitions** → Use --> for transitions with optional labels",
        "**Unclosed state blocks** → Ensure composite states have proper nesting"
    ]
    
    common_errors_er = [
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
    wiki_items: Optional[Dict[str, str]] = None
) -> str:
    """
    Build prompt for analyzing whether a user's request is a question or modification request.
    
    Args:
        user_prompt: User's request
        wiki_context: Existing wiki content from RAG
        codebase_context: Relevant codebase snippets
        wiki_items: Optional dict of {wiki_name: question} pairs
    
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
    diagram_type: str = None
) -> str:
    """
    Build prompt for creating a new wiki section.
    
    Args:
        wiki_name: Name/ID of the new section
        creation_prompt: Detailed requirements from problem analysis
        codebase_context: Relevant code snippets
        diagram_type: Optional diagram type ('auto' or specific type)
    
    Returns:
        Prompt string for creating new wiki content
    """
    # Determine diagram type instruction
    if diagram_type and diagram_type != 'auto':
        diagram_type_instruction = f'You MUST use diagram type: {diagram_type}'
        diagram_type_field = f'"diagram_type": "{diagram_type}",'
    else:
        diagram_type_instruction = 'Choose the most appropriate diagram type for the content'
        diagram_type_field = '"diagram_type": "flowchart|sequence|class|stateDiagram|erDiagram",'
    
    prompt = f"""You are creating a new wiki section for a codebase documentation system.

SECTION NAME: {wiki_name}

REQUIREMENTS:
{creation_prompt}

RELEVANT CODEBASE:
{codebase_context}

Generate a diagram section with the following JSON structure:
{{
    "section_id": "{wiki_name}",
    "section_title": "Human-readable title",
    "section_description": "What this diagram explains",
    {diagram_type_field}
    "key_concepts": ["concept1", "concept2", "concept3"],
    "mermaid_code": "Complete Mermaid diagram code here",
    "diagram_description": "What the diagram shows",
    "node_explanations": {{
        "nodeId": "What this component does"
    }},
    "edge_explanations": {{
        "source->target": "What this relationship means"
    }}
}}

Guidelines:
- {diagram_type_instruction}
- Include 5-10 key concepts
- Generate valid Mermaid syntax
- Provide detailed explanations for all nodes and edges
- Base content on the codebase context provided
- STYLING RULES (Professional Style):
  * Use MINIMAL and SELECTIVE coloring - most nodes should use default styling
  * Apply colors ONLY to emphasize critical nodes (entry points, error states, key decision points)
  * Use a consistent, muted color palette:
    - Entry/Start points: style X fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    - Error/Critical states: style Y fill:#ffebee,stroke:#c62828,stroke-width:2px
    - Success/End states: style Z fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    - Key decision points: style W fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
  * NO random rainbow colors (avoid #f0f8ff, #ffe4b5, #98fb98, #ff6347, #87ceeb, #9370db, etc.)
  * Leave most nodes unstyled for a clean, professional appearance

Respond with valid JSON only:"""
    
    return prompt


def build_wiki_modification_prompt(
    wiki_name: str,
    existing_content: Dict,
    modification_prompt: str,
    codebase_context: str
) -> str:
    """
    Build prompt for modifying existing wiki content.
    
    Args:
        wiki_name: Name/ID of the section to modify
        existing_content: Current wiki section content
        modification_prompt: What to change
        codebase_context: Updated code snippets
    
    Returns:
        Prompt string for modifying wiki content
    """
    # Extract existing diagram info
    existing_diagram = existing_content.get('diagram', {})
    existing_mermaid = existing_diagram.get('mermaid_code', '')
    existing_type = existing_diagram.get('diagram_type', 'flowchart')
    
    # Extract first line to preserve diagram type
    first_line = existing_mermaid.split('\n')[0].strip() if existing_mermaid else f"{existing_type} TD"
    
    prompt = f"""You are modifying an existing wiki section for a codebase documentation system.

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

Respond with valid JSON only:"""
    
    return prompt


def build_section_rag_query(
    repo_name: str,
    section_title: str,
    section_description: str,
    key_concepts: list,
    diagram_type: str
) -> str:
    """
    Build a comprehensive RAG query for retrieving section-relevant code.
    
    This query is designed to retrieve the most relevant code files for diagram generation.
    It includes project context, section focus, and specific concepts to look for.
    
    Args:
        repo_name: Name of the repository/project
        section_title: Title of the section being generated
        section_description: Detailed description of what the section covers
        key_concepts: List of key concepts that should be included
        diagram_type: Type of diagram being generated (flowchart, sequence, etc.)
    
    Returns:
        Comprehensive RAG query string
    """
    # Build key concepts emphasis
    concepts_text = ""
    if key_concepts and len(key_concepts) > 0:
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
