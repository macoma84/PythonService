import os
import sys
import importlib
from pathlib import Path
from typing import List
import shutil
import tempfile
import git  # Import GitPython
import logging
import io
import datetime
import asyncio
from collections import deque
from fastapi.responses import StreamingResponse

from fastapi import FastAPI, File, UploadFile, HTTPException, APIRouter, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Configure logging
# In-memory log storage using a deque with max length to prevent memory issues
MAX_LOG_ENTRIES = 1000
log_storage = deque(maxlen=MAX_LOG_ENTRIES)

# Custom log handler to capture logs in memory
class InMemoryLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = {
            'timestamp': datetime.datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'level': record.levelname,
            'module': record.module,
            'message': self.format(record)
        }
        log_storage.append(log_entry)

# Setup root logger with our custom handler
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
memory_handler = InMemoryLogHandler()
memory_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s'))
root_logger.addHandler(memory_handler)

# Redirect print statements to the logging system
original_print = print

def logging_print(*args, **kwargs):
    """Redirect print statements to the logging system."""
    # Get the frame where print was called
    frame = sys._getframe(1)
    module_name = frame.f_globals.get('__name__', 'unknown')
    
    # Construct the message from print arguments
    message = " ".join(str(arg) for arg in args)
    
    # Log the message at INFO level
    logging.getLogger(module_name).info(f"[PRINT] {message}")
    
    # Still perform the original print functionality
    return original_print(*args, **kwargs)

print = logging_print

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

class GitCommitRequest(BaseModel):
    message: str

class GitPushRequest(BaseModel):
    commit_message: str = None

class GitBranchRequest(BaseModel):
    branch_name: str

class GitMergeRequest(BaseModel):
    branch_name: str

class GitDiffRequest(BaseModel):
    file_path: str = None

app = FastAPI(title="Dynamic Microservice Runner")

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory store for loaded routers to prevent duplicate mounting
loaded_routers = {}

def get_authenticated_repo_url() -> str:
    """Returns the Git repository URL with authentication credentials."""
    repo_url = GIT_REPO_URL
    if "https://" in GIT_REPO_URL:
        if GIT_USERNAME and GIT_TOKEN:
            repo_url = GIT_REPO_URL.replace("https://", f"https://{GIT_USERNAME}:{GIT_TOKEN}@")
        elif GIT_TOKEN:
            repo_url = GIT_REPO_URL.replace("https://", f"https://oauth2:{GIT_TOKEN}@")
    return repo_url

def get_or_init_repo() -> git.Repo:
    """
    Gets the git repository from the modules directory.
    If it doesn't exist, initializes or clones it.
    """
    if not GIT_REPO_URL:
        raise ValueError("Git repository URL not configured. Set GIT_REPO_URL environment variable.")

    modules_git_dir = MODULES_DIR / ".git"

    # Check if modules directory already has a git repo
    if modules_git_dir.exists():
        try:
            repo = git.Repo(MODULES_DIR)
            print(f"Using existing git repository in {MODULES_DIR}")
            return repo
        except git.InvalidGitRepositoryError:
            print(f"Invalid git repository found in {MODULES_DIR}, reinitializing...")
            shutil.rmtree(modules_git_dir)

    # Initialize new repository
    print(f"Initializing git repository in {MODULES_DIR}")
    MODULES_DIR.mkdir(exist_ok=True)
    repo = git.Repo.init(MODULES_DIR)

    # Configure remote
    repo_url = get_authenticated_repo_url()

    try:
        origin = repo.remote('origin')
        origin.set_url(repo_url)
    except ValueError:
        # Remote doesn't exist, create it
        origin = repo.create_remote('origin', repo_url)

    # Configure user if provided
    if GIT_USERNAME:
        with repo.config_writer() as config:
            config.set_value("user", "name", GIT_USERNAME)
            if "@" in GIT_USERNAME:
                config.set_value("user", "email", GIT_USERNAME)

    return repo

def git_pull() -> GitSyncResponse:
    """
    Pulls changes from the remote repository to the modules directory.
    """
    if not GIT_REPO_URL:
        return GitSyncResponse(
            success=False,
            message="Git repository URL not configured. Set GIT_REPO_URL environment variable."
        )

    try:
        repo = get_or_init_repo()

        # Fetch from remote
        print(f"Fetching from remote repository (branch: {GIT_BRANCH})...")
        origin = repo.remote('origin')
        fetch_info = origin.fetch()

        # Check if branch exists locally
        branch_exists = GIT_BRANCH in [ref.name for ref in repo.heads]

        if not branch_exists:
            # Create local branch tracking remote
            print(f"Creating local branch {GIT_BRANCH} tracking origin/{GIT_BRANCH}")
            repo.create_head(GIT_BRANCH, origin.refs[GIT_BRANCH])
            repo.heads[GIT_BRANCH].set_tracking_branch(origin.refs[GIT_BRANCH])

        # Checkout the branch
        if repo.active_branch.name != GIT_BRANCH:
            print(f"Checking out branch {GIT_BRANCH}")
            repo.heads[GIT_BRANCH].checkout()

        # Pull changes
        print(f"Pulling changes from origin/{GIT_BRANCH}...")
        pull_info = origin.pull(GIT_BRANCH)

        # Get list of changed files
        changed_files = []
        for info in pull_info:
            if hasattr(info, 'commit') and info.commit:
                for item in info.commit.stats.files.keys():
                    if item.endswith('.py'):
                        changed_files.append(item)

        # Reload modules after pull
        load_all_modules()

        return GitSyncResponse(
            success=True,
            message=f"Successfully pulled changes from remote repository",
            synced_files=changed_files
        )

    except Exception as e:
        print(f"Error during git pull: {e}")
        return GitSyncResponse(success=False, message=f"Git pull failed: {str(e)}")

def git_push(commit_message: str = None) -> GitSyncResponse:
    """
    Pushes local changes to the remote repository.
    Optionally commits changes before pushing.
    """
    if not GIT_REPO_URL:
        return GitSyncResponse(
            success=False,
            message="Git repository URL not configured. Set GIT_REPO_URL environment variable."
        )

    try:
        repo = get_or_init_repo()

        # Stage all changes if commit message provided
        if commit_message:
            print("Staging all changes...")
            repo.git.add(A=True)

            # Check if there are changes to commit
            if repo.is_dirty() or repo.untracked_files:
                print(f"Committing changes: {commit_message}")
                repo.index.commit(commit_message)
            else:
                print("No changes to commit")

        # Push to remote
        print(f"Pushing to origin/{GIT_BRANCH}...")
        origin = repo.remote('origin')
        push_info = origin.push(GIT_BRANCH)

        pushed_files = []
        for info in push_info:
            if hasattr(info, 'summary'):
                print(f"Push result: {info.summary}")

        return GitSyncResponse(
            success=True,
            message=f"Successfully pushed changes to remote repository",
            synced_files=pushed_files
        )

    except Exception as e:
        print(f"Error during git push: {e}")
        return GitSyncResponse(success=False, message=f"Git push failed: {str(e)}")

def git_status() -> dict:
    """
    Gets the status of the git repository.
    Returns information about modified, added, deleted, and untracked files.
    """
    if not GIT_REPO_URL:
        return {
            "success": False,
            "message": "Git repository URL not configured."
        }

    try:
        repo = get_or_init_repo()

        # Get current branch
        current_branch = repo.active_branch.name if repo.head.is_valid() else "No branch"

        # Get modified files
        modified_files = [item.a_path for item in repo.index.diff(None)]

        # Get staged files
        staged_files = [item.a_path for item in repo.index.diff("HEAD")]

        # Get untracked files
        untracked_files = repo.untracked_files

        # Check if ahead/behind remote
        ahead = 0
        behind = 0
        try:
            if repo.head.is_valid() and current_branch != "No branch":
                tracking_branch = repo.active_branch.tracking_branch()
                if tracking_branch:
                    ahead = len(list(repo.iter_commits(f'{tracking_branch}..HEAD')))
                    behind = len(list(repo.iter_commits(f'HEAD..{tracking_branch}')))
        except Exception as e:
            print(f"Could not check ahead/behind status: {e}")

        return {
            "success": True,
            "current_branch": current_branch,
            "modified_files": modified_files,
            "staged_files": staged_files,
            "untracked_files": untracked_files,
            "ahead": ahead,
            "behind": behind,
            "is_dirty": repo.is_dirty()
        }

    except Exception as e:
        print(f"Error getting git status: {e}")
        return {
            "success": False,
            "message": f"Failed to get git status: {str(e)}"
        }

def git_diff(file_path: str = None) -> dict:
    """
    Gets the diff of changes in the repository.
    If file_path is provided, shows diff for that file only.
    """
    if not GIT_REPO_URL:
        return {
            "success": False,
            "message": "Git repository URL not configured."
        }

    try:
        repo = get_or_init_repo()

        # Get diff
        if file_path:
            # Diff for specific file
            diff = repo.git.diff('HEAD', '--', file_path)
        else:
            # Diff for all changes
            diff = repo.git.diff('HEAD')

        return {
            "success": True,
            "diff": diff
        }

    except Exception as e:
        print(f"Error getting git diff: {e}")
        return {
            "success": False,
            "message": f"Failed to get git diff: {str(e)}"
        }

def git_commit(message: str) -> GitSyncResponse:
    """
    Commits all changes with the provided message.
    """
    if not GIT_REPO_URL:
        return GitSyncResponse(
            success=False,
            message="Git repository URL not configured."
        )

    try:
        repo = get_or_init_repo()

        # Stage all changes
        print("Staging all changes...")
        repo.git.add(A=True)

        # Check if there are changes to commit
        if not repo.is_dirty() and not repo.untracked_files:
            return GitSyncResponse(
                success=True,
                message="No changes to commit",
                synced_files=[]
            )

        # Commit changes
        print(f"Committing changes: {message}")
        commit = repo.index.commit(message)

        # Get list of files in the commit
        changed_files = list(commit.stats.files.keys())

        return GitSyncResponse(
            success=True,
            message=f"Successfully committed changes: {commit.hexsha[:7]}",
            synced_files=changed_files
        )

    except Exception as e:
        print(f"Error during git commit: {e}")
        return GitSyncResponse(success=False, message=f"Git commit failed: {str(e)}")

def git_branches() -> dict:
    """
    Lists all local and remote branches.
    """
    if not GIT_REPO_URL:
        return {
            "success": False,
            "message": "Git repository URL not configured."
        }

    try:
        repo = get_or_init_repo()

        # Get local branches
        local_branches = [branch.name for branch in repo.heads]

        # Get remote branches
        remote_branches = []
        try:
            origin = repo.remote('origin')
            origin.fetch()
            remote_branches = [ref.name for ref in origin.refs]
        except Exception as e:
            print(f"Could not fetch remote branches: {e}")

        # Get current branch
        current_branch = repo.active_branch.name if repo.head.is_valid() else None

        return {
            "success": True,
            "current_branch": current_branch,
            "local_branches": local_branches,
            "remote_branches": remote_branches
        }

    except Exception as e:
        print(f"Error listing git branches: {e}")
        return {
            "success": False,
            "message": f"Failed to list branches: {str(e)}"
        }

def git_create_branch(branch_name: str) -> dict:
    """
    Creates a new branch.
    """
    if not GIT_REPO_URL:
        return {
            "success": False,
            "message": "Git repository URL not configured."
        }

    try:
        repo = get_or_init_repo()

        # Check if branch already exists
        if branch_name in [branch.name for branch in repo.heads]:
            return {
                "success": False,
                "message": f"Branch '{branch_name}' already exists"
            }

        # Create new branch
        print(f"Creating new branch: {branch_name}")
        new_branch = repo.create_head(branch_name)

        return {
            "success": True,
            "message": f"Branch '{branch_name}' created successfully"
        }

    except Exception as e:
        print(f"Error creating git branch: {e}")
        return {
            "success": False,
            "message": f"Failed to create branch: {str(e)}"
        }

def git_checkout_branch(branch_name: str) -> dict:
    """
    Checks out (switches to) a different branch.
    """
    if not GIT_REPO_URL:
        return {
            "success": False,
            "message": "Git repository URL not configured."
        }

    try:
        repo = get_or_init_repo()

        # Check if branch exists locally
        if branch_name not in [branch.name for branch in repo.heads]:
            # Try to create from remote
            try:
                origin = repo.remote('origin')
                origin.fetch()
                if f"origin/{branch_name}" in [ref.name for ref in origin.refs]:
                    print(f"Creating local branch {branch_name} from origin/{branch_name}")
                    repo.create_head(branch_name, origin.refs[branch_name])
                    repo.heads[branch_name].set_tracking_branch(origin.refs[branch_name])
                else:
                    return {
                        "success": False,
                        "message": f"Branch '{branch_name}' not found locally or on remote"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Branch '{branch_name}' not found: {str(e)}"
                }

        # Checkout the branch
        print(f"Checking out branch: {branch_name}")
        repo.heads[branch_name].checkout()

        # Reload modules after checkout
        load_all_modules()

        return {
            "success": True,
            "message": f"Switched to branch '{branch_name}'"
        }

    except Exception as e:
        print(f"Error checking out git branch: {e}")
        return {
            "success": False,
            "message": f"Failed to checkout branch: {str(e)}"
        }

def git_merge(branch_name: str) -> dict:
    """
    Merges the specified branch into the current branch.
    """
    if not GIT_REPO_URL:
        return {
            "success": False,
            "message": "Git repository URL not configured."
        }

    try:
        repo = get_or_init_repo()

        # Check if branch exists
        if branch_name not in [branch.name for branch in repo.heads]:
            return {
                "success": False,
                "message": f"Branch '{branch_name}' not found"
            }

        current_branch = repo.active_branch.name
        print(f"Merging {branch_name} into {current_branch}")

        # Perform the merge
        repo.git.merge(branch_name)

        # Reload modules after merge
        load_all_modules()

        return {
            "success": True,
            "message": f"Successfully merged '{branch_name}' into '{current_branch}'"
        }

    except git.GitCommandError as e:
        print(f"Git merge conflict: {e}")
        return {
            "success": False,
            "message": f"Merge conflict: {str(e)}. Please resolve conflicts manually."
        }
    except Exception as e:
        print(f"Error during git merge: {e}")
        return {
            "success": False,
            "message": f"Failed to merge: {str(e)}"
        }

def sync_with_git() -> GitSyncResponse:
    """
    Legacy function - now calls git_pull for backward compatibility.
    """
    return git_pull()

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
        
        # Create a logger for this module specifically
        module_logger = logging.getLogger(f"modules.{module_name}")
        module_logger.setLevel(logging.DEBUG)
        
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
            module_logger.info(f"Reloaded module: {import_path}")
        else:
            module = importlib.import_module(import_path)
            module_logger.info(f"Loaded module: {import_path}")

        # Find an APIRouter instance in the module
        router_instance = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, APIRouter):
                router_instance = attr
                module_logger.info(f"Found router with {len(getattr(attr, 'routes', []))} routes")
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
                
            # Unmount existing router if reloading            if prefix in loaded_routers:
                # FastAPI doesn't have a direct unmount. We rely on reload and potentially restart for full cleanup.
                # For now, we just overwrite the entry in our tracking dict.
                module_logger.warning(f"Router for {prefix} already exists. Reloading might require app restart for full effect.")

            app.include_router(router_instance, prefix=prefix, tags=[str(rel_path)])
            loaded_routers[prefix] = router_instance
            module_logger.info(f"Mounted router from {filename} at {prefix}")
        else:
            module_logger.warning(f"No APIRouter found in {filename}")

    except Exception as e:
        module_logger.error(f"Error loading module {filename}: {str(e)}", exc_info=True)
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
    """Endpoint to manually trigger synchronization with Git repository (legacy - calls git-pull)."""
    if not GIT_REPO_URL:
        return GitSyncResponse(
            success=False,
            message="Git repository URL not configured. Set GIT_REPO_URL environment variable."
        )

    return sync_with_git()

@app.get("/api/git/pull", response_model=GitSyncResponse)
async def api_git_pull():
    """Pull changes from remote repository."""
    return git_pull()

@app.post("/api/git/push", response_model=GitSyncResponse)
async def api_git_push(request: GitPushRequest = Body(...)):
    """Push local changes to remote repository. Optionally commit changes first."""
    return git_push(commit_message=request.commit_message)

@app.get("/api/git/status")
async def api_git_status():
    """Get the current git status."""
    return git_status()

@app.post("/api/git/diff")
async def api_git_diff(request: GitDiffRequest = Body(...)):
    """Get diff of changes. Optionally specify a file path."""
    return git_diff(file_path=request.file_path)

@app.post("/api/git/commit", response_model=GitSyncResponse)
async def api_git_commit(request: GitCommitRequest = Body(...)):
    """Commit all changes with the provided message."""
    return git_commit(message=request.message)

@app.get("/api/git/branches")
async def api_git_branches():
    """List all local and remote branches."""
    return git_branches()

@app.post("/api/git/branch/create")
async def api_git_create_branch(request: GitBranchRequest = Body(...)):
    """Create a new branch."""
    return git_create_branch(branch_name=request.branch_name)

@app.post("/api/git/branch/checkout")
async def api_git_checkout_branch(request: GitBranchRequest = Body(...)):
    """Checkout (switch to) a different branch."""
    return git_checkout_branch(branch_name=request.branch_name)

@app.post("/api/git/merge")
async def api_git_merge(request: GitMergeRequest = Body(...)):
    """Merge the specified branch into the current branch."""
    return git_merge(branch_name=request.branch_name)

@app.get("/logs", response_class=HTMLResponse)
async def view_logs():
    """Serves a simple HTML page for viewing logs."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Module Logs</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: monospace; margin: 20px; background-color: #f4f4f4; }
            .container { max-width: 100%; margin: auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            h1 { color: #333; }
            #logContainer { height: 600px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; background-color: #f9f9f9; }
            .log-entry { margin-bottom: 5px; padding: 3px; border-bottom: 1px solid #eee; }
            .timestamp { color: #888; }
            .level-INFO { color: #28a745; }
            .level-WARNING { color: #ffc107; }
            .level-ERROR { color: #dc3545; }
            .level-DEBUG { color: #17a2b8; }
            .module { font-weight: bold; }
            .controls { margin-bottom: 10px; }
            button { padding: 8px 15px; margin-right: 5px; cursor: pointer; background-color: #007bff; color: white; border: none; border-radius: 4px; }
            button:hover { background-color: #0069d9; }
            select { padding: 8px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Module Logs</h1>
            <div class="controls">
                <button id="refreshButton">Refresh</button>
                <button id="clearButton">Clear View</button>
                <button id="streamButton">Start Live Stream</button>
                <select id="logLevel">
                    <option value="all">All Levels</option>
                    <option value="DEBUG">Debug</option>
                    <option value="INFO">Info</option>
                    <option value="WARNING">Warning</option>
                    <option value="ERROR">Error</option>
                </select>
                <input type="text" id="moduleFilter" placeholder="Filter by module name">
            </div>
            <div id="logContainer"></div>
        </div>

        <script>
            const logContainer = document.getElementById('logContainer');
            const refreshButton = document.getElementById('refreshButton');
            const clearButton = document.getElementById('clearButton');
            const streamButton = document.getElementById('streamButton');
            const logLevelSelect = document.getElementById('logLevel');
            const moduleFilter = document.getElementById('moduleFilter');
            
            let isStreaming = false;
            let eventSource = null;

            function displayLogs(logs) {
                // Filter logs based on selected level and module name
                const level = logLevelSelect.value;
                const moduleText = moduleFilter.value.toLowerCase();
                
                const filteredLogs = logs.filter(log => {
                    const levelMatch = level === 'all' || log.level === level;
                    const moduleMatch = !moduleText || log.module.toLowerCase().includes(moduleText);
                    return levelMatch && moduleMatch;
                });
                
                // Display the filtered logs
                logContainer.innerHTML = filteredLogs.map(log => `
                    <div class="log-entry">
                        <span class="timestamp">${log.timestamp}</span> -
                        <span class="level-${log.level}">${log.level}</span> -
                        <span class="module">${log.module}</span> -
                        <span class="message">${log.message}</span>
                    </div>
                `).join('');
                
                // Auto-scroll to bottom
                logContainer.scrollTop = logContainer.scrollHeight;
            }

            async function fetchLogs() {
                try {
                    const response = await fetch('/api/logs');
                    if (response.ok) {
                        const logs = await response.json();
                        displayLogs(logs);
                    } else {
                        console.error('Failed to fetch logs');
                    }
                } catch (error) {
                    console.error('Error fetching logs:', error);
                }
            }

            function startLogStream() {
                if (eventSource) {
                    eventSource.close();
                }
                
                eventSource = new EventSource('/api/logs/stream');
                isStreaming = true;
                streamButton.textContent = 'Stop Live Stream';
                
                eventSource.onmessage = function(event) {
                    try {
                        const logs = JSON.parse(event.data);
                        displayLogs(logs);
                    } catch (error) {
                        console.error('Error parsing log stream data:', error);
                    }
                };
                
                eventSource.onerror = function() {
                    stopLogStream();
                };
            }

            function stopLogStream() {
                if (eventSource) {
                    eventSource.close();
                    eventSource = null;
                }
                isStreaming = false;
                streamButton.textContent = 'Start Live Stream';
            }

            // Event listeners
            refreshButton.addEventListener('click', fetchLogs);
            
            clearButton.addEventListener('click', () => {
                logContainer.innerHTML = '';
            });
            
            streamButton.addEventListener('click', () => {
                if (isStreaming) {
                    stopLogStream();
                } else {
                    startLogStream();
                }
            });
            
            logLevelSelect.addEventListener('change', fetchLogs);
            
            moduleFilter.addEventListener('input', fetchLogs);
            
            // Initial load
            fetchLogs();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/logs")
async def get_logs():
    """Return all logs as JSON for the UI."""
    # Convert deque to list for serialization
    return JSONResponse(content=list(log_storage))

async def log_stream_generator():
    """Generator for streaming logs via SSE."""
    while True:
        # Convert deque to list for serialization and send as SSE
        yield f"data: {JSONResponse(content=list(log_storage)).body.decode()}\n\n"
        # Wait before sending the next update
        await asyncio.sleep(1)

@app.get("/api/logs/stream")
async def stream_logs():
    """Stream logs using Server-Sent Events (SSE)."""
    return StreamingResponse(
        log_stream_generator(),
        media_type="text/event-stream"
    )