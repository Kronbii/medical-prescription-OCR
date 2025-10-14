import io
import os
import time
import json
import cv2
import numpy as np
from google.cloud import vision

# ---------------------------------------------
# CONFIGURATION
# ---------------------------------------------
SERVICE_ACCOUNT_PATH = "resource/vision-api.json"
IMAGE_PATH = "/home/kronbii/test.png"
OUTPUT_TEXT_FILE = "prescription_text.txt"
OUTPUT_JSON_FILE = "vision_full_response.json"
OUTPUT_IMAGE_FILE = "prescription_annotated.png"


# ---------------------------------------------
# MAIN FUNCTION
# ---------------------------------------------
def extract_text_from_prescription(image_path: str):
    """
    Uses Google Cloud Vision API to extract text from a medical prescription image.
    Saves full JSON response and an annotated image.
    """
    # Initialize Vision API client
    client = vision.ImageAnnotatorClient.from_service_account_json(SERVICE_ACCOUNT_PATH)

    # Load image bytes
    with io.open(image_path, "rb") as image_file:
        content = image_file.read()
    image = vision.Image(content=content)

    print(f"[INFO] Sending '{image_path}' to Google Vision API...")
    start_time = time.time()

    # Perform OCR
    response = client.document_text_detection(image=image)
    end_time = time.time()

    if response.error.message:
        raise Exception(f"Vision API Error: {response.error.message}")

    print(f"[INFO] Inference done in {end_time - start_time:.2f}s.")

    # Convert full response to dict and save
    response_dict = json.loads(vision.AnnotateImageResponse.to_json(response))
    with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(response_dict, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Full Vision API response saved to {OUTPUT_JSON_FILE}")

    # Extract text
    result_text = response.full_text_annotation.text
    if result_text.strip():
        with open(OUTPUT_TEXT_FILE, "w", encoding="utf-8") as f:
            f.write(result_text)
        print(f"[INFO] Extracted text saved to {OUTPUT_TEXT_FILE}")

    # Draw bounding boxes
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise FileNotFoundError("Could not read the input image.")

    # Loop over words to draw boxes and labels
    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    word_text = "".join([symbol.text for symbol in word.symbols])
                    box = [(v.x, v.y) for v in word.bounding_box.vertices]
                    if len(box) == 4:
                        pts = np.array(box, np.int32).reshape((-1, 1, 2))
                        cv2.polylines(image_bgr, [pts], isClosed=True, color=(0, 255, 0), thickness=2)

                        # Text position (top-left corner)
                        x, y = box[0]
                        cv2.putText(
                            image_bgr,
                            word_text,
                            (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 0, 255),
                            2,
                            cv2.LINE_AA,
                        )

    # Save annotated image
    cv2.imwrite(OUTPUT_IMAGE_FILE, image_bgr)
    print(f"[INFO] Annotated image saved to {OUTPUT_IMAGE_FILE}")
    print("=" * 60)
    print(result_text)
    print("=" * 60)

    return result_text


# ---------------------------------------------
# ENTRY POINT
# ---------------------------------------------
if __name__ == "__main__":
    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        print(f"[ERROR] Service account file not found: {SERVICE_ACCOUNT_PATH}")
        exit(1)

    if not os.path.exists(IMAGE_PATH):
        print(f"[ERROR] Image not found: {IMAGE_PATH}")
        exit(1)

    try:
        extract_text_from_prescription(IMAGE_PATH)
    except Exception as e:
        print("[ERROR]", e)
