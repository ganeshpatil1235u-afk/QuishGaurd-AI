# backend/services/vision_service.py  (REPLACES the old file)
import base64
import cv2
import numpy as np


class VisionEngine:
    def __init__(self):
        self.qr_detector = cv2.QRCodeDetector()
        print("✅ OpenCV Vision Engine ready (multi-QR + tamper check)")

    def _load(self, b64):
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        arr = np.frombuffer(base64.b64decode(b64), np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def _decode_variants(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        variants = [("color", img), ("gray", gray),
                    ("denoised", cv2.fastNlMeansDenoising(gray, h=10)),
                    ("adaptive", cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                       cv2.THRESH_BINARY, 11, 2)),
                    ("upscaled", cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))]
        for name, v in variants:
            # several QR codes in one photo?
            try:
                ok, texts, pts, _ = self.qr_detector.detectAndDecodeMulti(v)
                found = [t for t in (texts or []) if t] if ok else []
                if found:
                    return name, list(dict.fromkeys(found)), pts
            except cv2.error:
                pass
            data, pts, _ = self.qr_detector.detectAndDecode(v)
            if data:
                return name, [data], pts
        return None, [], None

    def tamper_check(self, img, pts):
        """Simple signs of a fake QR STICKER pasted over a real one."""
        signals = []
        try:
            if pts is None:
                return signals
            box = np.array(pts[0] if pts.ndim == 3 else pts).astype(int)
            x, y, w, h = cv2.boundingRect(box)
            pad = int(0.35 * max(w, h))
            x0, y0 = max(x - pad, 0), max(y - pad, 0)
            x1, y1 = min(x + w + pad, img.shape[1]), min(y + h + pad, img.shape[0])
            ring = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(ring, 80, 200)
            # a pasted sticker leaves a sharp straight paper edge just outside the code
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60,
                                    minLineLength=int(0.6 * w), maxLineGap=4)
            n_lines = 0 if lines is None else len(lines)
            if n_lines >= 6:
                signals.append({"type": "STICKER_EDGE_PATTERN",
                                "detail": "Straight edges around the QR – it may be a sticker pasted on top."})
            # a second QR-like finder pattern inside the region = QR on top of QR
            crop = img[y0:y1, x0:x1]
            ok, texts, _, _ = self.qr_detector.detectAndDecodeMulti(crop)
            if ok and len([t for t in texts if t]) > 1:
                signals.append({"type": "NESTED_QR",
                                "detail": "More than one QR code in the same spot."})
        except Exception:
            pass
        return signals

    def preprocess_and_decode(self, base64_image: str) -> dict:
        try:
            img = self._load(base64_image)
            if img is None:
                return {"success": False, "error": "Invalid image format"}
            method, texts, pts = self._decode_variants(img)
            if not texts:
                return {"success": False, "error": "No QR code detected in image"}
            signals = self.tamper_check(img, pts)
            return {"success": True, "decoded_text": texts[0], "all_decoded": texts,
                    "multiple_qr": len(texts) > 1, "method": f"OpenCV ({method})",
                    "tamper_signals": signals}
        except Exception as e:
            return {"success": False, "error": f"OpenCV error: {e}"}


vision_engine = VisionEngine()
