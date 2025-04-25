import os
import sys
import importlib
from pathlib import Path
from typing import List
import shutil
import tempfile
import git  # Import GitPython

from fastapi import FastAPI, File, UploadFile, HTTPException, APIRouter, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from git import Repo, GitCommandError

# Ensure the modules directory is in the Python path
# Get modules directory path from environment variable or use default
MODULES_DIR = Path(os.environ.get("MODULES_DIR", "modules"))
MODULES_DIR.mkdir(exist_ok=True)
if str(MODULES_DIR.resolve()) not in sys.path:
    sys.path.insert(0, str(MODULES_DIR.resolve().parent)) # Add parent of modules to path

# Git configuration from environment variables
GIT_REPO_URL = os.environ.get("GIT_REPO_URL", "")
GIT_USERNAME = os.environ.get("GIT_USERNAME", "")
GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
GIT_BRANCH = os.environ.get("GIT_BRANCH", "main")
GIT_SYNC_ON_STARTUP = os.environ.get("GIT_SYNC_ON_STARTUP", "false").lower() == "true"

# Define model for file content
class FileContent(BaseModel):
    content: str

class GitSyncResponse(BaseModel):
    success: bool
    message: str
    synced_files: List[str] = []

app = FastAPI(title="Dynamic Microservice Runner")

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory store for loaded routers to prevent duplicate mounting
loaded_routers = {}

def sync_with_git() -> GitSyncResponse:
    """
    Synchronizes the modules directory with the configured Git repository.
    Returns a GitSyncResponse object with the results of the operation.
    """
    if not GIT_REPO_URL:
        return GitSyncResponse(
            success=False, 
            message="Git repository URL not configured. Set GIT_REPO_URL environment variable."
        )

    try:
        repo = Repo(MODULES_DIR.parent)
        
        # Check if there are local changes that need to be preserved
        has_local_changes = repo.is_dirty(untracked_files=True)
        stash_created = False
        
        if has_local_changes:
            # Stash local changes to preserve them
            print("Stashing local changes before Git sync...")
            try:
                # Configure git user for stashing
                if not repo.config_reader().has_section('user'):
                    repo.git.config('user.email', 'automated@example.com')
                    repo.git.config('user.name', 'Automated Git Sync')
                
                # Create stash
                repo.git.stash('push', '-m', 'Automatic stash before Git sync')
                stash_created = True
                print("Local changes stashed successfully")
            except GitCommandError as stash_error:
                print(f"Warning: Failed to stash changes: {stash_error}")
                # We'll continue anyway and see if the pull can succeed

        # Stage all changes in the modules directory
        repo.git.add(MODULES_DIR.as_posix())

        # Remove deleted files from the repository
        deleted_files = [item.a_path for item in repo.index.diff(None) if item.change_type == 'D']
        for file in deleted_files:
            repo.git.rm(file)

        # Configure remote URL with embedded credentials if available
        if GIT_USERNAME and GIT_TOKEN and GIT_REPO_URL:
            # Parse the repo URL to insert credentials
            if GIT_REPO_URL.startswith('https://'):
                # Format: https://username:token@github.com/user/repo.git
                url_parts = GIT_REPO_URL.split('https://')
                if len(url_parts) == 2:
                    auth_url = f'https://{GIT_USERNAME}:{GIT_TOKEN}@{url_parts[1]}'
                    # Set the remote URL with credentials
                    repo.git.remote('set-url', 'origin', auth_url)
                    print("Git remote URL configured with authentication")
        
        # Pull latest changes from the remote repository
        origin = repo.remotes.origin
        
        # Set git config for pull strategy
        repo.git.config('pull.rebase', 'false')
        repo.git.config('pull.ff', 'false')  # Allow non-fast-forward merges
        
        # Configure git user for potential merge commits
        if not repo.config_reader().has_section('user'):
            repo.git.config('user.email', 'automated@example.com')
            repo.git.config('user.name', 'Automated Git Sync')
        
            message="Git synchronization completed successfully."
        )

    except GitCommandError as e:
        return GitSyncResponse(success=False, message=f"Git sync failed: {str(e)}")

@app.post("/git-commit", response_model=GitSyncResponse)
async def commit_changes_to_git(commit_message: str = Body(..., embed=True)):
    """Commits new and modified files in the modules directory to the Git repository."""
    if not GIT_REPO_URL:
        return GitSyncResponse(
            success=False,
            message="Git repository URL not configured. Set GIT_REPO_URL environment variable."
        )

    try:
        repo = Repo(MODULES_DIR.parent)

        # Stage all changes in the modules directory
        repo.git.add(MODULES_DIR.as_posix())

        # Check if there are changes to commit
        if repo.is_dirty(untracked_files=True):
            # Commit changes
            repo.index.commit(commit_message)
            return GitSyncResponse(
                success=True,
                message="Changes committed successfully to Git repository."
            )
        else:
            return GitSyncResponse(
                success=False,
                message="No changes to commit."
            )

    except GitCommandError as e:
        return GitSyncResponse(
            success=False,
            message=f"Git commit failed: {str(e)}"
        )

def load_module(filename: str):
    """Dynamically loads or reloads a Python module and mounts its router."""
    # Handle path separators in filename for nested modules
    filepath = MODULES_DIR / filename
    
    if not filepath.exists() or not filepath.name.endswith(".py"):
        return # Skip if not a python file or doesn't exist
    
    try:
        # Invalidate caches to ensure reloading works
        importlib.invalidate_caches()
        
        # Create the proper import path by replacing path separators with dots
        # First get relative path from modules directory, then convert to import path
        rel_path = filepath.relative_to(MODULES_DIR)
        path_parts = list(rel_path.parts)
        
        # The module name is the filename without .py extension
        module_name = path_parts[-1].removesuffix(".py")
        
        # Create the full import path (e.g., modules.subdir.my_service)
        if len(path_parts) > 1:
            # File is in a subdirectory
            # Remove the filename and keep only directory parts for the import path
            dir_parts = [p for p in path_parts[:-1]]
            import_path = f"{MODULES_DIR.name}.{'.'.join(dir_parts)}.{module_name}"
            
            # Ensure all parent directories have __init__.py files to make them proper packages
            current = MODULES_DIR
            for part in dir_parts:
                current = current / part
                init_file = current / "__init__.py"
                if not init_file.exists():
                    # Create empty __init__.py file if it doesn't exist
                    with open(init_file, "w") as f:
                        f.write("# Auto-generated package marker\n")
        else:
            # File is in the root of modules directory
            import_path = f"{MODULES_DIR.name}.{module_name}"
        
        # Check if module is already imported
        if import_path in sys.modules:
            module = importlib.reload(sys.modules[import_path])
            print(f"Reloaded module: {import_path}")
        else:
            module = importlib.import_module(import_path)
            print(f"Loaded module: {import_path}")

        # Find an APIRouter instance in the module
        router_instance = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, APIRouter):
                router_instance = attr
                break

        if router_instance:
            # Create prefix based on the file path
            # For root modules: /module_name
            # For nested modules: /directory/subdirectory/module_name
            if len(path_parts) > 1:
                # The path is relative to modules directory
                # Join all parts with / to create the prefix
                prefix_path = "/".join(str(p) for p in path_parts[:-1])
                prefix = f"/{prefix_path}/{module_name}"
            else:
                prefix = f"/{module_name}"
                
            # Unmount existing router if reloading
            if prefix in loaded_routers:
                # FastAPI doesn't have a direct unmount. We rely on reload and potentially restart for full cleanup.
                # For now, we just overwrite the entry in our tracking dict.
                print(f"Router for {prefix} already exists. Reloading might require app restart for full effect.")

            app.include_router(router_instance, prefix=prefix, tags=[str(rel_path)])
            loaded_routers[prefix] = router_instance
            print(f"Mounted router from {filename} at {prefix}")
        else:
            print(f"No APIRouter found in {filename}")

    except Exception as e:
        print(f"Error loading module {filename}: {e}")
        # Optionally raise or handle the error more gracefully
        # raise HTTPException(status_code=500, detail=f"Error loading module {filename}: {e}")

def load_all_modules():
    """Loads all .py files from the modules directory and subdirectories."""
    print(f"Loading modules from: {MODULES_DIR.resolve()}")
    # Walk through directory tree recursively to find all Python files
    for root, _, files in os.walk(MODULES_DIR):
        root_path = Path(root)
        for filename in files:
            if filename.endswith(".py") and filename != "__init__.py":
                # Get the relative path from the modules directory
                rel_path = root_path.relative_to(MODULES_DIR)
                if str(rel_path) == ".":
                    # File is in the root of modules directory
                    load_module(filename)
                else:
                    # File is in a subdirectory
                    rel_filepath = rel_path / filename
                    load_module(str(rel_filepath))

@app.on_event("startup")
async def startup_event():
    """Load all modules on application startup and sync with Git if configured."""
    # Check if Git sync on startup is enabled
    if GIT_SYNC_ON_STARTUP and GIT_REPO_URL:
        print("Git sync on startup is enabled. Syncing with repository...")
        sync_result = sync_with_git()
        if sync_result.success:
            print(f"Git sync successful: {sync_result.message}")
        else:
            print(f"Git sync failed: {sync_result.message}")
    else:
        # If no Git sync, just load modules normally
        load_all_modules()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serves the main HTML user interface."""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="index.html not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load UI: {e}")

@app.post("/upload", status_code=201)
async def upload_file(file: UploadFile = File(...), directory: str = ""):
    """
    Uploads a Python file and loads it as a module.
    Can place the file in a subdirectory by providing the directory parameter.
    """
    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .py files are allowed.")

    # Normalize directory path and ensure it doesn't have leading/trailing slashes
    directory = directory.strip("/\\").replace("\\", "/") if directory else ""
    
    # Create target directory if it doesn't exist
    target_dir = MODULES_DIR
    if directory:
        target_dir = MODULES_DIR / directory
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Create __init__.py files in each directory level to make them proper packages
        current = MODULES_DIR
        for part in directory.split("/"):
            current = current / part
            init_file = current / "__init__.py"
            if not init_file.exists():
                with open(init_file, "w") as f:
                    f.write("# Auto-generated package marker\n")
    
    # Full path to the file
    filepath = target_dir / file.filename
    
    try:
        contents = await file.read()
        with open(filepath, "wb") as f:
            f.write(contents)

        # Attempt to load the newly uploaded module
        rel_path = filepath.relative_to(MODULES_DIR)
        load_module(str(rel_path))

        return {
            "filename": file.filename,
            "path": str(rel_path),
            "message": "File uploaded and module loaded successfully."
        }
    except Exception as e:
        # Clean up partial file if upload failed
        if filepath.exists():
            os.remove(filepath)
        raise HTTPException(status_code=500, detail=f"Failed to upload or load file: {e}")
    finally:
        await file.close()

class FileItem(BaseModel):
    """Model representing a file or directory in the modules directory."""
    path: str  # Relative path from modules directory
    name: str  # Name of the file or directory
    is_dir: bool  # True if the item is a directory, False if it's a file

@app.get("/files")
def list_files():
    """Lists all .py files and directories in the modules directory and subdirectories."""
    try:
        items = []
        
        # Walk through directory tree recursively
        for root, dirs, files in os.walk(MODULES_DIR):
            root_path = Path(root)
            
            # Skip __pycache__ directories
            if "__pycache__" in root_path.parts:
                continue
                
            # Get relative path from modules directory
            try:
                rel_path = root_path.relative_to(MODULES_DIR)
                rel_path_str = str(rel_path) if str(rel_path) != "." else ""
            except ValueError:
                # Not relative to MODULES_DIR, should never happen
                continue
            
            # Add directories (skip any hidden directories starting with .)
            for dirname in dirs:
                if not dirname.startswith(".") and dirname != "__pycache__":
                    dir_path = str(Path(rel_path_str) / dirname) if rel_path_str else dirname
                    items.append(FileItem(path=dir_path, name=dirname, is_dir=True))
            
            # Add Python files (skip __init__.py)
            for filename in files:
                if filename.endswith(".py") and filename != "__init__.py" and not filename.startswith("."):
                    file_path = str(Path(rel_path_str) / filename) if rel_path_str else filename
                    items.append(FileItem(path=file_path, name=filename, is_dir=False))
        
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {e}")

@app.get("/files/{file_path:path}")
async def get_file_content(file_path: str):
    """Returns the content of a specific Python file, including those in subdirectories."""
    # Handle path separators in file_path
    normalized_path = file_path.replace('\\', '/').lstrip('/')
    filepath = MODULES_DIR / normalized_path
    
    if not filepath.exists() or not filepath.name.endswith(".py"):
        raise HTTPException(status_code=404, detail="File not found or not a .py file.")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return JSONResponse(content={"filename": filepath.name, "path": normalized_path, "content": content})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

@app.post("/files/{file_path:path}", status_code=200)
async def save_file_content(file_path: str, file_data: FileContent = Body(...)):
    """Saves new content to a specific Python file and reloads the module."""
    # Handle path separators in file_path
    normalized_path = file_path.replace('\\', '/').lstrip('/')
    filepath = MODULES_DIR / normalized_path
    
    if not filepath.exists() or not filepath.name.endswith(".py"):
        raise HTTPException(status_code=404, detail="File not found or not a .py file.")
    
    try:
        # Debug - print the received data
        print(f"Received data for {file_path}: {file_data}")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(file_data.content)

        # Reload the module after saving changes
        load_module(normalized_path)

        return {"filename": filepath.name, "path": normalized_path, "message": "File saved and module reloaded successfully."}
    except Exception as e:
        print(f"Error saving file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save or reload file: {e}")

@app.delete("/files/{file_path:path}", status_code=200)
async def delete_file(file_path: str):
    """Deletes a specific Python file from the modules directory."""
    # Handle path separators in file_path
    normalized_path = file_path.replace('\\', '/').lstrip('/')
    filepath = MODULES_DIR / normalized_path
    
    if not filepath.exists() or not filepath.name.endswith(".py"):
        raise HTTPException(status_code=404, detail="File not found or not a .py file.")
    
    try:
        # Check if the module is loaded and remove it from loaded_routers
        module_name = filepath.stem  # Name without extension
        
        # Create prefix based on the file path (same logic as in load_module)
        rel_path = filepath.relative_to(MODULES_DIR)
        path_parts = list(rel_path.parts)
        
        if len(path_parts) > 1:
            # The path is relative to modules directory
            prefix_path = "/".join(str(p) for p in path_parts[:-1])
            prefix = f"/{prefix_path}/{module_name}"
        else:
            prefix = f"/{module_name}"
            
        if prefix in loaded_routers:
            # Note: FastAPI doesn't support true router removal at runtime
            # We just remove it from our tracking dictionary
            del loaded_routers[prefix]
        
        # Delete the file
        os.remove(filepath)
        
        # Check if the parent directory is empty (except for __init__.py) and remove it if it is
        parent_dir = filepath.parent
        if parent_dir != MODULES_DIR:
            # Check if directory contains only __init__.py or is empty
            dir_contents = list(parent_dir.glob("*"))
            if len(dir_contents) <= 1 and all(f.name == "__init__.py" for f in dir_contents):
                # Directory only contains __init__.py or is empty, safe to remove __init__.py
                init_path = parent_dir / "__init__.py"
                if init_path.exists():
                    os.remove(init_path)
                    
                # If directory is now empty, try to remove it
                if not any(parent_dir.iterdir()):
                    try:
                        parent_dir.rmdir()
                    except OSError:
                        # Ignore if directory can't be removed
                        pass
        
        return {"filename": filepath.name, "path": normalized_path, "message": "File deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")

@app.get("/git-sync", response_model=GitSyncResponse)
async def trigger_git_sync():
    """Endpoint to manually trigger synchronization with Git repository."""
    if not GIT_REPO_URL:
        return GitSyncResponse(
            success=False, 
            message="Git repository URL not configured. Set GIT_REPO_URL environment variable."
        )
    
    return sync_with_git()