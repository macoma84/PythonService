from fastapi import APIRouter

router = APIRouter()

@router.get("/hello")
async def say_hello():
    """Returns a simple greeting."""
    return {"message": "Hello from the example service!"}