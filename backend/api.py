import fastapi
from fastapi.middleware.cors import CORSMiddleware
from main import SatelliteBackend
from config import config

app = fastapi.FastAPI()
satellite_backend = SatelliteBackend()

# Add CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.on_event("startup")
async def startup_event():
    """
    Validate configuration on startup.
    """
    try:
        config.validate()
        print(f"✅ Backend started with analyzer: {config.ANALYZER_TYPE.value}")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        raise


@app.get("/")
def home():
    return {
        "message": "Satellite Analysis API",
        "analyzer": config.ANALYZER_TYPE.value,
        "status": "ready"
    }


@app.get("/downloadSatelliteImages")
def download_satellite_images(
    latitude: float = fastapi.Query(..., description="Latitude coordinate"),
    longitude: float = fastapi.Query(..., description="Longitude coordinate"),
    zoom: int = fastapi.Query(default=10, description="Zoom level")
):
    """
    Download satellite images for given coordinates.
    """
    print(f"Downloading satellite images for {latitude}, {longitude} with zoom {zoom}")

    return satellite_backend.download_satellite_images(latitude, longitude, zoom)


@app.get("/analyzeSatelliteImages")
async def analyze_satellite_images(
    image_id: str = fastapi.Query(..., description="Image ID to analyze"),
    analysis_type: str = fastapi.Query(default="basic", description="Type of object to detect"),
):
    """
    Analyze satellite images using configured analyzer (Replicate or local).
    """
    print(f"Analyzing images {image_id} for {analysis_type}")
    
    return await satellite_backend.analyze_satellite_images(image_id, analysis_type)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)