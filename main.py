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
        # Create a temporary directory for git operations
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
              # Prepare the repo URL with username and token if provided
            repo_url = GIT_REPO_URL
            if "https://" in GIT_REPO_URL:
                # Proper authentication format: https://username:token@domain.com/repo
                if GIT_USERNAME and GIT_TOKEN:
                    # Insert both username and token into the URL for authentication
                    repo_url = GIT_REPO_URL.replace("https://", f"https://{GIT_USERNAME}:{GIT_TOKEN}@")
                elif GIT_TOKEN:
                    # If only token is provided, use it as the credential
                    repo_url = GIT_REPO_URL.replace("https://", f"https://oauth2:{GIT_TOKEN}@")
            
            # Clone the repository
            print(f"Cloning git repository from {GIT_REPO_URL} (branch: {GIT_BRANCH})...")
            repo = git.Repo.clone_from(repo_url, temp_path, branch=GIT_BRANCH)
            
            # Get a list of Python files
            synced_files = []
            
            # Create backup of current modules
            backup_dir = Path(f"{MODULES_DIR.parent}/modules_backup_{int(os.urandom(3).hex(), 16)}")
            if MODULES_DIR.exists() and any(MODULES_DIR.iterdir()):
                print(f"Creating backup of current modules at {backup_dir}")
                shutil.copytree(MODULES_DIR, backup_dir)
            
            # Copy Python files from the cloned repo to modules directory
            # excluding certain directories like .git, __pycache__, etc.
            exclude_dirs = {'.git', '__pycache__', '.github', '.vscode', '.idea'}
            
            # Create or ensure modules directory exists
            MODULES_DIR.mkdir(exist_ok=True)
            
            # Copy files from temp dir to modules dir
            for item in temp_path.glob('**/*'):
                if any(part for part in item.parts if part in exclude_dirs):
                    continue
                
                if item.is_file() and item.suffix == '.py':
                    # Get relative path from the temp_dir
                    rel_path = item.relative_to(temp_path)
                    target_path = MODULES_DIR / rel_path
                    
                    # Make sure the parent directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy the file
                    shutil.copy2(item, target_path)
                    synced_files.append(str(rel_path))
            
            # Load all modules after sync
            load_all_modules()
            
            return GitSyncResponse(
                success=True,
                message=f"Successfully synchronized {len(synced_files)} files from Git repository",
                synced_files=synced_files
            )
    
    except Exception as e:
        print(f"Error during Git synchronization: {e}")
        return GitSyncResponse(success=False, message=f"Git sync failed: {str(e)}")

def load_module(filename: str):
    """Dynamically loads or reloads a Python module and mounts its router."""
    module_name = filename.removesuffix(".py")
    filepath = MODULES_DIR / filename

    if not filepath.exists() or not filename.endswith(".py"):
        return # Skip if not a python file or doesn't exist

    try:
        # Invalidate caches to ensure reloading works
        importlib.invalidate_caches()

        # Construct the import path (e.g., modules.my_service)
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
            prefix = f"/{module_name}"
            # Unmount existing router if reloading
            if prefix in loaded_routers:
                 # FastAPI doesn't have a direct unmount. We rely on reload and potentially restart for full cleanup.
                 # For now, we just overwrite the entry in our tracking dict.
                 print(f"Router for {prefix} already exists. Reloading might require app restart for full effect.")

            app.include_router(router_instance, prefix=prefix, tags=[module_name])
            loaded_routers[prefix] = router_instance
            print(f"Mounted router from {filename} at {prefix}")
        else:
            print(f"No APIRouter found in {filename}")

    except Exception as e:
        print(f"Error loading module {filename}: {e}")
        # Optionally raise or handle the error more gracefully
        # raise HTTPException(status_code=500, detail=f"Error loading module {filename}: {e}")

def load_all_modules():
    """Loads all .py files from the modules directory."""
    print(f"Loading modules from: {MODULES_DIR.resolve()}")
    for filename in os.listdir(MODULES_DIR):
        if filename.endswith(".py") and filename != "__init__.py":
            load_module(filename)

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
async def upload_file(file: UploadFile = File(...)):
    """Uploads a Python file and loads it as a module."""
    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .py files are allowed.")

    filepath = MODULES_DIR / file.filename
    try:
        contents = await file.read()
        with open(filepath, "wb") as f:
            f.write(contents)

        # Attempt to load the newly uploaded module
        load_module(file.filename)

        return {"filename": file.filename, "message": "File uploaded and module loaded successfully."}
    except Exception as e:
        # Clean up partial file if upload failed
        if filepath.exists():
            os.remove(filepath)
        raise HTTPException(status_code=500, detail=f"Failed to upload or load file: {e}")
    finally:
        await file.close()

@app.get("/files", response_model=List[str])
def list_files():
    """Lists all .py files in the modules directory."""
    try:
        files = [f for f in os.listdir(MODULES_DIR) if f.endswith(".py") and f != "__init__.py"]
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {e}")

@app.get("/files/{filename}")
async def get_file_content(filename: str):
    """Returns the content of a specific Python file."""
    filepath = MODULES_DIR / filename
    if not filepath.exists() or not filename.endswith(".py"):
        raise HTTPException(status_code=404, detail="File not found or not a .py file.")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return JSONResponse(content={"filename": filename, "content": content})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

@app.post("/files/{filename}", status_code=200)
async def save_file_content(filename: str, file_data: FileContent = Body(...)):
    """Saves new content to a specific Python file and reloads the module."""
    filepath = MODULES_DIR / filename
    if not filepath.exists() or not filename.endswith(".py"):
        raise HTTPException(status_code=404, detail="File not found or not a .py file.")
    
    try:
        # Debug - print the received data
        print(f"Received data for {filename}: {file_data}")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(file_data.content)

        # Reload the module after saving changes
        load_module(filename)

        return {"filename": filename, "message": "File saved and module reloaded successfully."}
    except Exception as e:
        print(f"Error saving file {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save or reload file: {e}")

@app.delete("/files/{filename}", status_code=200)
async def delete_file(filename: str):
    """Deletes a specific Python file from the modules directory."""
    filepath = MODULES_DIR / filename
    if not filepath.exists() or not filename.endswith(".py"):
        raise HTTPException(status_code=404, detail="File not found or not a .py file.")
    
    try:
        # Check if the module is loaded and remove it from loaded_routers
        module_name = filename.removesuffix(".py")
        prefix = f"/{module_name}"
        if prefix in loaded_routers:
            # Note: FastAPI doesn't support true router removal at runtime
            # We just remove it from our tracking dictionary
            del loaded_routers[prefix]
        
        # Delete the file
        os.remove(filepath)
        return {"filename": filename, "message": "File deleted successfully."}
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