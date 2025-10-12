import os
from PIL import Image
from io import BytesIO
import base64
from helpers.satellite_downloader import SatelliteDownloader
from helpers.analyzer_factory import create_analyzer
from config import config


class SatelliteBackend:

    def __init__(self):
        self.images_db = {}
        self.image_names = {}
        self.satellite_downloader = SatelliteDownloader()
        
        # Use factory to get appropriate analyzer
        self.satellite_analyzer = create_analyzer()
        
        # Read all existing images from filesystem
        data_dir = config.DATA_DIR
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            self.image_ids = []
        else:
            self.image_ids = [f.name for f in os.scandir(data_dir) if f.is_dir()]

        # Load images into memory (these are already PIL images from disk)
        for image_id in self.image_ids:
            image_dir = f"{data_dir}/{image_id}"
            if os.path.exists(image_dir):
                image_files = [file for file in os.scandir(image_dir) if file.name.endswith(('.jpg', '.jpeg', '.png'))]
                images = [Image.open(f"{image_dir}/{file.name}") for file in image_files]
                self.images_db[image_id] = images
                self.image_names[image_id] = [file.name for file in image_files]

    def download_satellite_images(self, latitude: float, longitude: float, zoom: int):
        """
        Download satellite images for given coordinates.
        """
        image_id, images = self.satellite_downloader.download(latitude, longitude, zoom)

        # Extract PIL images from MapTileImage wrappers
        pil_images = [img.image if hasattr(img, 'image') else img for img in images]
        self.images_db[str(image_id)] = pil_images
        
        # Get image names from downloaded images
        image_dir = f"{config.DATA_DIR}/{image_id}"
        if os.path.exists(image_dir):
            self.image_names[str(image_id)] = [f.name for f in os.scandir(image_dir) if f.name.endswith(('.jpg', '.jpeg', '.png'))]

        # Use original images for tobytes (MapTileImage has custom tobytes method)
        images_bytes = [image.tobytes() for image in images]

        return {
            "image_id": str(image_id),
            "images": images_bytes
        }

    async def analyze_satellite_images(self, image_id: str, analysis_type: str):
        """
        Analyze satellite images using configured analyzer (async).
        Images in database are PIL Image.Image objects (extracted from MapTileImage wrappers).
        """
        if image_id not in self.images_db:
            return {"error": "Image not found"}

        images = self.images_db[image_id]  # PIL Image.Image objects
        image_names = self.image_names.get(image_id, [f"image_{i}" for i in range(len(images))])

        os.makedirs(f"{config.PROCESSED_DATA_DIR}/{image_id}", exist_ok=True)

        # Call async analyzer
        processed_image_paths = await self.satellite_analyzer.analyze_images(
            images=images,
            analysis_type=analysis_type,
            image_id=image_id,
            image_names=image_names,
            box_threshold=config.DEFAULT_BOX_THRESHOLD,
            text_threshold=config.DEFAULT_TEXT_THRESHOLD,
        )

        # Load processed images and convert to JSON-safe format
        processed_images = []
        for processed_path_info in processed_image_paths:
            try:
                img = Image.open(processed_path_info["image_path"])
                processed_images.append(self.image_to_json_safe(img))
            except Exception as e:
                print(f"Error loading processed image: {e}")
                processed_images.append(None)

        counts = [result["count"] for result in processed_image_paths]

        return {
            "image_id": image_id,
            "processed_images": processed_images,
            "counts": counts
        }

    def image_to_json_safe(self, pil_image: Image.Image) -> str:
        """
        Convert PIL image to base64 string for JSON serialization.
        """
        buffered = BytesIO()
        pil_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return img_str