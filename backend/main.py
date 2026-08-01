from fastapi import FastAPI

app = FastAPI(title="HeyPico Maps Proxy API")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Backend API is running successfully"}
