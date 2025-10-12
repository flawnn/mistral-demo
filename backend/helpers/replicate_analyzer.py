import os
import base64
from io import BytesIO
from typing import List, Dict, Any
from PIL import Image, ImageDraw, ImageFont
import replicate

from .analyzer_interface import ImageAnalyzerInterface


class ReplicateAnalyzer(ImageAnalyzerInterface):
    """
    Image analyzer using Replicate's hosted Grounding DINO model.
    No local GPU/CUDA required - all inference happens via API.
    """

    MODEL_VERSION = "adirik/grounding-dino:efd10a8ddc57ea28773327e881ce95e20cc1d734c589f7dd01d2036921ed78aa"

    def __init__(self, api_token: str | None = None):
        """
        Initialize Replicate client.

        Args:
            api_token: Replicate API token (defaults to REPLICATE_API_TOKEN env var)
        """
        self.client = replicate.Client(api_token=api_token or os.getenv("REPLICATE_API_TOKEN"))

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
        Analyze images using Replicate's Grounding DINO API.
        """
        results = []

        for image, image_name in zip(images, image_names):
            result = await self._analyze_single_image(
                image=image,
                analysis_type=analysis_type,
                image_id=image_id,
                image_name=image_name,
                box_threshold=box_threshold,
                text_threshold=text_threshold,
            )
            results.append(result)

        return results

    async def _analyze_single_image(
        self,
        image: Image.Image,
        analysis_type: str,
        image_id: str,
        image_name: str,
        box_threshold: float,
        text_threshold: float,
    ) -> Dict[str, Any]:
        """
        Analyze a single image via Replicate API.
        """
        image_data_uri = self._image_to_data_uri(image)

        query = f"{analysis_type}."

        output = await self.client.async_run(
            self.MODEL_VERSION,
            input={
                "image": image_data_uri,
                "query": query,
                "box_threshold": box_threshold,
                "text_threshold": text_threshold,
                "show_visualisation": True,
            },
        )

        count = self._extract_count(output)
        boxes = self._extract_boxes(output)

        os.makedirs(f"processed_data/{image_id}", exist_ok=True)

        if output.get("visualization"):
            visualized_image = self._download_visualization(output["visualization"])
            output_path = f"processed_data/{image_id}/{image_name}.png"
            visualized_image.save(output_path)
        else:
            annotated_image = self._draw_boxes_on_image(image.copy(), boxes)
            output_path = f"processed_data/{image_id}/{image_name}.png"
            annotated_image.save(output_path)

        return {
            "count": count,
            "boxes": boxes,
            "image_path": output_path,
        }

    def _image_to_data_uri(self, image: Image.Image) -> str:
        """
        Convert PIL Image to data URI for Replicate API.
        """
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        img_base64 = base64.b64encode(img_bytes).decode()
        return f"data:image/png;base64,{img_base64}"

    def _extract_count(self, output: Dict[str, Any]) -> int:
        """
        Extract detection count from Replicate output.
        """
        if isinstance(output, dict):
            detections = output.get("detections", [])
            return len(detections) if detections else 0
        return 0

    def _extract_boxes(self, output: Dict[str, Any]) -> List[List[float]]:
        """
        Extract bounding boxes from Replicate output.
        Format: [[x1, y1, x2, y2], ...]
        """
        if isinstance(output, dict):
            detections = output.get("detections", [])
            boxes = []
            for detection in detections:
                if "box" in detection:
                    box = detection["box"]
                    boxes.append([box.get("x1", 0), box.get("y1", 0), box.get("x2", 0), box.get("y2", 0)])
            return boxes
        return []

    def _download_visualization(self, viz_url: str) -> Image.Image:
        """
        Download visualization image from Replicate output URL.
        """
        import requests

        response = requests.get(viz_url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))

    def _draw_boxes_on_image(self, image: Image.Image, boxes: List[List[float]]) -> Image.Image:
        """
        Draw bounding boxes on image (fallback if visualization not provided).
        """
        draw = ImageDraw.Draw(image)

        try:
            font = ImageFont.truetype("Arial.ttf", 20)
        except:
            font = ImageFont.load_default()

        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
            draw.text((x1, y1 - 10), f"#{i+1}", fill="red", font=font)

        return image 