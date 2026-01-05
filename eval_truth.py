import json
import re
from pathlib import Path

def norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def find_item(items, *needles):
    """
    Returns list of values for items whose key contains any needle.
    """
    out = []
    for it in items:
        k = norm(it.get("key", ""))
        v = (it.get("value", "") or "").strip()
        if any(n in k for n in needles) and v:
            out.append(v)
    return out

def best_match(values, truth, mode="text"):
    """
    For each field, decide if any harvested value matches the truth.
    mode:
      - text: case/space normalized exact
      - digits: digit-only match
    """
    if truth is None:
        return None, None

    truth_s = str(truth)
    if mode == "digits":
        t = digits(truth_s)
        for v in values:
            if digits(v) == t and t:
                return True, v
        return False, (values[0] if values else "")
    else:
        t = norm(truth_s)
        for v in values:
            if norm(v) == t and t:
                return True, v
        return False, (values[0] if values else "")

def main(truth_path: str, harvest_path: str):
    truth = json.loads(Path(truth_path).read_text(encoding="utf-8"))
    harvest = json.loads(Path(harvest_path).read_text(encoding="utf-8"))

    items = harvest.get("items") or []

    # Your synthetic truth fields (from your generator)
    fields = truth.get("fields") or {}

    checks = [
        # (label, truth_value, harvested_values, match_mode)
        ("bank_name", fields.get("bank_name"), find_item(items, "bank", "bank name"), "text"),
        ("subject", fields.get("subject"), find_item(items, "subject"), "text"),
        ("issue_date", fields.get("issue_date"), find_item(items, "date", "issued", "issue date"), "text"),

        ("account_number", fields.get("account_number"), find_item(items, "account number"), "digits"),
        ("sort_code", fields.get("sort_code"), find_item(items, "sort code"), "digits"),

        ("owner_full_name", fields.get("owner_full_name"), find_item(items, "account owner", "owner", "name"), "text"),
        ("owner_postcode", fields.get("owner_postcode"), find_item(items, "postcode", "post code"), "text"),
    ]

    total = 0
    correct = 0

    print("\n=== Ground Truth Evaluation ===")
    print(f"Truth:   {truth_path}")
    print(f"Harvest: {harvest_path}\n")

    for label, truth_val, got_vals, mode in checks:
        ok, example = best_match(got_vals, truth_val, mode=mode)
        if ok is None:
            continue

        total += 1
        if ok:
            correct += 1
            status = "OK"
        else:
            status = "MISS"

        print(f"{status:4}  {label:16}  truth={truth_val!r}  got={example!r}")

    acc = (correct / total * 100.0) if total else 0.0
    print(f"\nScore: {correct}/{total} = {acc:.1f}%")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python eval_truth.py <truth.json> <harvest.json>")
        raise SystemExit(2)
    main(sys.argv[1], sys.argv[2])
