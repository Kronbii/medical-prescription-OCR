import os
import json
import time
import cv2
import torch
import numpy as np
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

# --- Config ---
IMAGE_PATH = "test.png"
OUTPUT_JSON = "out.json"
OUTPUT_IMG = "out_vis.png"
MAX_TOKENS = 64
MODEL_NAME = "microsoft/trocr-large-handwritten"
EAST_MODEL = "frozen_east_text_detection.pb"

# --- Logging helpers ---
def log(msg):
    t = time.strftime("%H:%M:%S")
    print(f"[{t}] {msg}")

# --- Text Detection (EAST) ---
def detect_text_regions(image_path, conf_threshold=0.5, nms_threshold=0.7):
    log("Loading image for detection...")
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not read {image_path}")
    orig = image.copy()
    (H, W) = image.shape[:2]

    newW, newH = (320, 320)  # keep same as your base code
    rW = W / float(newW)
    rH = H / float(newH)
    image = cv2.resize(image, (newW, newH))
    blob = cv2.dnn.blobFromImage(
        image, 1.0, (newW, newH),
        (123.68, 116.78, 103.94), swapRB=True, crop=False
    )

    log("Loading EAST network...")
    net = cv2.dnn.readNet(EAST_MODEL)
    # (no GPU backend set — original behavior)

    log("Running EAST forward pass...")
    start = time.time()
    net.setInput(blob)
    (scores, geometry) = net.forward(
        ["feature_fusion/Conv_7/Sigmoid", "feature_fusion/concat_3"]
    )
    det_time = time.time() - start
    log(f"EAST forward pass done in {det_time:.2f}s")

    numRows, numCols = scores.shape[2:4]
    rects = []
    confidences = []

    for y in range(numRows):
        scoresData = scores[0, 0, y]
        xData0 = geometry[0, 0, y]
        xData1 = geometry[0, 1, y]
        xData2 = geometry[0, 2, y]
        xData3 = geometry[0, 3, y]
        anglesData = geometry[0, 4, y]

        for x in range(numCols):
            if scoresData[x] < conf_threshold:
                continue

            offsetX, offsetY = (x * 4.0, y * 4.0)
            angle = anglesData[x]
            cos = np.cos(angle)
            sin = np.sin(angle)
            h = xData0[x] + xData2[x]
            w = xData1[x] + xData3[x]

            endX = int(offsetX + (cos * xData1[x]) + (sin * xData2[x]))
            endY = int(offsetY - (sin * xData1[x]) + (cos * xData2[x]))
            startX = int(endX - w)
            startY = int(endY - h)

            rects.append([startX, startY, int(w), int(h)])
            confidences.append(float(scoresData[x]))

    indices = cv2.dnn.NMSBoxes(rects, confidences, conf_threshold, nms_threshold)
    final_boxes = []
    if len(indices) > 0:
        for i in indices.flatten():
            (x, y, w, h) = rects[i]
            startX = int(x * rW)
            startY = int(y * rH)
            endX = int((x + w) * rW)
            endY = int((y + h) * rH)
            final_boxes.append((startX, startY, endX, endY))

    log(f"Detected {len(final_boxes)} text boxes.")
    return orig, final_boxes


# --- Handwriting recognizer ---
class HandwritingRecognizer:
    def __init__(self, model_name=MODEL_NAME):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        log(f"Loading TrOCR model ({model_name}) on {self.device}...")
        t0 = time.time()
        self.processor = TrOCRProcessor.from_pretrained(model_name)
        self.model = VisionEncoderDecoderModel.from_pretrained(model_name).to(self.device)
        self.model.eval()
        log(f"TrOCR model loaded in {time.time() - t0:.2f}s")

    @torch.no_grad()
    def recognize(self, images):
        if not images:
            return []
        pixel_values = self.processor(images=images, return_tensors="pt").pixel_values.to(self.device)
        start = time.time()
        gen = self.model.generate(pixel_values, max_new_tokens=MAX_TOKENS)
        texts = self.processor.batch_decode(gen, skip_special_tokens=True)
        log(f"TrOCR inference for {len(images)} crops took {time.time() - start:.2f}s")
        return texts


# --- Visualization helper ---
def visualize(image, boxes, texts):
    vis = image.copy()
    for (box, text) in zip(boxes, texts):
        (x1, y1, x2, y2) = box
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(vis, text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 200, 50), 2)
    return vis


# --- Main pipeline ---
def main():
    total_start = time.time()
    log("=== OCR Pipeline Started ===")

    # 1. Detection
    t0 = time.time()
    image, boxes = detect_text_regions(IMAGE_PATH)
    t1 = time.time()
    log(f"Detection total time: {t1 - t0:.2f}s")

    if not boxes:
        log("No text boxes detected.")
        return

    # 2. Crop regions
    crops = []
    for (x1, y1, x2, y2) in boxes:
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        crops.append(Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)))
    log(f"Prepared {len(crops)} crops for recognition.")

    # 3. Recognition
    recognizer = HandwritingRecognizer()
    texts = recognizer.recognize(crops)

    # 4. Save outputs
    vis_img = visualize(image, boxes, texts)
    cv2.imwrite(OUTPUT_IMG, vis_img)
    results = [{"bbox": b, "text": t} for b, t in zip(boxes, texts)]
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"image": IMAGE_PATH, "results": results}, f, indent=2, ensure_ascii=False)

    log(f"Output written to {OUTPUT_JSON}, visualization -> {OUTPUT_IMG}")
    log(f"=== Pipeline Finished in {time.time() - total_start:.2f}s ===")


if __name__ == "__main__":
    main()
