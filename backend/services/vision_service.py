# backend/services/vision_service.py
import cv2
import numpy as np
import base64

class VisionEngine:
    def __init__(self):
        self.qr_detector = cv2.QRCodeDetector()
        print("✅ OpenCV Vision Engine ready (QR Detector)")

    def preprocess_and_decode(self, base64_image: str) -> dict:
        try:
            # Remove data URL prefix if present
            if "," in base64_image:
                base64_image = base64_image.split(",")[1]

            # Decode base64 to image
            img_bytes = base64.b64decode(base64_image)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return {
                    "success": False,
                    "error": "Invalid image format"
                }

            # Convert to grayscale for better detection
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Method 1: Direct decode on color image
            data, bbox, _ = self.qr_detector.detectAndDecode(img)
            if data:
                return {
                    "success": True,
                    "decoded_text": data,
                    "method": "OpenCV QRDetector (color)",
                    "bounding_box": self._format_bbox(bbox),
                }

            # Method 2: Try on grayscale
            data, bbox, _ = self.qr_detector.detectAndDecode(gray)
            if data:
                return {
                    "success": True,
                    "decoded_text": data,
                    "method": "OpenCV QRDetector (grayscale)",
                    "bounding_box": self._format_bbox(bbox),
                }

            # Method 3: Apply denoising
            denoised = cv2.fastNlMeansDenoising(gray, h=10)
            data, bbox, _ = self.qr_detector.detectAndDecode(denoised)
            if data:
                return {
                    "success": True,
                    "decoded_text": data,
                    "method": "OpenCV QRDetector (denoised)",
                    "bounding_box": self._format_bbox(bbox),
                }

            # Method 4: Adaptive thresholding for low quality images
            thresh = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
            data, bbox, _ = self.qr_detector.detectAndDecode(thresh)
            if data:
                return {
                    "success": True,
                    "decoded_text": data,
                    "method": "OpenCV QRDetector (adaptive threshold)",
                    "bounding_box": self._format_bbox(bbox),
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

    def _format_bbox(self, bbox):
        """Format bounding box coordinates"""
        if bbox is None or len(bbox) == 0:
            return None
        try:
            points = bbox[0]
            return {
                "top_left": [int(points[0][0]), int(points[0][1])],
                "top_right": [int(points[1][0]), int(points[1][1])],
                "bottom_right": [int(points[2][0]), int(points[2][1])],
                "bottom_left": [int(points[3][0]), int(points[3][1])],
            }
        except:
            return None

vision_engine = VisionEngine()
