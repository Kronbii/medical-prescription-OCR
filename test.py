import io
import os
import time
from google.cloud import vision

# ---------------------------------------------
# CONFIGURATION
# ---------------------------------------------
# Path to your Google Cloud service account key (.json)
SERVICE_ACCOUNT_PATH = "resource/client_secret_code1.json"

# Path to the image you want to analyze
IMAGE_PATH = "/home/kronbii/test.png"

# Optional: output text file
OUTPUT_TEXT_FILE = "prescription_text.txt"


# ---------------------------------------------
# MAIN FUNCTION
# ---------------------------------------------
def extract_text_from_prescription(image_path: str) -> str:
    """
    Uses Google Cloud Vision API to extract text from a medical prescription image.
    Returns recognized text as a string.
    """
    # Initialize Vision API client
    client = vision.ImageAnnotatorClient.from_service_account_json(SERVICE_ACCOUNT_PATH)

    # Load image bytes
    with io.open(image_path, "rb") as image_file:
        content = image_file.read()
    image = vision.Image(content=content)

    print(f"[INFO] Sending '{image_path}' to Google Vision API...")
    start_time = time.time()

    # Perform OCR (document_text_detection gives more detailed layout)
    response = client.document_text_detection(image=image)
    end_time = time.time()

    # Check for API errors
    if response.error.message:
        raise Exception(f"Vision API Error: {response.error.message}")

    # Extract full text
    result_text = response.full_text_annotation.text
    print(f"[INFO] Inference done in {end_time - start_time:.2f}s.")
    print("=" * 50)
    print(result_text)
    print("=" * 50)

    # Save text to file
    if result_text.strip():
        with open(OUTPUT_TEXT_FILE, "w", encoding="utf-8") as f:
            f.write(result_text)
        print(f"[INFO] Extracted text saved to {OUTPUT_TEXT_FILE}")

    return result_text


# ---------------------------------------------
# ENTRY POINT
# ---------------------------------------------
if __name__ == "__main__":
    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        print(f"[ERROR] Service account file not found: {SERVICE_ACCOUNT_PATH}")
        print("→ Create it in Google Cloud Console > Credentials > Service Account > Create Key (JSON).")
        exit(1)

    if not os.path.exists(IMAGE_PATH):
        print(f"[ERROR] Image not found: {IMAGE_PATH}")
        exit(1)

    try:
        text = extract_text_from_prescription(IMAGE_PATH)
    except Exception as e:
        print("[ERROR]", e)
