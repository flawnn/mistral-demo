import fastapi
from config import config
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from main import SatelliteBackend

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


def validate_coordinates(latitude: float, longitude: float) -> None:
    """
    Validate latitude and longitude coordinates.
    
    Raises:
        HTTPException: If coordinates are invalid
    """
    # Check for 0,0 (common error/default value)
    if latitude == 0 and longitude == 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid coordinates: (0, 0). Please provide valid location coordinates."
        )
    
    # Validate latitude range
    if not -90 <= latitude <= 90:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid latitude: {latitude}. Latitude must be between -90 and 90 degrees."
        )
    
    # Validate longitude range
    if not -180 <= longitude <= 180:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid longitude: {longitude}. Longitude must be between -180 and 180 degrees."
        )


@app.get("/")
def home():
    return {
        "message": "Satellite Analysis API",
        "analyzer": config.ANALYZER_TYPE.value,
        "status": "ready"
    }


@app.get("/downloadSatelliteImages")
def download_satellite_images(
    latitude: float = fastapi.Query(..., description="Latitude coordinate (-90 to 90)"),
    longitude: float = fastapi.Query(..., description="Longitude coordinate (-180 to 180)"),
    zoom: int = fastapi.Query(default=10, description="Zoom level", ge=1, le=20)
):
    """
    Download satellite images for given coordinates.
    
    Validates coordinates before processing:
    - Rejects (0, 0) as it's typically an error
    - Ensures latitude is between -90 and 90
    - Ensures longitude is between -180 and 180
    """
    # Validate coordinates
    validate_coordinates(latitude, longitude)
    
    print(f"✅ Downloading satellite images for {latitude}, {longitude} with zoom {zoom}")

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