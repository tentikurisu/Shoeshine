import os
from typing import List, Dict

import numpy as np

from shoeshine_lib import (
    load_cfg,
    make_ocr,
    ocr_items,
    items_to_chunks,
    render_pdf_pages,
    load_image,
    ollama_embed,
    save_index,
)

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")

def ingest():
    cfg = load_cfg()
    os.makedirs(cfg.index_dir, exist_ok=True)

    ocr = make_ocr(cfg)

    vectors: List[np.ndarray] = []
    metas: List[Dict] = []

    if not os.path.isdir(cfg.raw_dir):
        print(f"Raw dir does not exist: {cfg.raw_dir}")
        return

    files = [
        os.path.join(cfg.raw_dir, f)
        for f in os.listdir(cfg.raw_dir)
        if os.path.isfile(os.path.join(cfg.raw_dir, f))
    ]

    if not files:
        print(f"No files found in {cfg.raw_dir}")
        return

    for path in files:
        fn = os.path.basename(path)
        ext = os.path.splitext(fn)[1].lower()

        print(f"\n=== Processing: {fn} ===")

        if ext == ".pdf":
            for page_no, img_bgr in render_pdf_pages(cfg, path):
                items = ocr_items(ocr, cfg, img_bgr)
                print(f"OCR({fn} p{page_no}) items={len(items)}")
                if items:
                    print("  sample:", [x["text"] for x in items[:3]])

                chunks = items_to_chunks(cfg, items)
                print(f"  chunks={len(chunks)}")

                for text in chunks:
                    v = ollama_embed(cfg, text)
                    vectors.append(v)
                    metas.append({"source_file": fn, "page": page_no, "text": text})

        elif ext in IMAGE_EXTS:
            img_bgr = load_image(path)
            items = ocr_items(ocr, cfg, img_bgr)
            print(f"OCR({fn}) items={len(items)}")
            if items:
                print("  sample:", [x["text"] for x in items[:3]])

            chunks = items_to_chunks(cfg, items)
            print(f"  chunks={len(chunks)}")

            for text in chunks:
                v = ollama_embed(cfg, text)
                vectors.append(v)
                metas.append({"source_file": fn, "page": 1, "text": text})

        else:
            print(f"Skipping unsupported: {fn}")

    save_index(cfg, vectors, metas)
    print(f"\nIndexed {len(metas)} chunks into {cfg.index_dir} (pure Python index).")

if __name__ == "__main__":
    ingest()
