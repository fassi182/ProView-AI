from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, chat, document, history  # Imported history module

app = FastAPI(
    title="ProView AI Core Microservice",
    description="Decoupled high-performance backend orchestrating auth, RAG, and live AI Interview Simulations.",
    version="2.0.0"
)

# Crucial security configuration enabling any universal frontend interface (React Native or Web) to consume your API safely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows web pages or mobile wrappers from any network to talk to this backend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bind all active system routing modules
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(document.router)
app.include_router(history.router)  # Attached session history retrieval pathways

@app.get("/health", tags=["System Health"])
async def health_check():
    """
    Simple health check endpoint to verify that the containerized API 
    is alive and accessible globally.
    """
    return {"status": "alive", "engine": "FastAPI + Supabase Cloud"}

if __name__ == "__main__":
    import uvicorn
    # Starts the high-performance ASGI server locally on port 8000 with auto-reload active
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)