from shoeshine_lib import (
    load_cfg,
    search_index,
    format_evidence,
    ollama_chat,
    harvest_document,
)

GROUND_SYSTEM = """You answer questions about banking documents.
Use ONLY the provided evidence blocks.

Rules:
- Every factual claim MUST cite one or more evidence IDs like [E1].
- If the answer is not present in the evidence, reply exactly:
  "Not found in provided evidence."
- Do not guess or infer missing values.

Return a clear answer.
"""

def answer_question(question: str) -> str:
    cfg = load_cfg()
    evidence = search_index(cfg, question)
    ev_text = format_evidence(evidence)
    user = f"Evidence:\n{ev_text}\n\nQuestion:\n{question}"
    return ollama_chat(cfg, [
        {"role": "system", "content": GROUND_SYSTEM},
        {"role": "user", "content": user}
    ])

def run_harvest_summary():
    cfg = load_cfg()
    filt = input("Doc filter (part of filename, blank=all)> ").strip()
    max_chunks_s = input("Max chunks (default 80)> ").strip()
    max_chunks = int(max_chunks_s) if max_chunks_s else 80

    paths = harvest_document(cfg, doc_filter=filt, max_chunks=max_chunks)
    print("Wrote outputs:")
    for p in paths:
        print(" -", p)

if __name__ == "__main__":
    while True:
        mode = input("\nMode (qa/summary/quit)> ").strip().lower()
        if mode in ("quit", "exit"):
            break
        if mode == "qa":
            q = input("Question> ").strip()
            print("\n", answer_question(q))
        elif mode == "summary":
            run_harvest_summary()
        else:
            print("Choose 'qa' or 'summary'.")
