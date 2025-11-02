import base64
import os
from io import BytesIO
from typing import Any, Dict, List

import replicate
from config import config
from PIL import Image, ImageDraw, ImageFont

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
        # Extract PIL image if wrapped
        if hasattr(image, 'image'):
            image = image.image
        
        # Store original image size for coordinate conversion
        original_size = image.size
            
        image_data_uri = self._image_to_data_uri(image)

        query = f"{analysis_type}."

        try:
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
            print(f"🔍 Replicate API Response Type: {type(output)}")
            print(f"🔍 Replicate API Response: {output}")
        except Exception as e:
            print(f"❌ Replicate API error: {e}")
            raise

        count = self._extract_count(output)
        boxes = self._extract_boxes(output, original_size)

        os.makedirs(f"processed_data/{image_id}", exist_ok=True)

        # Handle Replicate output format
        visualization_url = None
        if isinstance(output, dict):
            visualization_url = output.get("visualization")
        elif isinstance(output, str):
            # Sometimes Replicate returns a URL directly
            visualization_url = output
        
        print(f"🖼️  Visualization URL: {visualization_url}")

        # Always draw boxes manually since we have more control
        # and can ensure they're visible
        if boxes:
            print(f"✏️  Drawing {len(boxes)} bounding boxes on image")
            annotated_image = self._draw_boxes_on_image(image.copy(), boxes)
            output_path = f"processed_data/{image_id}/{image_name}.png"
            annotated_image.save(output_path)
            print(f"💾 Saved annotated image to: {output_path}")
        else:
            print(f"⚠️  No boxes to draw, saving original image")
            output_path = f"processed_data/{image_id}/{image_name}.png"
            image.save(output_path)
            print(f"💾 Saved original image to: {output_path}")

        return {
            "count": count,
            "boxes": boxes,
            "image_path": output_path,
        }

    def _image_to_data_uri(self, image: Image.Image) -> str:
        """
        Convert PIL Image to data URI for Replicate API.
        Handles MapTileImage wrappers and RGBA conversion.
        """
        # Extract PIL image if wrapped
        if hasattr(image, 'image'):
            image = image.image
        
        # Convert RGBA to RGB if needed (JPEG doesn't support transparency)
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=config.IMAGE_QUALITY, optimize=True)
        img_bytes = buffered.getvalue()
        img_base64 = base64.b64encode(img_bytes).decode()
        base64_size = len(img_base64)
        print(f"📤 Upload size: {base64_size / 1024 / 1024:.2f}MB (base64)")
        
        return f"data:image/jpeg;base64,{img_base64}"

    def _extract_count(self, output: Dict[str, Any]) -> int:
        """
        Extract detection count from Replicate output.
        """
        if isinstance(output, dict):
            detections = output.get("detections", [])
            return len(detections) if detections else 0
        return 0

    def _extract_boxes(self, output: Dict[str, Any], image_size: tuple) -> List[List[float]]:
        """
        Extract bounding boxes from Replicate output.
        Handles both normalized (0-1) and pixel coordinates.
        Format: [[x1, y1, x2, y2], ...]
        """
        boxes = []
        
        if isinstance(output, dict):
            detections = output.get("detections", [])
            
            if not detections:
                print(f"⚠️  No detections found in output")
                print(f"    Output keys: {list(output.keys())}")
                return boxes
            
            print(f"✅ Found {len(detections)} detections")
            
            width, height = image_size
            
            for i, detection in enumerate(detections):
                # Replicate returns 'bbox' not 'box'!
                if "bbox" in detection or "box" in detection:
                    # Get bbox as list [x1, y1, x2, y2] or as dict
                    bbox = detection.get("bbox") or detection.get("box")
                    
                    # Handle list format [x1, y1, x2, y2]
                    if isinstance(bbox, list) and len(bbox) == 4:
                        x1, y1, x2, y2 = bbox
                    # Handle dict format {x1: ..., y1: ..., x2: ..., y2: ...}
                    elif isinstance(bbox, dict):
                        x1 = bbox.get("x1", bbox.get("xmin", 0))
                        y1 = bbox.get("y1", bbox.get("ymin", 0))
                        x2 = bbox.get("x2", bbox.get("xmax", 0))
                        y2 = bbox.get("y2", bbox.get("ymax", 0))
                    else:
                        print(f"⚠️  Detection {i+1} has invalid bbox format: {bbox}")
                        continue
                    
                    # Check if coordinates are normalized (0-1) and convert to pixels
                    if 0 <= x1 <= 1 and 0 <= y1 <= 1 and 0 <= x2 <= 1 and 0 <= y2 <= 1:
                        x1, x2 = x1 * width, x2 * width
                        y1, y2 = y1 * height, y2 * height
                        print(f"   Detection {i+1}: Converted normalized coords to pixels")
                    
                    boxes.append([x1, y1, x2, y2])
                    
                    if i < 5 or (i + 1) == len(detections):  # Log first 5 and last
                        print(f"   Detection {i+1}: Box [{x1:.0f}, {y1:.0f}, {x2:.0f}, {y2:.0f}]")
                else:
                    print(f"⚠️  Detection {i+1} missing bbox/box field: {detection}")
            
        return boxes

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
        Draw bounding boxes on image with enhanced visibility.
        """
        if not boxes:
            return image
        
        draw = ImageDraw.Draw(image)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            try:
                font = ImageFont.truetype("Arial.ttf", 24)
            except:
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
                except:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)

        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box
            
            # Draw box with thick outline
            draw.rectangle([x1, y1, x2, y2], outline="red", width=5)
            
            # Draw label background
            label = f"#{i+1}"
            label_bbox = draw.textbbox((x1, y1), label, font=font)
            label_width = label_bbox[2] - label_bbox[0]
            label_height = label_bbox[3] - label_bbox[1]
            
            # Position label above box, or inside if box is at top
            label_y = y1 - label_height - 5 if y1 > label_height + 5 else y1 + 5
            
            # Draw white background for label
            draw.rectangle(
                [x1, label_y, x1 + label_width + 4, label_y + label_height + 4],
                fill="red"
            )
            
            # Draw label text
            draw.text((x1 + 2, label_y + 2), label, fill="white", font=font)

        return image 