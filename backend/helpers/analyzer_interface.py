from abc import ABC, abstractmethod
from typing import List, Dict, Any
from PIL import Image


class ImageAnalyzerInterface(ABC):
    """
    Abstract interface for satellite image analysis.
    Implementations can use local models, cloud APIs, etc.
    """

    @abstractmethod
    async def analyze_images(
        self,
        images: List[Image.Image],
        analysis_type: str,
        image_id: str,
        image_names: List[str],
        box_threshold: float = 0.2,
        text_threshold: float = 0.2,
    ) -> List[Dict[str, Any]]:
        """
        Analyze images for specific objects.

        Args:
            images: List of PIL Images to analyze
            analysis_type: Type of object to detect (e.g., "car", "building")
            image_id: Unique identifier for this batch
            image_names: Names corresponding to each image
            box_threshold: Confidence threshold for bounding boxes
            text_threshold: Confidence threshold for text matching

        Returns:
            List of dicts containing:
                - count: Number of detected objects
                - boxes: Bounding box coordinates (if available)
                - image_path: Path to processed/annotated image
        """
        pass 