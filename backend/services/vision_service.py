# backend/services/vision_service.py
import cv2
import numpy as np
import base64
from pyzbar import pyzbar

class VisionEngine:
    def __init__(self):
        self.qr_detector = cv2.QRCodeDetector()
        print("✅ OpenCV Vision Engine ready")

    def preprocess_and_decode(self, base64_image: str) -> dict:
        try:
            if "," in base64_image:
                base64_image = base64_image.split(",")[1]

            img_bytes = base64.b64decode(base64_image)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return {
                    "success": False,
                    "error": "Invalid image format"
                }

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            denoised = cv2.fastNlMeansDenoise(gray, h=10)
            thresh = cv2.adaptiveThreshold(
                denoised, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )

            for candidate, method in [
                (img, "color"),
                (gray, "grayscale"),
                (thresh, "adaptive_threshold"),
            ]:
                decoded = pyzbar.decode(candidate)
                if decoded:
                    obj = decoded[0]
                    return {
                        "success": True,
                        "decoded_text": obj.data.decode(
                            "utf-8", errors="ignore"
                        ),
                        "method": f"OpenCV+PyZbar ({method})",
                        "bounding_box": {
                            "left": int(obj.rect.left),
                            "top": int(obj.rect.top),
                            "width": int(obj.rect.width),
                            "height": int(obj.rect.height),
                        },
                    }

            data, _, _ = self.qr_detector.detectAndDecode(gray)
            if data:
                return {
                    "success": True,
                    "decoded_text": data,
                    "method": "OpenCV Native QRDetector",
                    "bounding_box": None,
                }

            return {
                "success": False,
                "error": "No QR code detected in image"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"OpenCV error: {str(e)}"
            }

vision_engine = VisionEngine()
