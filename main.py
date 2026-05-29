from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, chat, document, history  # Imported history module

app = FastAPI(
    title="ProView AI Core Microservice",
    docs_url="/docs"
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

@app.get("/")
async def root():
    return {"message": "The API is live and connected!"}

if __name__ == "__main__":
    import uvicorn
    # Starts the high-performance ASGI server locally on port 8000 with auto-reload active
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)