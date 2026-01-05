"""
Mermaid diagram parsing utilities.

This module provides functions to parse Mermaid diagrams and extract:
- List of nodes
- Node labels
- List of edges
- Edge relationships
"""

import re
from typing import Dict, List, Tuple, Optional


def sanitize_mermaid_label(label: str) -> str:
    """
    Sanitize a label for use in Mermaid diagrams.
    Escapes special characters that break Mermaid syntax.
    
    Args:
        label: The raw label text
        
    Returns:
        Sanitized label safe for Mermaid
    """
    if not label:
        return label
    
    # Replace problematic characters with HTML entities
    # Parentheses inside brackets break Mermaid syntax
    label = label.replace('(', '#40;')  # HTML entity for (
    label = label.replace(')', '#41;')  # HTML entity for )
    label = label.replace('[', '#91;')  # HTML entity for [
    label = label.replace(']', '#93;')  # HTML entity for ]
    label = label.replace('{', '#123;') # HTML entity for {
    label = label.replace('}', '#125;') # HTML entity for }
    label = label.replace('"', '#quot;')  # HTML entity for "
    
    return label


class MermaidNode:
    """Represents a node in a Mermaid diagram."""
    def __init__(self, node_id: str, label: str = None, shape: str = "rectangle"):
        self.node_id = node_id
        self.label = label or node_id
        self.shape = shape
    
    def __repr__(self):
        return f"MermaidNode(id={self.node_id}, label={self.label}, shape={self.shape})"


class MermaidEdge:
    """Represents an edge/connection in a Mermaid diagram."""
    def __init__(self, source: str, target: str, label: str = None, edge_type: str = "arrow"):
        self.source = source
        self.target = target
        self.label = label
        self.edge_type = edge_type
        self.edge_key = f"{source}->{target}"
    
    def __repr__(self):
        return f"MermaidEdge({self.source} -> {self.target}, label={self.label})"


class MermaidDiagramParser:
    """Parser for Mermaid diagram syntax."""
    
    def __init__(self, mermaid_code: str):
        self.mermaid_code = mermaid_code
        self.nodes: Dict[str, MermaidNode] = {}
        self.edges: List[MermaidEdge] = []
        self.diagram_type = None
        
    def parse(self) -> Tuple[Dict[str, MermaidNode], List[MermaidEdge]]:
        """
        Parse the Mermaid diagram and extract nodes and edges.
        
        Returns:
            Tuple of (nodes_dict, edges_list)
        """
        lines = self.mermaid_code.strip().split('\n')
        
        # Detect diagram type
        if lines:
            first_line = lines[0].strip().lower()
            if first_line.startswith('flowchart'):
                self.diagram_type = 'flowchart'
            elif first_line.startswith('sequencediagram'):
                self.diagram_type = 'sequence'
            elif first_line.startswith('classdiagram'):
                self.diagram_type = 'class'
            elif first_line.startswith('statediagram'):
                self.diagram_type = 'stateDiagram'
            elif first_line.startswith('erdiagram'):
                self.diagram_type = 'erDiagram'
        
        # Parse based on diagram type
        if self.diagram_type == 'flowchart':
            self._parse_graph(lines[1:])  # Skip first line (graph TD/LR)
        elif self.diagram_type == 'sequence':
            self._parse_sequence(lines[1:])
        elif self.diagram_type == 'class':
            self._parse_class(lines[1:])
        elif self.diagram_type == 'erDiagram':
            self._parse_er(lines[1:])
        else:
            # Generic parsing for other types
            self._parse_generic(lines[1:])
        
        return self.nodes, self.edges
    
    def _parse_graph(self, lines: List[str]):
        """Parse flowchart/graph diagram."""
        for line in lines:
            line = line.strip()
            if not line or line.startswith('%%'):  # Skip empty and comments
                continue
            
            # Try to match edge patterns first
            edge_match = self._match_edge(line)
            if edge_match:
                source_id, source_label, edge_type, edge_label, target_id, target_label = edge_match
                
                # Add source node if not exists
                if source_id not in self.nodes:
                    shape = self._detect_shape(source_label) if source_label else "rectangle"
                    self.nodes[source_id] = MermaidNode(
                        source_id, 
                        self._extract_label(source_label) if source_label else source_id,
                        shape
                    )
                
                # Add target node if not exists
                if target_id not in self.nodes:
                    shape = self._detect_shape(target_label) if target_label else "rectangle"
                    self.nodes[target_id] = MermaidNode(
                        target_id,
                        self._extract_label(target_label) if target_label else target_id,
                        shape
                    )
                
                # Add edge
                self.edges.append(MermaidEdge(
                    source_id,
                    target_id,
                    self._extract_label(edge_label) if edge_label else None,
                    edge_type
                ))
            else:
                # Try to match standalone node definition
                node_match = self._match_node(line)
                if node_match:
                    node_id, node_label = node_match
                    if node_id not in self.nodes:
                        shape = self._detect_shape(node_label) if node_label else "rectangle"
                        self.nodes[node_id] = MermaidNode(
                            node_id,
                            self._extract_label(node_label) if node_label else node_id,
                            shape
                        )
    
    def _parse_sequence(self, lines: List[str]):
        """Parse sequence diagram."""
        for line in lines:
            line = line.strip()
            if not line or line.startswith('%%'):
                continue
            
            # Participant definition: participant A as "Label"
            participant_match = re.match(r'participant\s+(\w+)(?:\s+as\s+["\']?([^"\']+)["\']?)?', line)
            if participant_match:
                node_id = participant_match.group(1)
                label = participant_match.group(2) if participant_match.group(2) else node_id
                self.nodes[node_id] = MermaidNode(node_id, label, "actor")
                continue
            
            # Interaction: A->>B: Message
            interaction_match = re.match(r'(\w+)\s*(--?>>?|--?x)\s*(\w+)\s*:\s*(.+)', line)
            if interaction_match:
                source = interaction_match.group(1)
                edge_type = interaction_match.group(2)
                target = interaction_match.group(3)
                message = interaction_match.group(4).strip()
                
                # Add nodes if not defined
                if source not in self.nodes:
                    self.nodes[source] = MermaidNode(source, source, "actor")
                if target not in self.nodes:
                    self.nodes[target] = MermaidNode(target, target, "actor")
                
                self.edges.append(MermaidEdge(source, target, message, edge_type))
    
    def _parse_class(self, lines: List[str]):
        """Parse class diagram."""
        current_class = None
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('%%'):
                continue
            
            # Class definition: class ClassName
            class_match = re.match(r'class\s+(\w+)\s*\{?', line)
            if class_match:
                class_name = class_match.group(1)
                self.nodes[class_name] = MermaidNode(class_name, class_name, "class")
                current_class = class_name
                continue
            
            # Relationship: ClassA --|> ClassB
            rel_match = re.match(r'(\w+)\s*(--|\.\.)(>|o|\*|\+|#)\s*(\w+)\s*:?\s*(.*)?', line)
            if rel_match:
                source = rel_match.group(1)
                edge_type = rel_match.group(2) + rel_match.group(3)
                target = rel_match.group(4)
                label = rel_match.group(5).strip() if rel_match.group(5) else None
                
                if source not in self.nodes:
                    self.nodes[source] = MermaidNode(source, source, "class")
                if target not in self.nodes:
                    self.nodes[target] = MermaidNode(target, target, "class")
                
                self.edges.append(MermaidEdge(source, target, label, edge_type))
    
    def _parse_er(self, lines: List[str]):
        """Parse ER (Entity-Relationship) diagram."""
        in_entity_block = False
        current_entity = None
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('%%'):  # Skip empty and comments
                continue
            
            # Close entity block
            if in_entity_block and line == '}':
                in_entity_block = False
                current_entity = None
                continue
            
            # Skip attribute definitions inside entity blocks
            if in_entity_block:
                continue
            
            # Entity relationship: EntityA ||--o{ EntityB : relationship
            # Patterns: ||--o{, ||--|{, }o--o{, }|..|{, etc.
            rel_pattern = r'(\w+)\s+([|}][|o])?(--+|==+|\.\.+)([o|][{|])\s+(\w+)\s*:\s*(.+)?'
            rel_match = re.match(rel_pattern, line)
            if rel_match:
                source = rel_match.group(1)
                target = rel_match.group(5)
                label = rel_match.group(6).strip() if rel_match.group(6) else None
                
                if source not in self.nodes:
                    self.nodes[source] = MermaidNode(source, source, "entity")
                if target not in self.nodes:
                    self.nodes[target] = MermaidNode(target, target, "entity")
                
                self.edges.append(MermaidEdge(source, target, label, "relationship"))
                continue
            
            # Entity definition with attributes: class EntityName {
            entity_match = re.match(r'class\s+(\w+)\s*\{?', line)
            if entity_match:
                entity_name = entity_match.group(1)
                if entity_name not in self.nodes:
                    self.nodes[entity_name] = MermaidNode(entity_name, entity_name, "entity")
                if not line.endswith('{'):
                    # Single line definition (rare)
                    continue
                in_entity_block = True
                current_entity = entity_name
                continue
    
    def _parse_generic(self, lines: List[str]):
        """Generic parser for other diagram types."""
        # Simple node and edge extraction
        for line in lines:
            line = line.strip()
            if not line or line.startswith('%%'):
                continue
            
            # Extract all word tokens as potential nodes
            tokens = re.findall(r'\w+', line)
            for token in tokens:
                if token not in self.nodes and not token.lower() in ['graph', 'td', 'lr', 'tb']:
                    self.nodes[token] = MermaidNode(token, token, "rectangle")
    
    def _match_edge(self, line: str) -> Optional[Tuple]:
        """
        Match edge pattern: NodeA[Label A] -->|edge label| NodeB[Label B]
        
        Returns:
            Tuple of (source_id, source_label, edge_type, edge_label, target_id, target_label) or None
        """
        # Pattern: NodeA[Label] -->|label| NodeB[Label]
        # Also handles: NodeA --> NodeB, NodeA -->|label| NodeB, etc.
        
        # Complex pattern with all components
        pattern = r'(\w+)(?:\[([^\]]+)\])?\s*(--+>|==+>|\.\.+>|--+o|--+x|-\.-+>)\s*(?:\|([^\|]+)\|)?\s*(\w+)(?:\[([^\]]+)\])?'
        match = re.match(pattern, line)
        
        if match:
            return match.groups()  # (source_id, source_label, edge_type, edge_label, target_id, target_label)
        
        return None
    
    def _match_node(self, line: str) -> Optional[Tuple[str, str]]:
        """
        Match standalone node definition: NodeA[Label]
        
        Returns:
            Tuple of (node_id, node_label) or None
        """
        pattern = r'(\w+)\[([^\]]+)\]'
        match = re.match(pattern, line)
        
        if match:
            return match.group(1), match.group(2)
        
        return None
    
    def _extract_label(self, label_str: str) -> str:
        """Extract clean label from various bracket formats."""
        if not label_str:
            return ""
        
        # Remove outer quotes if present
        label = label_str.strip().strip('"').strip("'")
        # Sanitize the label for safe Mermaid usage
        return sanitize_mermaid_label(label)
    
    def _detect_shape(self, label_str: str) -> str:
        """Detect node shape from label format."""
        if not label_str:
            return "rectangle"
        
        if label_str.startswith('(') and label_str.endswith(')'):
            return "rounded"
        elif label_str.startswith('((') and label_str.endswith('))'):
            return "circle"
        elif label_str.startswith('{') and label_str.endswith('}'):
            return "diamond"
        elif label_str.startswith('[[') and label_str.endswith(']]'):
            return "subroutine"
        elif label_str.startswith('[(') and label_str.endswith(')]'):
            return "cylinder"
        else:
            return "rectangle"


def parse_mermaid_diagram(mermaid_code: str) -> Dict:
    """
    Parse a Mermaid diagram and extract structured information.
    
    Args:
        mermaid_code: The Mermaid diagram code
    
    Returns:
        Dictionary containing:
        - nodes: List of node objects
        - edges: List of edge objects
        - node_list: Simple list of node IDs
        - edge_list: Simple list of edge connections
    """
    parser = MermaidDiagramParser(mermaid_code)
    nodes_dict, edges_list = parser.parse()
    
    return {
        "diagram_type": parser.diagram_type,
        "nodes": {node_id: {
            "id": node.node_id,
            "label": node.label,
            "shape": node.shape
        } for node_id, node in nodes_dict.items()},
        "edges": [{
            "source": edge.source,
            "target": edge.target,
            "label": edge.label,
            "type": edge.edge_type,
            "key": edge.edge_key
        } for edge in edges_list],
        "node_list": list(nodes_dict.keys()),
        "edge_list": [edge.edge_key for edge in edges_list]
    }


def validate_mermaid_syntax(mermaid_code: str) -> Tuple[bool, str]:
    """
    Validate Mermaid diagram syntax.
    
    Args:
        mermaid_code: The Mermaid diagram code
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        lines = mermaid_code.strip().split('\n')
        
        if not lines:
            return False, "Empty diagram"
        
        first_line = lines[0].strip().lower()
        valid_types = ['flowchart', 'sequencediagram', 'classdiagram', 
                      'statediagram', 'erdiagram', 'gantt', 'pie', 'journey']
        
        if not any(first_line.startswith(t) for t in valid_types):
            return False, f"Invalid diagram type. First line: {first_line}"
        
        # Try to parse
        parser = MermaidDiagramParser(mermaid_code)
        nodes, edges = parser.parse()
        
        if not nodes and not edges:
            return False, "No nodes or edges found in diagram"
        
        return True, "Valid Mermaid syntax"
        
    except Exception as e:
        return False, f"Parsing error: {str(e)}"