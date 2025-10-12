
import requests

import torch
from PIL import Image
import matplotlib.pyplot as plt
from PIL import ImageDraw, ImageFont
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
from torchvision.ops import box_iou
import os
from typing import List, Dict, Any

from .analyzer_interface import ImageAnalyzerInterface


class SatelliteAnalyzer(ImageAnalyzerInterface):
    """
    Local GPU-based analyzer using Grounding DINO.
    Requires CUDA and transformers library.
    """

    def __init__(self):
        self.images = {}

        model_id = "IDEA-Research/grounding-dino-base"
        self.device = "cuda"

        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id).to(self.device)

    async def analyze_images(
        self,
        images: List[Image.Image],
        analysis_type: str,
        image_id: str,
        image_names: List[str],
        box_threshold: float = 0.2,
        text_threshold: float = 0.9,
    ) -> List[Dict[str, Any]]:
        """
        Async wrapper for local model inference.
        """
        results = []
        for image, image_name in zip(images, image_names):
            count, boxes, _ = self.counting(
                image, 
                analysis_type, 
                plot=True, 
                box_threshold=box_threshold, 
                text_threshold=text_threshold, 
                image_id=image_id, 
                image_name=image_name
            )
            print(f"Number of {analysis_type} in the image: {count}")
            results.append({
                "count": count,
                "boxes": boxes.tolist() if hasattr(boxes, 'tolist') else boxes,
                "image_path": f"processed_data/{image_id}/{image_name}.png"
            })

        return results

    def find_jpgs(self, directory):
        return [f for f in os.listdir(directory) if f.endswith('.jpg')]

    def plot_boxes(self, image, results):
        # Convert the image to a drawable format
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()  # Default font; customize if needed

        for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
            # Convert box to a list and extract coordinates
            box = box.tolist()
            x0, y0, x1, y1 = box

            # Draw the bounding box
            draw.rectangle([x0, y0, x1, y1], outline="red", width=3)

            # Draw the label and score
            text = f"{label} ({score:.2f})"
            text_size = draw.textbbox((0, 0), text, font=font)  # Use textbbox to calculate the text size
            text_width = text_size[2] - text_size[0]
            text_height = text_size[3] - text_size[1]

            # Add background for text
            draw.rectangle([x0, y0 - text_height, x0 + text_width, y0], fill="red")
            draw.text((x0, y0 - text_height), text, fill="white", font=font)

        return image

    def remove_overlapping_boxes_from_results(results, iou_threshold=0.5):
        """
        Removes overlapping bounding boxes from results dictionary, keeping the smaller box.

        Args:
            results (dict): Dictionary containing "boxes", "scores", and "labels".
                            - "boxes" is a tensor of shape (num_boxes, 4) with box coordinates (x1, y1, x2, y2).
                            - "scores" is a tensor of shape (num_boxes,) with confidence scores.
                            - "labels" is a list of labels corresponding to the boxes.
            iou_threshold (float): IoU overlap threshold for filtering.

        Returns:
            dict: Filtered results dictionary.
        """
        boxes = results["boxes"]
        scores = results["scores"]
        labels = results["labels"]

        # Compute pairwise IoU
        iou_matrix = box_iou(boxes, boxes)

        # Keep track of which boxes to remove
        keep = set(range(len(boxes)))

        for i in range(len(boxes)):
            if i not in keep:
                continue

            for j in range(i + 1, len(boxes)):
                if j not in keep:
                    continue

                # If IoU exceeds the threshold, keep the smaller box
                if iou_matrix[i, j] > iou_threshold:
                    # Calculate areas of the boxes
                    area_i = (boxes[i][2] - boxes[i][0]) * (boxes[i][3] - boxes[i][1])
                    area_j = (boxes[j][2] - boxes[j][0]) * (boxes[j][3] - boxes[j][1])

                    if area_i <= area_j:
                        keep.remove(j)  # Keep i, remove j
                    else:
                        keep.remove(i)  # Keep j, remove i
                        break

        # Convert keep to a sorted list of indices
        keep = sorted(keep)

        # Filter the boxes, scores, and labels based on the indices to keep
        filtered_results = {
            "boxes": boxes[keep],
            "scores": scores[keep],
            "labels": [labels[i] for i in keep],  # Filter labels using list comprehension
        }

        return filtered_results

    def counting(self, image, looking_for, plot=True, box_threshold=0.2, text_threshold=0.9, image_id=None, image_name=None):
        text = f"{looking_for}."

        inputs = self.processor(images=image, text=text, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)

        results = self.processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            box_threshold=box_threshold,
            text_threshold=text_threshold,
            target_sizes=[image.size[::-1]]
        )

        if plot:
            image_with_boxes = self.plot_boxes(image.copy(), self.remove_overlapping_boxes_from_results(results[0], 0.5))
            count_boxes = len(results[0]["boxes"])

            plt.figure(figsize=(10, 10))
            plt.imshow(image_with_boxes)
            plt.axis("off")
            # plt.show()
            
            # Create a directory data/processed if it doesn't exist
            os.makedirs("data/processed", exist_ok=True)

            # Create processed_data/{image_id} folder if it doesn't exist
            os.makedirs(f"processed_data/{image_id}", exist_ok=True)
            plt.savefig(f"processed_data/{image_id}/{image_name}.png")

            print(f"Number of {looking_for} in the image: {count_boxes}")

            return count_boxes, results[0]["boxes"], image_with_boxes

        return len(results[0]["boxes"]), results[0]["boxes"]