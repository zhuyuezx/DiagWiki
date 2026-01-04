import os
import logging
from const.const import Const
from adalflow.core.types import Document
import tiktoken

logger = logging.getLogger(__name__)

class RepoUtil:
    """Utility class for repository operations"""
    MAX_TOKEN_LIMIT = Const.MAX_TOKEN_LIMIT

    @staticmethod
    def build_tree(current_path):
        """Build a tree structure of a directory
        
        Args:
            current_path: Path to build tree from
        
        Returns:
            Dict representing directory tree, or None if path should be skipped
        """
        basename = os.path.basename(current_path)
        
        # Skip directories that should be excluded
        if os.path.isdir(current_path) and RepoUtil.should_skip_directory(basename):
            return None
        
        # Skip hidden files
        if basename.startswith('.'):
            return None
            
        if os.path.isdir(current_path):
            children = []
            for item in os.listdir(current_path):
                item_path = os.path.join(current_path, item)
                child_tree = RepoUtil.build_tree(item_path)
                if child_tree is not None:
                    children.append(child_tree)
            return {
                "name": basename,
                "type": "directory",
                "children": children
            }
        else:
            return {
                "name": basename,
                "type": "file"
            }

    @staticmethod
    def is_valuable_file(file_name: str, allowed_extensions=None) -> bool:
        """Check if a file is valuable based on its extension
        
        Args:
            file_name: Name of the file to check
            allowed_extensions: List of allowed extensions, or None for default (CODE + DOC)
        """
        # Skip known large files that shouldn't be embedded
        large_file_patterns = ['package-lock.json', 'yarn.lock', 'poetry.lock', 'Cargo.lock', 'package.json.lock']
        if file_name in large_file_patterns:
            return False
        
        _, ext = os.path.splitext(file_name)
        if allowed_extensions is None:
            return ext in Const.CODE_EXTENSIONS or ext in Const.DOC_EXTENSIONS
        return ext in allowed_extensions
    
    @staticmethod
    def should_skip_directory(dir_name: str) -> bool:
        """Check if a directory should be skipped during traversal"""
        return (dir_name.startswith('.') or 
                dir_name in Const.DIR_SKIP_LIST)
    
    @staticmethod
    def repo_filter(root: str, allowed_extensions=None):
        """Filter function to identify valuable files for analysis
        
        Args:
            root: Root directory to scan
            allowed_extensions: List of allowed extensions, or None for default
        
        Returns:
            List of relative file paths
        """
        docs = []
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip unwanted directories in-place
            dirnames[:] = [d for d in dirnames if not RepoUtil.should_skip_directory(d)]
            
            for filename in filenames:
                if RepoUtil.is_valuable_file(filename, allowed_extensions):
                    root_path = os.path.relpath(dirpath, root)
                    file_path = os.path.join(root_path, filename)
                    docs.append(file_path)
        
        logger.info(f"Found {len(docs)} valuable files in repository.")
        return docs
    
    @staticmethod
    def token_count(text: str) -> int:
        """Estimate token count for a given text
        use ollama as default embedder
        """
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        return len(tokens)

    @staticmethod
    def read_file_as_document(full_path: str, root: str = None, truncate_large: bool = True) -> Document:
        """Read a file and return it as a Document object with metadata
        
        Args:
            full_path: Full path to the file
            root: Optional root directory for calculating relative path
            truncate_large: If True, truncate content that exceeds MAX_TOKEN_LIMIT * 10
        
        Returns:
            Document object with file content and metadata, or None if reading fails
        """
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            token_count = RepoUtil.token_count(content)
            
            # Handle large files
            if token_count > RepoUtil.MAX_TOKEN_LIMIT and token_count < RepoUtil.MAX_TOKEN_LIMIT * 10:
                if truncate_large:
                    logger.warning(f"File {full_path} is too large with {token_count} tokens, cutting off content that exceeds limit.")
                    content = content[:RepoUtil.MAX_TOKEN_LIMIT * 10]
                    token_count = RepoUtil.MAX_TOKEN_LIMIT * 10
                else:
                    logger.warning(f"File {full_path} is very large with {token_count} tokens")
                    return None
            elif token_count >= RepoUtil.MAX_TOKEN_LIMIT * 10:
                logger.warning(f"File {full_path} is excessively large with {token_count} tokens, skipping.")
                return None
            
            # Calculate paths and metadata
            filename = os.path.basename(full_path)
            ext = os.path.splitext(filename)[1].lower()
            
            meta_data = {
                "source": full_path,
                "full_path": full_path,
                "filename": filename,
                "extension": ext,
                "token_count": token_count
            }
            
            if root:
                relative_path = os.path.relpath(full_path, root)
                meta_data["root"] = root
                meta_data["file_path"] = relative_path
                meta_data["real_path"] = relative_path
            
            return Document(text=f'File_path: {relative_path}\ncontent: {content}', meta_data=meta_data)
            
        except Exception as e:
            logger.error(f"Error reading file {full_path}: {e}")
            return None

    @staticmethod
    def file_content(root: str, file_path: str) -> Document:
        """Read and return the content of a file given its path relative to root
        
        Args:
            root: Root directory
            file_path: File path relative to root
        
        Returns:
            Document object with file content, or empty string on error
        """
        full_path = os.path.join(root, file_path)
        doc = RepoUtil.read_file_as_document(full_path, root=root, truncate_large=True)
        return doc if doc else ""
    
    @staticmethod
    def collect_documents(root: str, allowed_extensions=None):
        """Collect documents from a folder and return Document objects
        
        Args:
            root: Root directory to scan
            allowed_extensions: List of allowed extensions, or None for default
        
        Returns:
            List of Document objects with metadata
        """
        documents = []
        
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip unwanted directories in-place
            dirnames[:] = [d for d in dirnames if not RepoUtil.should_skip_directory(d)]
            
            for filename in filenames:
                # Check extension
                if not RepoUtil.is_valuable_file(filename, allowed_extensions):
                    continue
                
                file_path = os.path.join(dirpath, filename)
                
                # Use the shared read function
                doc = RepoUtil.read_file_as_document(file_path, root=root, truncate_large=True)
                
                if doc and doc.text.strip():  # Only add non-empty files
                    # Add source_folder to metadata
                    doc.meta_data["source_folder"] = root
                    documents.append(doc)
        
        logger.info(f"Collected {len(documents)} documents from {root}")
        return documents