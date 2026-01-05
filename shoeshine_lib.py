# ============================================================================
# OCR Service Classes
# ============================================================================

import numpy as np
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class ApiConfig:
    """API-specific configuration."""

    api_key: Optional[str]
    host: str
    port: int
    ollama_url: Optional[str]
    llm_model: Optional[str]
    aws_region: Optional[str]
    aws_access_key_id: Optional[str]
    aws_secret_access_key: Optional[str]
    bedrock_model_id: Optional[str]
    ocr_engine: str

    @classmethod
    def from_env(cls) -> "ApiConfig":
        import os

        return cls(
            api_key=os.getenv("SHOESHINE_API_KEY"),
            host=os.getenv("SHOESHINE_HOST", "0.0.0.0"),
            port=int(os.getenv("SHOESHINE_PORT", "8000")),
            ollama_url=os.getenv("SHOESHINE_OLLAMA_URL"),
            llm_model=os.getenv("SHOESHINE_LLM_MODEL", "llama3"),
            aws_region=os.getenv("AWS_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            bedrock_model_id=os.getenv(
                "BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250507"
            ),
            ocr_engine=os.getenv("SHOESHINE_OCR_ENGINE", "easyocr"),
        )


class EasyOCRService:
    """OCR service using EasyOCR."""

    def __init__(self):
        """Initialize EasyOCR service."""
        try:
            import easyocr

            # Disable verbose to avoid Unicode issues on Windows
            self.reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            self.available = True
        except Exception as e:
            print(f"EasyOCR initialization failed: {e}")
            self.reader = None
            self.available = False

    def process(self, img_bgr: np.ndarray) -> Dict[str, Any]:
        """Process image and return extracted text."""
        if not self.available:
            return {
                "success": False,
                "error": "OCR not available",
                "text": "",
                "items": [],
            }

        try:
            result = self.reader.readtext(img_bgr)

            items = []
            for detection in result:
                bbox, text, confidence = detection
                if text and text.strip():
                    if isinstance(bbox, list) and len(bbox) == 4:
                        xs = [p[0] for p in bbox]
                        ys = [p[1] for p in bbox]
                        bbox_list = [
                            int(min(xs)),
                            int(min(ys)),
                            int(max(xs)),
                            int(max(ys)),
                        ]
                    else:
                        bbox_list = [0, 0, 0, 0]

                    items.append(
                        {
                            "text": text.strip(),
                            "confidence": float(confidence),
                            "bbox": bbox_list,
                        }
                    )

            items.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
            text = " ".join(item["text"] for item in items)

            return {"success": True, "text": text, "items": items}

        except Exception as e:
            return {"success": False, "error": str(e), "text": "", "items": []}


class TesseractOCRService:
    """OCR service using Tesseract."""

    def __init__(self):
        """Initialize Tesseract service."""
        try:
            import pytesseract
            from pytesseract import Output

            self.pytesseract = pytesseract
            self.Output = Output
            self.available = True
        except Exception as e:
            print(f"Tesseract initialization failed: {e}")
            self.pytesseract = None
            self.available = False

    def process(self, img_bgr: np.ndarray) -> Dict[str, Any]:
        """Process image and return extracted text."""
        if not self.available:
            return {
                "success": False,
                "error": "Tesseract not available",
                "text": "",
                "items": [],
            }

        try:
            # Get data with bbox info
            data = self.pytesseract.image_to_data(img_bgr, output_type=self.Output.DICT)

            items = []
            for i, text in enumerate(data["text"]):
                if text and text.strip():
                    conf = int(data["conf"][i]) if data["conf"][i] > -1 else 0
                    x, y, w, h = (
                        data["left"][i],
                        data["top"][i],
                        data["width"][i],
                        data["height"][i],
                    )

                    items.append(
                        {
                            "text": text.strip(),
                            "confidence": conf / 100.0,
                            "bbox": [x, y, x + w, y + h],
                        }
                    )

            items.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
            text = " ".join(item["text"] for item in items)

            return {"success": True, "text": text, "items": items}

        except Exception as e:
            return {"success": False, "error": str(e), "text": "", "items": []}


class OCRService:
    """Unified OCR service that tries multiple backends."""

    def __init__(self, engine: str = "easyocr"):
        """Initialize OCR service with specified engine."""
        self.engine = engine
        self.primary = None
        self.fallback = None
        self.available = False

        # Try to initialize primary engine
        if engine == "easyocr":
            self.primary = EasyOCRService()
            self.fallback = TesseractOCRService()
        else:
            self.primary = TesseractOCRService()
            self.fallback = EasyOCRService()

        self.available = self.primary.available or self.fallback.available

    def process(self, img_bgr: np.ndarray) -> Dict[str, Any]:
        """Process image using primary or fallback engine."""
        if self.primary and self.primary.available:
            result = self.primary.process(img_bgr)
            if result["success"]:
                return result

        if self.fallback and self.fallback.available:
            result = self.fallback.process(img_bgr)
            if result["success"]:
                return result

        return {
            "success": False,
            "error": "No OCR engine available",
            "text": "",
            "items": [],
        }


def decode_upload_file(content: bytes) -> np.ndarray:
    """Decode uploaded file content to OpenCV image."""
    import cv2
    from PIL import Image
    import io

    img_array = np.frombuffer(content, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if img is None:
        pil_img = Image.open(io.BytesIO(content))
        pil_img = pil_img.convert("RGB")
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    return img


class OllamaService:
    """Service for Ollama integration."""

    def __init__(self, base_url: str):
        """Initialize Ollama service."""
        import requests

        self.base_url = base_url

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        import requests

        try:
            response = requests.get(f"{self.base_url}/api/version", timeout=2)
            return response.status_code == 200
        except:
            return False

    def extract_structured(
        self, text: str, fields: List[str], system_prompt: str = None
    ) -> List[Dict]:
        """Extract structured data from text using Ollama."""
        import requests
        import json

        if not self.is_available():
            return []

        config = ApiConfig.from_env()
        model = config.llm_model or "llama3"

        default_system = """You are extracting structured data from a document.
Extract requested fields as JSON array of objects.
Output format: [{"key": "field_name", "value": "extracted value", "where": "location"}]

If a field is not found, include it with value "NOT_FOUND"."""

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt or default_system},
                        {
                            "role": "user",
                            "content": f"Extract these fields: {', '.join(fields)}\n\nDocument:\n{text}",
                        },
                    ],
                    "stream": False,
                },
                timeout=120,
            )

            if response.status_code != 200:
                return []

            result = response.json()
            content = result.get("message", {}).get("content", "")

            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "items" in data:
                    return data["items"]
            except:
                pass

        except Exception as e:
            print(f"Ollama extraction failed: {e}")

        return []


class BedrockService:
    """Service for AWS Bedrock integration."""

    def __init__(self):
        """Initialize Bedrock service."""
        self.config = ApiConfig.from_env()
        self.client = None
        if self.config.aws_region and self.config.aws_access_key_id:
            import boto3

            self.client = boto3.client(
                "bedrock-runtime",
                region_name=self.config.aws_region,
                aws_access_key_id=self.config.aws_access_key_id,
                aws_secret_access_key=self.config.aws_secret_access_key,
            )

    def is_available(self) -> bool:
        """Check if Bedrock is available."""
        return self.client is not None

    def extract_structured(
        self, text: str, fields: List[str], system_prompt: str = None
    ) -> List[Dict]:
        """Extract structured data from text using Bedrock."""
        import json

        if not self.is_available():
            return []

        model_id = self.config.bedrock_model_id or "anthropic.claude-sonnet-4-20250507"

        default_system = """You are extracting structured data from a document.
Extract requested fields as JSON array of objects.
Output format: [{"key": "field_name", "value": "extracted value", "where": "location"}]

If a field is not found, include it with value "NOT_FOUND"."""

        try:
            response = self.client.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": f"Extract these fields: {', '.join(fields)}\n\nDocument:\n{text}"
                            }
                        ],
                    }
                ],
                system=[{"text": system_prompt or default_system}],
                inferenceConfig={"maxTokens": 4096, "temperature": 0.0},
            )

            content = response["output"]["message"]["content"][0]["text"]

            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "items" in data:
                    return data["items"]
            except:
                pass
        except Exception as e:
            print(f"Bedrock extraction failed: {e}")

        return []


try:
    from paddleocr import PaddleOCR

    PADDLEOCR_AVAILABLE = True
except ImportError:
    PaddleOCR = None
    PADDLEOCR_AVAILABLE = False


# -------------------------
# Config loading
# -------------------------
@dataclass
class Cfg:
    raw_dir: str
    out_dir: str
    index_dir: str
    ocr_lang: str
    ocr_min_conf: float
    pdf_zoom: float
    chunk_max_chars: int
    chunk_min_chars: int
    top_k: int
    ollama_url: str
    embed_model: str
    llm_model: str
    keep_alive: str
    output_format: str


def load_cfg(path="config.yaml") -> Cfg:
    with open(path, "r", encoding="utf-8") as f:
        y = yaml.safe_load(f)
    return Cfg(
        raw_dir=y["paths"]["raw_dir"],
        out_dir=y["paths"]["out_dir"],
        index_dir=y["paths"]["index_dir"],
        ocr_lang=y["ocr"]["lang"],
        ocr_min_conf=float(y["ocr"]["min_conf"]),
        pdf_zoom=float(y["pdf"]["zoom"]),
        chunk_max_chars=int(y["chunking"]["max_chars"]),
        chunk_min_chars=int(y["chunking"]["min_chars"]),
        top_k=int(y["retrieval"]["top_k"]),
        ollama_url=y["ollama"]["base_url"],
        embed_model=y["ollama"]["embed_model"],
        llm_model=y["ollama"]["llm_model"],
        keep_alive=y["ollama"]["keep_alive"],
        output_format=y["extraction"]["output_format"],
    )


# -------------------------
# Ollama helpers
# -------------------------
def ollama_embed(cfg: Cfg, text: str) -> np.ndarray:
    r = requests.post(
        f"{cfg.ollama_url}/api/embeddings",
        json={"model": cfg.embed_model, "prompt": text},
        timeout=120,
    )
    r.raise_for_status()
    v = np.array(r.json()["embedding"], dtype=np.float32)
    n = np.linalg.norm(v) + 1e-12
    return v / n


def ollama_chat(cfg: Cfg, messages: List[Dict[str, str]]) -> str:
    r = requests.post(
        f"{cfg.ollama_url}/api/chat",
        json={
            "model": cfg.llm_model,
            "messages": messages,
            "stream": False,
            "keep_alive": cfg.keep_alive,
        },
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


# -------------------------
# Image preprocessing (less destructive)
# -------------------------
def preprocess_for_ocr(img_bgr: np.ndarray) -> np.ndarray:
    """
    IMPORTANT: Your synthetic docs have heavy speckle noise.
    This preproc focuses on *de-speckling* and contrast, without destroying text.
    """
    if img_bgr is None:
        return img_bgr

    if img_bgr.dtype != np.uint8:
        img_bgr = img_bgr.astype(np.uint8)

    # Ensure 3-channel
    if len(img_bgr.shape) == 2:
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_GRAY2BGR)
    elif img_bgr.shape[2] == 4:
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2BGR)

    h, w = img_bgr.shape[:2]
    if max(h, w) < 1400:
        s = 1400 / max(h, w)
        img_bgr = cv2.resize(img_bgr, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # median blur helps speckle noise a lot
    gray = cv2.medianBlur(gray, 3)

    # CLAHE to improve faint text
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # mild binarisation (otsu)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # morphological opening to remove tiny dots
    kernel = np.ones((2, 2), np.uint8)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=1)

    # convert back to 3-channel (some OCR pipelines expect it)
    return cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)


# -------------------------
# PDF/image loading
# -------------------------
def render_pdf_pages(cfg: Cfg, pdf_path: str):
    doc = fitz.open(pdf_path)
    for i in range(len(doc)):
        page = doc[i]
        mat = fitz.Matrix(cfg.pdf_zoom, cfg.pdf_zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, 3
        )
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        yield (i + 1, img_bgr)


def load_image(path: str) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Failed to read image: {path}")
    return img


# -------------------------
# OCR + chunking
# -------------------------
def make_ocr(cfg: Cfg) -> PaddleOCR:
    return PaddleOCR(lang=cfg.ocr_lang)


def _call_ocr(ocr: PaddleOCR, img: np.ndarray):
    """
    Call OCR in a way that works across PaddleOCR output/call variations.
    """
    # Try direct
    try:
        return ocr.ocr(img)
    except TypeError:
        pass
    except Exception:
        pass

    # Try list-wrapped
    try:
        return ocr.ocr([img])
    except Exception:
        return None


def _parse_ocr_result(res) -> List[Tuple[List, object]]:
    """
    Normalise PaddleOCR results into a list of (quad, payload).
    Supports both PaddleOCR 2.x and 3.x formats.
    """
    if res is None:
        return []

    # PaddleOCR 3.x format: list of dicts with 'rec_texts', 'rec_scores', 'dt_polys', etc.
    if isinstance(res, list) and len(res) > 0:
        # Check if 3.x format (dict with keys like rec_texts)
        if isinstance(res[0], dict) and "rec_texts" in res[0]:
            page = res[0]
            texts = page.get("rec_texts", [])
            scores = page.get("rec_scores", [])
            polys = page.get("dt_polys", []) or page.get("rec_polys", [])

            out = []
            for i, txt in enumerate(texts):
                if not txt:
                    continue
                score = scores[i] if i < len(scores) else 1.0
                poly = polys[i] if i < len(polys) else None
                if poly is not None:
                    out.append((poly, [txt, score]))
            return out

        # PaddleOCR 2.x format: [ [ [quad, (text, conf)], ... ] ]
        if len(res) == 1 and isinstance(res[0], list):
            page = res[0]
            if (
                len(page) > 0
                and isinstance(page[0], (list, tuple))
                and len(page[0]) >= 2
            ):
                return [
                    (ln[0], ln[1])
                    for ln in page
                    if isinstance(ln, (list, tuple)) and len(ln) >= 2
                ]
        # sometimes already lines
        if len(res) > 0 and isinstance(res[0], (list, tuple)) and len(res[0]) >= 2:
            return [
                (ln[0], ln[1])
                for ln in res
                if isinstance(ln, (list, tuple)) and len(ln) >= 2
            ]

    return []

    # Common: [ [ [quad, (text, conf)], ... ] ]
    if isinstance(res, list):
        if len(res) == 0:
            return []
        if len(res) == 1 and isinstance(res[0], list):
            # sometimes res[0] is page lines, sometimes res[0] is list of pages
            page = res[0]
            # if it's already [quad,payload] lines:
            if (
                len(page) > 0
                and isinstance(page[0], (list, tuple))
                and len(page[0]) >= 2
            ):
                return [
                    (ln[0], ln[1])
                    for ln in page
                    if isinstance(ln, (list, tuple)) and len(ln) >= 2
                ]
        # sometimes already lines
        if len(res) > 0 and isinstance(res[0], (list, tuple)) and len(res[0]) >= 2:
            return [
                (ln[0], ln[1])
                for ln in res
                if isinstance(ln, (list, tuple)) and len(ln) >= 2
            ]

    return []


def ocr_items(ocr: PaddleOCR, cfg: Cfg, img_bgr: np.ndarray) -> List[Dict]:
    """
    Fallback strategy:
    1) original RGB
    2) original BGR
    3) preprocessed RGB
    4) preprocessed BGR
    """
    if img_bgr is None:
        return []

    # ensure 3-channel
    if len(img_bgr.shape) == 2:
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_GRAY2BGR)
    elif img_bgr.shape[2] == 4:
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2BGR)

    img_pre = preprocess_for_ocr(img_bgr)

    tries = [
        ("orig_rgb", cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)),
        ("orig_bgr", img_bgr),
        ("prep_rgb", cv2.cvtColor(img_pre, cv2.COLOR_BGR2RGB)),
        ("prep_bgr", img_pre),
    ]

    best_out: List[Dict] = []
    best_count = 0

    for name, img in tries:
        res = _call_ocr(ocr, img)
        lines = _parse_ocr_result(res)

        out = []
        for quad, payload in lines:
            # payload should be (text, conf) but may vary
            txt = None
            conf = 1.0

            if isinstance(payload, (list, tuple)) and len(payload) >= 2:
                txt = payload[0]
                conf = payload[1]
            else:
                txt = payload

            if not txt:
                continue

            try:
                conf = float(conf)
            except Exception:
                conf = 1.0

            if conf < cfg.ocr_min_conf:
                continue

            # quad should be 4 points
            try:
                xs = [int(p[0]) for p in quad]
                ys = [int(p[1]) for p in quad]
                bbox = (min(xs), min(ys), max(xs), max(ys))
            except Exception:
                bbox = (0, 0, 0, 0)

            out.append({"text": str(txt).strip(), "conf": conf, "bbox": bbox})

        if len(out) > best_count:
            best_out = out
            best_count = len(out)

    return best_out


def items_to_chunks(cfg: Cfg, items: List[Dict]) -> List[str]:
    if not items:
        return []

    items = sorted(items, key=lambda d: (d["bbox"][1], d["bbox"][0]))

    # group into lines
    lines = []
    for it in items:
        placed = False
        x1, y1, x2, y2 = it["bbox"]
        for ln in reversed(lines[-12:]):
            ly1 = ln[0]["bbox"][1]
            ly2 = ln[0]["bbox"][3]
            if abs(y1 - ly1) < 12 or abs(y2 - ly2) < 12 or (y1 <= ly2 and y2 >= ly1):
                ln.append(it)
                placed = True
                break
        if not placed:
            lines.append([it])

    norm_lines = []
    for ln in lines:
        ln = sorted(ln, key=lambda d: d["bbox"][0])
        text = " ".join(d["text"] for d in ln).strip()
        if text:
            norm_lines.append(text)

    # blocks: every ~10 lines
    blocks = []
    cur = []
    for line in norm_lines:
        cur.append(line)
        if len(cur) >= 10:
            blocks.append("\n".join(cur))
            cur = []
    if cur:
        blocks.append("\n".join(cur))

    # split blocks to size
    chunks = []
    for b in blocks:
        t = " ".join(b.split()).strip()
        if len(t) < cfg.chunk_min_chars:
            continue
        if len(t) <= cfg.chunk_max_chars:
            chunks.append(t)
            continue

        start = 0
        while start < len(t):
            end = min(len(t), start + cfg.chunk_max_chars)
            cut = max(t.rfind(". ", start, end), t.rfind("; ", start, end))
            if cut <= start + int(cfg.chunk_max_chars * 0.5):
                cut = end
            part = t[start:cut].strip()
            if len(part) >= cfg.chunk_min_chars:
                chunks.append(part)
            start = cut

    return chunks


# -------------------------
# Pure-python vector index
# -------------------------
def index_paths(cfg: Cfg):
    os.makedirs(cfg.index_dir, exist_ok=True)
    return (
        os.path.join(cfg.index_dir, "vectors.npy"),
        os.path.join(cfg.index_dir, "meta.jsonl"),
    )


def save_index(cfg: Cfg, vectors: List[np.ndarray], metas: List[Dict]):
    vec_path, meta_path = index_paths(cfg)
    V = (
        np.stack(vectors, axis=0).astype(np.float32)
        if vectors
        else np.zeros((0, 768), dtype=np.float32)
    )
    np.save(vec_path, V)
    with open(meta_path, "w", encoding="utf-8") as f:
        for m in metas:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")


def load_index(cfg: Cfg):
    vec_path, meta_path = index_paths(cfg)
    V = np.load(vec_path).astype(np.float32)
    metas = []
    with open(meta_path, "r", encoding="utf-8") as f:
        for line in f:
            metas.append(json.loads(line))
    return V, metas


def search_index(cfg: Cfg, question: str, top_k: Optional[int] = None):
    V, metas = load_index(cfg)
    if V.shape[0] == 0:
        return []

    qv = ollama_embed(cfg, question)
    sims = V @ qv
    k = top_k or cfg.top_k
    idx = np.argpartition(-sims, kth=min(k, len(sims) - 1))[:k]
    idx = idx[np.argsort(-sims[idx])]

    evidence = []
    for rank, i in enumerate(idx, start=1):
        m = metas[int(i)]
        evidence.append(
            {
                "eid": f"E{rank}",
                "score": float(sims[int(i)]),
                "source_file": m["source_file"],
                "page": m["page"],
                "text": m["text"],
            }
        )
    return evidence


def format_evidence(evidence: List[Dict]) -> str:
    parts = []
    for e in evidence:
        parts.append(f"[{e['eid']}] {e['source_file']} p.{e['page']}\n{e['text']}")
    return "\n\n---\n\n".join(parts)


def safe_json_parse(s: str) -> Dict:
    try:
        return json.loads(s)
    except Exception:
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(s[start : end + 1])
        raise


# -------------------------
# Banking info extraction (Option B: Chunk Harvester)
# -------------------------
HARVEST_SYSTEM = """You are harvesting banking-relevant information from a document excerpt.

Instructions:
- Extract any banking-relevant information you can clearly see in the excerpt.
- Do NOT guess. If unsure, omit it.
- Do NOT force a fixed schema. Choose what you think is relevant.
- Output JSON ONLY in this format:

{"items":[{"key":"…","value":"…","where":"…optional…","note":"…optional…"}]}

Rules:
- Keep keys short (e.g., "Account number", "Sort code", "Transaction", "Statement period", "Balance", "Bank name", "Address").
- Values should be copied exactly as shown where possible.
"""

HARVEST_MERGE_SYSTEM = """You merge multiple partial harvest JSON objects into one.

Input: {"partials":[ ... ]}

Rules:
- Combine all items into one list.
- Deduplicate near-identical items (same key and value).
- If conflicts exist, keep both and add a note like "conflict" if needed.
- Output JSON ONLY: {"items":[...]}
"""

HARVEST_SUMMARY_SYSTEM = """You write a document summary based ONLY on the harvested items JSON.

Output:
1) DOCUMENT SUMMARY (plain text, 8-15 bullets)
2) BANKING INFO (key/value report style)

Do not invent details.
"""


def harvest_chunk(cfg: Cfg, chunk_text: str, where: str = "") -> Dict:
    payload = chunk_text if not where else f"Where: {where}\n\nExcerpt:\n{chunk_text}"
    content = ollama_chat(
        cfg,
        [
            {"role": "system", "content": HARVEST_SYSTEM},
            {"role": "user", "content": payload},
        ],
    )
    return safe_json_parse(content)


def merge_harvest(cfg: Cfg, partials: List[Dict]) -> Dict:
    content = ollama_chat(
        cfg,
        [
            {"role": "system", "content": HARVEST_MERGE_SYSTEM},
            {
                "role": "user",
                "content": json.dumps({"partials": partials}, ensure_ascii=False),
            },
        ],
    )
    return safe_json_parse(content)


def harvest_summary(cfg: Cfg, merged: Dict) -> str:
    return ollama_chat(
        cfg,
        [
            {"role": "system", "content": HARVEST_SUMMARY_SYSTEM},
            {"role": "user", "content": json.dumps(merged, ensure_ascii=False)},
        ],
    )


def write_harvest_outputs(cfg: Cfg, doc_label: str, merged: Dict, summary_text: str):
    os.makedirs(cfg.out_dir, exist_ok=True)

    json_path = os.path.join(cfg.out_dir, f"{doc_label}.harvest.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    txt_path = os.path.join(cfg.out_dir, f"{doc_label}.harvest.summary.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(summary_text.strip() + "\n")

    csv_path = os.path.join(cfg.out_dir, f"{doc_label}.harvest.keyvalues.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("key,value,where,note\n")
        for it in merged.get("items") or []:
            k = str(it.get("key", "")).replace('"', '""')
            v = str(it.get("value", "")).replace('"', '""')
            w = str(it.get("where", "")).replace('"', '""')
            n = str(it.get("note", "")).replace('"', '""')
            if k and v:
                f.write(f'"{k}","{v}","{w}","{n}"\n')

    return json_path, txt_path, csv_path


def harvest_document(cfg: Cfg, doc_filter: str = "", max_chunks: int = 80):
    meta_path = os.path.join(cfg.index_dir, "meta.jsonl")
    if not os.path.exists(meta_path):
        raise RuntimeError("Index not found. Run python ingest.py first.")

    metas = []
    with open(meta_path, "r", encoding="utf-8") as f:
        for line in f:
            m = json.loads(line)
            if doc_filter and doc_filter.lower() not in m["source_file"].lower():
                continue
            metas.append(m)

    if not metas:
        raise RuntimeError("No chunks matched doc_filter. Check your filename filter.")

    metas = metas[:max_chunks]

    partials: List[Dict] = []
    for m in metas:
        where = f"{m['source_file']} p.{m['page']}"
        partials.append(harvest_chunk(cfg, m["text"], where=where))

    merged = merge_harvest(cfg, partials)
    summary_text = harvest_summary(cfg, merged)

    label = (doc_filter.strip().replace(" ", "_") or "bankdoc")[:60]
    return write_harvest_outputs(cfg, label, merged, summary_text)


# ============================================================================
# OCR Service Classes (Moved from api_server.py for code reuse)
# ============================================================================

import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class OCRConfig:
    """OCR-specific configuration."""

    api_key: Optional[str]
    host: str
    port: int
    ollama_url: Optional[str]
    llm_model: Optional[str]
    aws_region: Optional[str]
    aws_access_key_id: Optional[str]
    aws_secret_access_key: Optional[str]
    bedrock_model_id: Optional[str]
    ocr_engine: str

    @classmethod
    def from_env(cls) -> "OCRConfig":
        return cls(
            api_key=os.getenv("SHOESHINE_API_KEY"),
            host=os.getenv("SHOESHINE_HOST", "0.0.0.0"),
            port=int(os.getenv("SHOESHINE_PORT", "8000")),
            ollama_url=os.getenv("SHOESHINE_OLLAMA_URL"),
            llm_model=os.getenv("SHOESHINE_LLM_MODEL", "llama3"),
            aws_region=os.getenv("AWS_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            bedrock_model_id=os.getenv(
                "BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250507"
            ),
            ocr_engine=os.getenv("SHOESHINE_OCR_ENGINE", "easyocr"),
        )


class EasyOCRService:
    """OCR service using EasyOCR."""

    def __init__(self):
        """Initialize EasyOCR service."""
        try:
            import easyocr

            # Disable verbose to avoid Unicode issues on Windows
            self.reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            self.available = True
        except Exception as e:
            print(f"EasyOCR initialization failed: {e}")
            self.reader = None
            self.available = False

    def process(self, img_bgr: np.ndarray) -> Dict[str, Any]:
        """Process image and return extracted text."""
        if not self.available:
            return {
                "success": False,
                "error": "OCR not available",
                "text": "",
                "items": [],
            }

        try:
            result = self.reader.readtext(img_bgr)

            items = []
            for detection in result:
                bbox, text, confidence = detection
                if text and text.strip():
                    if isinstance(bbox, list) and len(bbox) == 4:
                        xs = [p[0] for p in bbox]
                        ys = [p[1] for p in bbox]
                        bbox_list = [
                            int(min(xs)),
                            int(min(ys)),
                            int(max(xs)),
                            int(max(ys)),
                        ]
                    else:
                        bbox_list = [0, 0, 0, 0]

                    items.append(
                        {
                            "text": text.strip(),
                            "confidence": float(confidence),
                            "bbox": bbox_list,
                        }
                    )

            items.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
            text = " ".join(item["text"] for item in items)

            return {"success": True, "text": text, "items": items}

        except Exception as e:
            return {"success": False, "error": str(e), "text": "", "items": []}


class TesseractOCRService:
    """OCR service using Tesseract."""

    def __init__(self):
        """Initialize Tesseract service."""
        try:
            import pytesseract
            from pytesseract import Output

            self.pytesseract = pytesseract
            self.Output = Output
            self.available = True
        except Exception as e:
            print(f"Tesseract initialization failed: {e}")
            self.pytesseract = None
            self.available = False

    def process(self, img_bgr: np.ndarray) -> Dict[str, Any]:
        """Process image and return extracted text."""
        if not self.available:
            return {
                "success": False,
                "error": "Tesseract not available",
                "text": "",
                "items": [],
            }

        try:
            data = self.pytesseract.image_to_data(img_bgr, output_type=self.Output.DICT)

            items = []
            for i, text in enumerate(data["text"]):
                if text and text.strip():
                    conf = int(data["conf"][i]) if data["conf"][i] > -1 else 0
                    x, y, w, h = (
                        data["left"][i],
                        data["top"][i],
                        data["width"][i],
                        data["height"][i],
                    )

                    items.append(
                        {
                            "text": text.strip(),
                            "confidence": conf / 100.0,
                            "bbox": [x, y, x + w, y + h],
                        }
                    )

            items.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
            text = " ".join(item["text"] for item in items)

            return {"success": True, "text": text, "items": items}

        except Exception as e:
            return {"success": False, "error": str(e), "text": "", "items": []}


class OCRService:
    """Unified OCR service that tries multiple backends."""

    def __init__(self, engine: str = "easyocr"):
        """Initialize OCR service with specified engine."""
        self.engine = engine
        self.primary = None
        self.fallback = None
        self.available = False

        if engine == "easyocr":
            self.primary = EasyOCRService()
            self.fallback = TesseractOCRService()
        else:
            self.primary = TesseractOCRService()
            self.fallback = EasyOCRService()

        self.available = self.primary.available or self.fallback.available

    def process(self, img_bgr: np.ndarray) -> Dict[str, Any]:
        """Process image using primary or fallback engine."""
        if self.primary and self.primary.available:
            result = self.primary.process(img_bgr)
            if result["success"]:
                return result

        if self.fallback and self.fallback.available:
            result = self.fallback.process(img_bgr)
            if result["success"]:
                return result

        return {
            "success": False,
            "error": "No OCR engine available",
            "text": "",
            "items": [],
        }


def decode_upload_file(content: bytes) -> np.ndarray:
    """Decode uploaded file content to OpenCV image."""
    img_array = np.frombuffer(content, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if img is None:
        from PIL import Image
        import io

        pil_img = Image.open(io.BytesIO(content))
        pil_img = pil_img.convert("RGB")
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    return img


class OllamaService:
    """Service for Ollama integration."""

    def __init__(self, base_url: str):
        """Initialize Ollama service."""
        self.base_url = base_url

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            response = requests.get(f"{self.base_url}/api/version", timeout=2)
            return response.status_code == 200
        except:
            return False

    def extract_structured(
        self, text: str, fields: List[str], system_prompt: str = None
    ) -> List[Dict]:
        """Extract structured data from text using Ollama."""
        if not self.is_available():
            return []

        config = OCRConfig.from_env()
        model = config.llm_model or "llama3"

        default_system = """You are extracting structured data from a document.
Extract requested fields as JSON array of objects.
Output format: [{"key": "field_name", "value": "extracted value", "where": "location"}]

If a field is not found, include it with value "NOT_FOUND"."""

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt or default_system},
                        {
                            "role": "user",
                            "content": f"Extract these fields: {', '.join(fields)}\n\nDocument:\n{text}",
                        },
                    ],
                    "stream": False,
                },
                timeout=120,
            )

            if response.status_code != 200:
                return []

            result = response.json()
            content = result.get("message", {}).get("content", "")

            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "items" in data:
                    return data["items"]
            except:
                pass

        except Exception as e:
            print(f"Ollama extraction failed: {e}")

        return []


class BedrockService:
    """Service for AWS Bedrock integration."""

    def __init__(self):
        """Initialize Bedrock service."""
        self.config = OCRConfig.from_env()
        self.client = None
        if self.config.aws_region and self.config.aws_access_key_id:
            import boto3

            self.client = boto3.client(
                "bedrock-runtime",
                region_name=self.config.aws_region,
                aws_access_key_id=self.config.aws_access_key_id,
                aws_secret_access_key=self.config.aws_secret_access_key,
            )

    def is_available(self) -> bool:
        """Check if Bedrock is available."""
        return self.client is not None

    def extract_structured(
        self, text: str, fields: List[str], system_prompt: str = None
    ) -> List[Dict]:
        """Extract structured data from text using Bedrock."""
        if not self.is_available():
            return []

        model_id = self.config.bedrock_model_id or "anthropic.claude-sonnet-4-20250507"

        default_system = """You are extracting structured data from a document.
Extract requested fields as JSON array of objects.
Output format: [{"key": "field_name", "value": "extracted value", "where": "location"}]

If a field is not found, include it with value "NOT_FOUND"."""

        try:
            response = self.client.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": f"Extract these fields: {', '.join(fields)}\n\nDocument:\n{text}",
                            }
                        ],
                    }
                ],
                system=[{"text": system_prompt or default_system}],
                inferenceConfig={"maxTokens": 4096, "temperature": 0.0},
            )

            content = response["output"]["message"]["content"][0]["text"]

            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "items" in data:
                    return data["items"]
            except:
                pass
        except Exception as e:
            print(f"Bedrock extraction failed: {e}")

        return []


def verify_api_key(x_api_key: Optional[str]) -> bool:
    """Verify API key if configured."""
    config = OCRConfig.from_env()
    if config.api_key is None:
        return True
    if x_api_key is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if x_api_key != config.api_key:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Invalid API key")
    return True


class UsageInfo:
    """Token usage information (OpenAI-compatible format)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_text(cls, text: str) -> "UsageInfo":
        token_count = len(text) // 4
        return cls(prompt_tokens=token_count, total_tokens=token_count)


class BBoxItem:
    """Bounding box item with text."""

    text: str
    confidence: float
    bbox: List[int]
