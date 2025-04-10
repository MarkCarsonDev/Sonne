"""
File utility functions for Sonne.
Provides utilities for file operations like copying, ensuring directories exist, etc.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import List, Optional, Set

logger = logging.getLogger('sonne')

def ensure_dir(directory: str) -> None:
    """Ensure a directory exists, creating it if necessary.
    
    Args:
        directory: Path to the directory.
    """
    os.makedirs(directory, exist_ok=True)
    
def copy_static_files(static_dir: str, output_dir: str) -> None:
    """Copy static files to the output directory.
    
    Args:
        static_dir: Path to the static directory.
        output_dir: Path to the output directory.
    """
    if not os.path.exists(static_dir):
        logger.warning(f"Static directory does not exist: {static_dir}")
        return
        
    # Copy all files from static directory to output directory
    for root, dirs, files in os.walk(static_dir):
        # Skip hidden directories and files
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        files = [f for f in files if not f.startswith('.')]
        
        # Calculate relative path
        rel_path = os.path.relpath(root, static_dir)
        
        # Create output directory if it doesn't exist
        if rel_path != '.':
            ensure_dir(os.path.join(output_dir, rel_path))
            
        # Copy each file
        for file in files:
            source_file = os.path.join(root, file)
            dest_file = os.path.join(output_dir, rel_path, file)
            
            # Copy the file
            try:
                shutil.copy2(source_file, dest_file)
                logger.debug(f"Copied static file: {source_file} -> {dest_file}")
            except Exception as e:
                logger.error(f"Error copying static file {source_file}: {e}")
                
def get_file_mtime(file_path: str) -> float:
    """Get the modification time of a file.
    
    Args:
        file_path: Path to the file.
        
    Returns:
        Modification time as a timestamp.
    """
    try:
        return os.path.getmtime(file_path)
    except OSError:
        return 0
        
def is_file_modified(source_file: str, dest_file: str) -> bool:
    """Check if a source file is newer than a destination file.
    
    Args:
        source_file: Path to the source file.
        dest_file: Path to the destination file.
        
    Returns:
        True if the source file is newer than the destination file or if the destination file does not exist.
    """
    if not os.path.exists(dest_file):
        return True
        
    source_mtime = get_file_mtime(source_file)
    dest_mtime = get_file_mtime(dest_file)
    
    return source_mtime > dest_mtime
    
def get_all_files(directory: str, extensions: Optional[List[str]] = None) -> List[str]:
    """Get all files in a directory, optionally filtering by extension.
    
    Args:
        directory: Path to the directory.
        extensions: List of file extensions to include.
        
    Returns:
        List of file paths.
    """
    files = []
    
    if not os.path.exists(directory):
        return files
        
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if extensions is None or any(filename.endswith(ext) for ext in extensions):
                files.append(os.path.join(root, filename))
                
    return files
    
def clean_directory(directory: str, exclude: Optional[List[str]] = None) -> None:
    """Clean a directory by removing all files and subdirectories.
    
    Args:
        directory: Path to the directory.
        exclude: List of filenames or directories to exclude from cleaning.
    """
    if not os.path.exists(directory):
        return
        
    exclude_set = set(exclude or [])
    
    for item in os.listdir(directory):
        if item in exclude_set:
            continue
            
        item_path = os.path.join(directory, item)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        except Exception as e:
            logger.error(f"Error cleaning directory {directory}: {e}")