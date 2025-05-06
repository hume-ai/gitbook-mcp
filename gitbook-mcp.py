# GitBook Model Context Provider (MCP) Server
# A server that provides context from your codebase to GitBook documentation

import os
import re
import json
import glob
import logging
import argparse
import threading
from typing import Dict, List, Any, Optional, Union
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
import hashlib

# Web server dependencies
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

# Code parsing dependencies
import ast
import inspect
import importlib
import importlib.util
import sys

# For markdown parsing (if needed)
import markdown
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gitbook-mcp")

@dataclass
class CodeEntity:
    """Base class for code entities extracted from source files."""
    name: str
    filepath: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None
    code_snippet: Optional[str] = None
    entity_type: str = "unknown"
    hash: str = field(default="", init=False)
    
    def __post_init__(self):
        if self.code_snippet:
            self.hash = hashlib.md5(self.code_snippet.encode()).hexdigest()

@dataclass
class FunctionEntity(CodeEntity):
    """Represents a function in the codebase."""
    parameters: List[Dict[str, str]] = field(default_factory=list)
    return_type: Optional[str] = None
    entity_type: str = "function"

@dataclass
class ClassEntity(CodeEntity):
    """Represents a class in the codebase."""
    methods: List[FunctionEntity] = field(default_factory=list)
    properties: List[Dict[str, Any]] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    entity_type: str = "class"

@dataclass
class ModuleEntity(CodeEntity):
    """Represents a module in the codebase."""
    functions: List[FunctionEntity] = field(default_factory=list)
    classes: List[ClassEntity] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    entity_type: str = "module"

class CodeIndexer:
    """Indexes code entities from Python source files."""
    
    def __init__(self, root_path: str, exclude_patterns: List[str] = None):
        self.root_path = os.path.abspath(root_path)
        self.exclude_patterns = exclude_patterns or ["__pycache__", "*.pyc", ".*", "venv", "env"]
        self.modules: Dict[str, ModuleEntity] = {}
        self.all_entities: Dict[str, CodeEntity] = {}
        
    def index_codebase(self):
        """Index all Python files in the codebase."""
        logger.info(f"Indexing codebase at: {self.root_path}")
        python_files = self._find_python_files()
        logger.info(f"Found {len(python_files)} Python files to index")
        
        for file_path in python_files:
            try:
                self._index_file(file_path)
            except Exception as e:
                logger.error(f"Error indexing file {file_path}: {e}")
                
        logger.info(f"Indexing complete. Found {len(self.all_entities)} code entities")
    
    def _find_python_files(self) -> List[str]:
        """Find all Python files in the root path, excluding patterns."""
        python_files = []
        
        for root, dirs, files in os.walk(self.root_path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not any(
                re.match(pattern.replace('*', '.*'), d) 
                for pattern in self.exclude_patterns
            )]
            
            for file in files:
                if file.endswith('.py'):
                    full_path = os.path.join(root, file)
                    # Skip excluded files
                    if not any(re.match(pattern.replace('*', '.*'), file) 
                              for pattern in self.exclude_patterns):
                        python_files.append(full_path)
        
        return python_files
    
    def _index_file(self, file_path: str):
        """Index a single Python file."""
        logger.debug(f"Indexing file: {file_path}")
        rel_path = os.path.relpath(file_path, self.root_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        try:
            module_ast = ast.parse(file_content)
            module_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # Extract module-level docstring
            module_docstring = ast.get_docstring(module_ast)
            
            # Create module entity
            module = ModuleEntity(
                name=module_name,
                filepath=rel_path,
                line_start=1,
                line_end=len(file_content.splitlines()),
                docstring=module_docstring,
                code_snippet=file_content
            )
            
            # Extract imports
            module.imports = self._extract_imports(module_ast)
            
            # Process classes and functions
            for node in module_ast.body:
                if isinstance(node, ast.ClassDef):
                    class_entity = self._process_class(node, file_path, file_content)
                    module.classes.append(class_entity)
                    self.all_entities[class_entity.name] = class_entity
                    
                elif isinstance(node, ast.FunctionDef):
                    func_entity = self._process_function(node, file_path, file_content)
                    module.functions.append(func_entity)
                    self.all_entities[func_entity.name] = func_entity
            
            self.modules[module_name] = module
            self.all_entities[module_name] = module
            
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
    
    def _extract_imports(self, module_ast) -> List[str]:
        """Extract import statements from module AST."""
        imports = []
        for node in module_ast.body:
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.append(f"import {name.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for name in node.names:
                    imports.append(f"from {module} import {name.name}")
        return imports
    
    def _process_class(self, node: ast.ClassDef, file_path: str, file_content: str) -> ClassEntity:
        """Process a class definition AST node."""
        source_lines = file_content.splitlines()
        class_start = node.lineno
        class_end = self._find_node_end(node, source_lines)
        
        # Extract class code
        class_code = "\n".join(source_lines[class_start-1:class_end])
        
        # Extract base classes
        base_classes = [self._get_name_from_expr(base) for base in node.bases]
        
        class_entity = ClassEntity(
            name=node.name,
            filepath=os.path.relpath(file_path, self.root_path),
            line_start=class_start,
            line_end=class_end,
            docstring=ast.get_docstring(node),
            code_snippet=class_code,
            base_classes=base_classes
        )
        
        # Process methods
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_entity = self._process_function(item, file_path, file_content)
                class_entity.methods.append(method_entity)
                # Also add to global entity list with qualified name
                qualified_name = f"{node.name}.{item.name}"
                method_entity.name = qualified_name  # Update name to qualified name
                self.all_entities[qualified_name] = method_entity
        
        return class_entity
    
    def _process_function(self, node: ast.FunctionDef, file_path: str, file_content: str) -> FunctionEntity:
        """Process a function definition AST node."""
        source_lines = file_content.splitlines()
        func_start = node.lineno
        func_end = self._find_node_end(node, source_lines)
        
        # Extract function code
        func_code = "\n".join(source_lines[func_start-1:func_end])
        
        # Extract parameters
        parameters = []
        for arg in node.args.args:
            param = {"name": arg.arg}
            if arg.annotation:
                param["type"] = self._get_name_from_expr(arg.annotation)
            parameters.append(param)
        
        # Extract return type
        return_type = None
        if node.returns:
            return_type = self._get_name_from_expr(node.returns)
        
        return FunctionEntity(
            name=node.name,
            filepath=os.path.relpath(file_path, self.root_path),
            line_start=func_start,
            line_end=func_end,
            docstring=ast.get_docstring(node),
            code_snippet=func_code,
            parameters=parameters,
            return_type=return_type
        )
    
    def _find_node_end(self, node, source_lines) -> int:
        """Find the last line number of a node."""
        # This is a simplistic approach, more robust would be to use ast.unparse in Python 3.9+
        for i, child in enumerate(ast.iter_child_nodes(node)):
            if hasattr(child, 'lineno'):
                last_child_end = self._find_node_end(child, source_lines)
                if i == len(list(ast.iter_child_nodes(node))) - 1:
                    return last_child_end
        
        # If no children with line numbers, use node's line number
        return node.lineno
    
    def _get_name_from_expr(self, expr) -> str:
        """Extract name from an expression node."""
        if isinstance(expr, ast.Name):
            return expr.id
        elif isinstance(expr, ast.Attribute):
            return f"{self._get_name_from_expr(expr.value)}.{expr.attr}"
        elif isinstance(expr, ast.Subscript):
            base = self._get_name_from_expr(expr.value)
            if isinstance(expr.slice, ast.Index):  # Python 3.8 and before
                if hasattr(expr.slice, 'value'):
                    if isinstance(expr.slice.value, ast.Name):
                        return f"{base}[{expr.slice.value.id}]"
                    else:
                        return f"{base}[...]"
            else:  # Python 3.9+
                return f"{base}[...]"
        else:
            return str(type(expr).__name__)
    
    def search_entities(self, query: str, entity_type: Optional[str] = None) -> List[CodeEntity]:
        """Search for code entities matching the query."""
        results = []
        query_lower = query.lower()
        
        for entity in self.all_entities.values():
            if entity_type and entity.entity_type != entity_type:
                continue
                
            # Search in name
            if query_lower in entity.name.lower():
                results.append(entity)
                continue
                
            # Search in docstring
            if entity.docstring and query_lower in entity.docstring.lower():
                results.append(entity)
                continue
                
            # Search in code snippet
            if entity.code_snippet and query_lower in entity.code_snippet.lower():
                results.append(entity)
                continue
        
        return results
    
    def get_entity_by_name(self, name: str) -> Optional[CodeEntity]:
        """Get a code entity by its name."""
        return self.all_entities.get(name)
    
    def get_entity_relationships(self, entity_name: str) -> Dict[str, List[str]]:
        """Get relationships for a given entity."""
        entity = self.all_entities.get(entity_name)
        if not entity:
            return {"imports": [], "imported_by": [], "uses": [], "used_by": []}
        
        relationships = {
            "imports": [],
            "imported_by": [],
            "uses": [],
            "used_by": []
        }
        
        # For module entities, find imports/imported_by relationships
        if isinstance(entity, ModuleEntity):
            for other_module in self.modules.values():
                # Check if other module imports this module
                for import_stmt in other_module.imports:
                    if entity.name in import_stmt:
                        relationships["imported_by"].append(other_module.name)
            
            # This module's imports
            for import_stmt in entity.imports:
                for other_module_name in self.modules:
                    if other_module_name in import_stmt:
                        relationships["imports"].append(other_module_name)
        
        # For class/function entities, find usage relationships
        entity_name_parts = entity.name.split(".")
        simple_name = entity_name_parts[-1]
        
        for other_entity in self.all_entities.values():
            if other_entity.name == entity.name:
                continue
                
            # Check if other entity uses this entity
            if other_entity.code_snippet and simple_name in other_entity.code_snippet:
                # Simple heuristic - could be improved
                pattern = r'\b' + re.escape(simple_name) + r'\b'
                if re.search(pattern, other_entity.code_snippet):
                    relationships["used_by"].append(other_entity.name)
            
            # Check if this entity uses other entity
            other_simple_name = other_entity.name.split(".")[-1]
            if entity.code_snippet and other_simple_name in entity.code_snippet:
                pattern = r'\b' + re.escape(other_simple_name) + r'\b'
                if re.search(pattern, entity.code_snippet):
                    relationships["uses"].append(other_entity.name)
        
        return relationships


class DocParser:
    """Parse documentation files for context enhancement."""
    
    def __init__(self, docs_path: str):
        self.docs_path = os.path.abspath(docs_path)
        self.doc_files = {}
        
    def index_docs(self):
        """Index all documentation files."""
        logger.info(f"Indexing documentation at: {self.docs_path}")
        md_files = glob.glob(f"{self.docs_path}/**/*.md", recursive=True)
        
        for file_path in md_files:
            rel_path = os.path.relpath(file_path, self.docs_path)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title from first heading or filename
            title = os.path.splitext(os.path.basename(file_path))[0]
            heading_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if heading_match:
                title = heading_match.group(1)
            
            self.doc_files[rel_path] = {
                "path": rel_path,
                "title": title,
                "content": content
            }
        
        logger.info(f"Indexed {len(self.doc_files)} documentation files")
    
    def search_docs(self, query: str) -> List[Dict[str, Any]]:
        """Search documentation for the given query."""
        results = []
        query_lower = query.lower()
        
        for file_info in self.doc_files.values():
            content = file_info["content"]
            
            if query_lower in content.lower():
                # Find context around the match
                lines = content.split('\n')
                match_context = []
                
                for i, line in enumerate(lines):
                    if query_lower in line.lower():
                        start = max(0, i - 2)
                        end = min(len(lines), i + 3)
                        context = '\n'.join(lines[start:end])
                        match_context.append({
                            "line": i + 1,
                            "context": context
                        })
                
                results.append({
                    "path": file_info["path"],
                    "title": file_info["title"],
                    "matches": match_context
                })
        
        return results
    
    def extract_code_references(self, path: str) -> List[str]:
        """Extract code references from a documentation file."""
        if path not in self.doc_files:
            return []
        
        content = self.doc_files[path]["content"]
        references = []
        
        # Look for code references in various formats
        # Standard inline code: `function_name`
        inline_code = re.findall(r'`([^`]+)`', content)
        references.extend(inline_code)
        
        # Code blocks with language specifier
        code_blocks = re.findall(r'```python\s+(.*?)\s+```', content, re.DOTALL)
        for block in code_blocks:
            # Extract potential function/class names from code blocks
            func_matches = re.findall(r'def\s+(\w+)', block)
            class_matches = re.findall(r'class\s+(\w+)', block)
            references.extend(func_matches)
            references.extend(class_matches)
        
        return references


class GitBookMCPServer:
    """Main MCP server for GitBook integration."""
    
    def __init__(self, code_path: str, docs_path: str = None, port: int = 5000,
                 gitbook_space_id: str = None, gitbook_token: str = None):
        self.port = port
        self.code_indexer = CodeIndexer(code_path)
        self.doc_parser = DocParser(docs_path) if docs_path else None
        self.gitbook_space_id = gitbook_space_id
        self.gitbook_token = gitbook_token
        self.app = Flask(__name__)
        CORS(self.app)
        self._setup_routes()
        
        # For code updates tracking
        self.last_indexed = 0
        self.index_interval = 300  # 5 minutes
        
    def _setup_routes(self):
        """Set up API routes."""
        @self.app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({"status": "ok", "version": "1.0.0"})
        
        @self.app.route('/search', methods=['GET'])
        def search():
            query = request.args.get('q', '')
            entity_type = request.args.get('type')
            
            if not query:
                return jsonify({"error": "Query parameter 'q' is required"}), 400
            
            # Search code entities
            code_results = self.code_indexer.search_entities(query, entity_type)
            code_results_json = [asdict(entity) for entity in code_results]
            
            # Search docs if available
            doc_results = []
            if self.doc_parser:
                doc_results = self.doc_parser.search_docs(query)
            
            return jsonify({
                "code_results": code_results_json,
                "doc_results": doc_results
            })
        
        @self.app.route('/entity/<path:entity_name>', methods=['GET'])
        def get_entity(entity_name):
            entity = self.code_indexer.get_entity_by_name(entity_name)
            if not entity:
                return jsonify({"error": f"Entity '{entity_name}' not found"}), 404
            
            # Get entity relationships
            relationships = self.code_indexer.get_entity_relationships(entity_name)
            
            return jsonify({
                "entity": asdict(entity),
                "relationships": relationships
            })
        
        @self.app.route('/sync', methods=['POST'])
        def sync_to_gitbook():
            """Sync code info to GitBook using their API."""
            if not self.gitbook_space_id or not self.gitbook_token:
                return jsonify({"error": "GitBook API credentials not configured"}), 400
            
            try:
                # Prepare data for GitBook sync
                entities_data = {}
                for entity in self.code_indexer.all_entities.values():
                    if entity.entity_type == "module":  # Only sync modules for now
                        entities_data[entity.name] = {
                            "name": entity.name,
                            "type": entity.entity_type,
                            "filepath": entity.filepath,
                            "docstring": entity.docstring or "",
                            "classes": [c.name for c in getattr(entity, "classes", [])],
                            "functions": [f.name for f in getattr(entity, "functions", [])]
                        }
                
                # Example GitBook integration - would need to be adapted to actual API
                gitbook_url = f"https://api.gitbook.com/v1/spaces/{self.gitbook_space_id}/content"
                headers = {
                    "Authorization": f"Bearer {self.gitbook_token}",
                    "Content-Type": "application/json"
                }
                
                response = requests.post(
                    gitbook_url,
                    headers=headers,
                    json={"content": entities_data}
                )
                
                if response.status_code == 200:
                    return jsonify({"status": "success", "message": "Synced to GitBook"})
                else:
                    return jsonify({
                        "status": "error", 
                        "message": f"Failed to sync: {response.status_code} - {response.text}"
                    }), 400
                    
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        
        @self.app.route('/webhook', methods=['POST'])
        def gitbook_webhook():
            """Handle webhook events from GitBook."""
            event_data = request.json
            event_type = event_data.get('type')
            
            if event_type == 'page.updated':
                page_id = event_data.get('page', {}).get('id')
                # Process page update to enhance with code context
                # This would require additional GitBook API calls to get page content
                return jsonify({"status": "received", "action": "page.updated"})
                
            elif event_type == 'comment.created':
                comment = event_data.get('comment', {})
                # Process code questions in comments
                return jsonify({"status": "received", "action": "comment.created"})
                
            return jsonify({"status": "received", "action": "unhandled"})
    
    def start(self):
        """Start the MCP server."""
        # Index code and docs
        self.code_indexer.index_codebase()
        if self.doc_parser:
            self.doc_parser.index_docs()
            
        self.last_indexed = time.time()
        
        # Start background indexing thread
        indexer_thread = threading.Thread(target=self._background_indexing)
        indexer_thread.daemon = True
        indexer_thread.start()
        
        # Start Flask server
        logger.info(f"Starting MCP server on http://localhost:{self.port}")
        self.app.run(host='0.0.0.0', port=self.port)
    
    def _background_indexing(self):
        """Background thread to periodically re-index code."""
        while True:
            time.sleep(60)  # Check every minute
            now = time.time()
            if now - self.last_indexed > self.index_interval:
                logger.info("Performing background re-indexing of code")
                self.code_indexer.index_codebase()
                if self.doc_parser:
                    self.doc_parser.index_docs()
                self.last_indexed = now


def main():
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="GitBook Model Context Provider Server")
    parser.add_argument("--code-path", required=True, help="Path to the codebase root")
    parser.add_argument("--docs-path", help="Path to documentation files (optional)")
    parser.add_argument("--port", type=int, default=5000, help="Server port (default: 5000)")
    parser.add_argument("--gitbook-space", help="GitBook Space ID for API integration (optional)")
    parser.add_argument("--gitbook-token", help="GitBook API token (optional)")
    
    args = parser.parse_args()
    
    server = GitBookMCPServer(
        code_path=args.code_path,
        docs_path=args.docs_path,
        port=args.port,
        gitbook_space_id=args.gitbook_space,
        gitbook_token=args.gitbook_token
    )
    
    server.start()


if __name__ == "__main__":
    main()