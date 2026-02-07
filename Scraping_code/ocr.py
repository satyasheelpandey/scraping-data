# ocr.py
import os
import tempfile
import requests
import cv2
import easyocr

# Initialize OCR engine once
ocr_engine = easyocr.Reader(["en"], gpu=False)


def _download_image(url: str) -> str | None:
    """
    Downloads an image with browser-like headers to bypass hotlink protection.
    Skips SVG files because OCR cannot process vector images.
    """
    if not url:
        return None

    # ---- Skip SVG images (OCR cannot read SVG) ----
    if url.lower().endswith(".svg"):
        print("[OCR] Skipping SVG image")
        return None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        # Referer is critical for PE / VC sites (hotlink protection)
        "Referer": "https://www.adamsstreetpartners.com/",
        "Connection": "keep-alive",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()

        fd, path = tempfile.mkstemp(suffix=".png")
        with os.fdopen(fd, "wb") as f:
            f.write(resp.content)

        return path

    except Exception as e:
        print(f"[OCR] Download failed: {e}")
        return None


def _preprocess(path: str):
    """
    Image preprocessing for better OCR accuracy.
    """
    img = cv2.imread(path)
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    return gray


def run_logo_ocr(logo_image_url: str) -> tuple[str, float]:
    """
    Runs OCR on a logo image.

    Returns:
        (text, confidence)
    """
    path = _download_image(logo_image_url)
    if not path:
        return "", 0.0

    try:
        img = _preprocess(path)
        if img is None:
            return "", 0.0

        results = ocr_engine.readtext(img)
        if not results:
            return "", 0.0

        # Pick highest confidence result
        best = max(results, key=lambda r: r[2])
        text = best[1].strip()
        confidence = float(best[2])

        return text, confidence

    except Exception as e:
        print(f"[OCR ERROR] {e}")
        return "", 0.0

    finally:
        try:
            os.remove(path)
        except Exception:
            pass
