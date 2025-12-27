"""
Prompt templates for LLM interactions.

This module contains all prompt templates used for:
- Wiki structure generation
- Wiki page generation
- RAG queries
- Interactive diagram generation
"""

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
                        "enum": ["flowchart", "sequence", "class", "graph", "stateDiagram", "erDiagram"],
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
   - All diagrams MUST use vertical orientation (graph TD, not LR)
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
   - System architecture / component relationships → flowchart or graph
   - Data flow / process workflows → flowchart
   - Class hierarchies / inheritance → classDiagram
   - API call sequences / request-response patterns → sequence diagram
   - State machines / lifecycle → stateDiagram
   - Module dependencies → graph
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
      "diagram_type": "flowchart|sequence|class|graph|stateDiagram|erDiagram",
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
- Show the logical flow from top to bottom""",
        
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
- Show interfaces and abstract classes clearly""",
        
        "graph": """
- MUST start with: graph TD (top-down) or graph LR (left-right)
- Use TD orientation for hierarchies
- Use LR for linear flows only if needed
- Show clear relationships between nodes
- Use different node shapes to indicate different types
- Keep the layout clean and readable""",
        
        "stateDiagram": """
- MUST start with: stateDiagram-v2
- Show all important states
- Clearly mark initial state with [*]
- Show transitions with labeled arrows
- Include conditional transitions where relevant
- Mark final states""",
        
        "erDiagram": """
- MUST start with: erDiagram
- Show entities as tables
- Include key attributes for each entity
- Show relationships clearly (||--o{, etc.)
- Label relationship cardinality
- Focus on the logical data model"""
    }
    
    # Map diagram types to their required Mermaid syntax prefixes
    diagram_syntax = {
        "flowchart": "flowchart TD",
        "sequence": "sequenceDiagram",
        "class": "classDiagram",
        "graph": "graph TD",
        "stateDiagram": "stateDiagram-v2",
        "erDiagram": "erDiagram"
    }
    
    specific_instructions = diagram_instructions.get(diagram_type, diagram_instructions["flowchart"])
    required_syntax = diagram_syntax.get(diagram_type, "flowchart TD")
    
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
⚠️ CRITICAL: Your mermaid_code MUST start with: {required_syntax}
   (NOT "graph TD" if diagram_type is "{diagram_type}")

DIAGRAM REQUIREMENTS:
{specific_instructions}

CRITICAL RULES:
1. Node IDs must be simple alphanumeric (e.g., API, Client, UserService, validateInput)
2. SYNTAX VARIES BY DIAGRAM TYPE:
   - Flowcharts/Graphs: Use Node[Label] or Node["Label"] syntax
   - Sequence diagrams: Use "participant Name as Label" (NOT Name[Label])
   - Class diagrams: Use "class Name" with methods/properties
   - State diagrams: Use state names directly
3. IMPORTANT: Use descriptive, meaningful node/participant IDs that reflect their purpose
   - Good: API, Client, Database, UserService, validateInput, processRequest
   - Bad: A, B, C, Node1, Node2, temp, xyz
4. Make the diagram COMPREHENSIVE - it must fully explain {section_title}
5. Include 8-20 nodes/participants (be thorough, this is the main content)
6. Add meaningful edge labels where it adds clarity
7. Ensure the diagram is syntactically correct Mermaid code for {diagram_type}
8. Since this is the primary content, be detailed and complete

IMPORTANT DIAGRAM QUALITY (CRITICAL FOR DIAGRAM-FIRST WIKI):
- Every node should represent a real component/concept from the codebase
- Relationships should accurately reflect the actual code structure
- Use the RAG context and source snippets as your primary source of truth
- The diagram MUST be comprehensive enough to understand the section WITHOUT additional text
- Think: "Can someone understand this topic fully just from this diagram and explanations?"
- The node and edge explanations will be displayed interactively when clicked

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