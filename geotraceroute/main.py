from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn
import argparse
from pathlib import Path
from dotenv import load_dotenv
from geotraceroute.api.routes import router

app = FastAPI(
    title="GeoTraceroute API",
    description="API for performing traceroute with geographical information",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production environment, this should be restricted to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "web" / "templates"))

# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "web" / "static"), name="static")

# Include routes - router already has prefix '/api'
app.include_router(router)

# Add root path route
@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    """Return the frontend homepage"""
    return templates.TemplateResponse("index.html", {"request": request})

def main():
    """Run the application as a script"""
    # Load environment variables
    load_dotenv()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='GeoTraceroute web application')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    parser.add_argument('--workers', type=int, default=1, help='Number of worker processes')
    
    args = parser.parse_args()

    # Start the service
    uvicorn.run(
        "geotraceroute.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers
    )

if __name__ == "__main__":
    main() 