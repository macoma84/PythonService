import os
import sys
import importlib
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, UploadFile, HTTPException, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Ensure the modules directory is in the Python path
MODULES_DIR = Path("modules")
MODULES_DIR.mkdir(exist_ok=True)
if str(MODULES_DIR.resolve()) not in sys.path:
    sys.path.insert(0, str(MODULES_DIR.resolve().parent)) # Add parent of modules to path

app = FastAPI(title="Dynamic Microservice Runner")

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory store for loaded routers to prevent duplicate mounting
loaded_routers = {}

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
    """Load all modules on application startup."""
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
async def save_file_content(filename: str, content: str):
    """Saves new content to a specific Python file and reloads the module."""
    filepath = MODULES_DIR / filename
    if not filepath.exists() or not filename.endswith(".py"):
        raise HTTPException(status_code=404, detail="File not found or not a .py file.")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        # Reload the module after saving changes
        load_module(filename)

        return {"filename": filename, "message": "File saved and module reloaded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save or reload file: {e}")