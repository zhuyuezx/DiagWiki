import os
import logging
from const.const import Const
from adalflow.core.types import Document
import tiktoken

logger = logging.getLogger(__name__)

class RepoUtil:
    """Utility class for repository operations"""
    MAX_TOKEN_LIMIT = 8192

    @staticmethod
    def build_tree(current_path):
        # ignore hidden files and folders
        if os.path.basename(current_path).startswith('.'):
            return None
        # ignore __pycache__ folders
        if os.path.basename(current_path) == '__pycache__':
            return None
        if os.path.isdir(current_path):
            children = []
            for item in os.listdir(current_path):
                item_path = os.path.join(current_path, item)
                child_tree = RepoUtil.build_tree(item_path)
                if child_tree is not None:
                    children.append(child_tree)
            return {
                "name": os.path.basename(current_path),
                "type": "directory",
                "children": children
            }
        else:
            return {
                "name": os.path.basename(current_path),
                "type": "file"
            }

    @staticmethod
    def repo_filter(root: str):
        """Filter function to identify valuable files for analysis"""
        
        def is_valuable_file(file_name: str) -> bool:
            _, ext = os.path.splitext(file_name)
            return ext in Const.CODE_EXTENSIONS or ext in Const.DOC_EXTENSIONS
        
        docs = []
        for dirpath, dirnames, filenames in os.walk(root):
            for filename in filenames:
                if is_valuable_file(filename):
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
    def file_content(root: str, file_path: str) -> str:
        """Read and return the content of a file given its path relative to root"""
        full_path = os.path.join(root, file_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                token_count = RepoUtil.token_count(content)
                if token_count > RepoUtil.MAX_TOKEN_LIMIT * 10:
                    # cutoff files that are too large
                    logger.warning(f"File {full_path} is too large with {token_count} tokens, cutting off content that exceeds limit.")
                    content = content[:RepoUtil.MAX_TOKEN_LIMIT * 10]
                    token_count = RepoUtil.MAX_TOKEN_LIMIT * 10
                return Document(
                    text=content,
                    meta_data={
                        "source": full_path,
                        "root": root,
                        "real_path": file_path,
                        "token_count": token_count
                    }
                )
        except Exception as e:
            logger.error(f"Error reading file {full_path}: {e}")
            return ""