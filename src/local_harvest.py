"""
Local Harvest Service - Offline Pattern-Based Extraction

Provides extraction without requiring external LLM services.
Uses regex patterns for known field types and keyword proximity for unknown fields.
"""

import re
from typing import Dict, List, Optional, Tuple


PATTERNS: Dict[str, Tuple[str, float]] = {
    "email": (r"[\w.-]+@[\w.-]+\.\w+", 0.95),
    "phone": (r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", 0.90),
    "date": (r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", 0.85),
    "currency": (r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?", 0.90),
    "ssn": (r"\d{3}[-\s]?\d{2}[-\s]?\d{4}", 0.95),
    "account": (r"\d{2}[-\s]?\d{2}[-\s]?\d{2}[-\s]?\d{5,8}", 0.85),
    "url": (r"https?://[\w./-]+", 0.95),
    "ip_address": (r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", 0.90),
    "zipcode": (r"\b\d{5}(?:-\d{4})?\b", 0.85),
    "credit_card": (r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}", 0.90),
    "amount": (r"\d{1,3}(?:,\d{3})*(?:\.\d{2})?", 0.70),
    "percentage": (r"\d+(?:\.\d+)?%", 0.85),
}


KEYWORDS: Dict[str, List[str]] = {
    "account_number": ["account", "acct", "number", "#", "acct number"],
    "amount": ["amount", "total", "sum", "due", "balance"],
    "date": ["date", "dated", "on", "effective"],
    "name": ["name", "customer", "client", "from", "sender"],
    "invoice": ["invoice", "inv", "bill", "reference"],
    "due_date": ["due", "pay by", "deadline", "expiration"],
    "address": ["address", "street", "location", "mail to"],
    "phone": ["phone", "tel", "call", "mobile", "cell"],
    "email": ["email", "e-mail", "contact at"],
    "website": ["website", "web", "site", "www"],
    "description": ["description", "regarding", "subject", "re"],
}


class LocalHarvestService:
    """Offline pattern-based extraction service."""

    def __init__(self):
        self.compiled_patterns: Dict[str, re.Pattern] = {}
        for field_type, (pattern, _) in PATTERNS.items():
            self.compiled_patterns[field_type] = re.compile(pattern, re.IGNORECASE)

    def _get_context(self, text: str, match_start: int, match_end: int) -> str:
        """Get 50 characters of context before the match."""
        context_start = max(0, match_start - 50)
        context = text[context_start:match_start]
        return context.strip(" \n\t...") if context else None

    def _extract_with_pattern(
        self, field_type: str, text: str
    ) -> List[Dict[str, Optional[str, float]]]:
        """Extract values using regex pattern."""
        if field_type not in self.compiled_patterns:
            return []

        pattern = self.compiled_patterns[field_type]
        base_confidence = PATTERNS[field_type][1]
        matches = []

        for match in pattern.finditer(text):
            match_text = match.group()
            context = self._get_context(text, match.start(), match.end())

            confidence = base_confidence
            if field_type == "amount":
                if "$" in match_text:
                    confidence += 0.05

            matches.append(
                {
                    "key": field_type,
                    "value": match_text,
                    "where": context,
                    "confidence": round(confidence, 2),
                }
            )

        return matches

    def _extract_with_keywords(
        self, field_name: str, text: str
    ) -> Optional[Dict[str, Optional[str, float]]]:
        """Extract value using keyword proximity for unknown field types."""
        field_lower = field_name.lower().replace("_", " ").replace("-", " ")
        field_words = field_lower.split()

        if not field_words:
            return None

        best_match = None
        best_confidence = 0.0

        text_lower = text.lower()

        for keyword_list in KEYWORDS.values():
            for keyword in keyword_list:
                keyword_lower = keyword.lower()
                if keyword_lower in field_lower or field_lower in keyword_lower:
                    base_confidence = 0.75

                    for i, word in enumerate(field_words):
                        if word in keyword_lower:
                            base_confidence += 0.05 * (len(field_words) - i)

                    idx = text_lower.find(keyword_lower)
                    if idx != -1:
                        after_keyword = text[idx + len(keyword_lower) :]
                        value_match = re.search(
                            r"^[\s:]*([A-Za-z0-9.,$@/-]{1,30})", after_keyword
                        )
                        if value_match:
                            value = value_match.group(1).strip()
                            context = self._get_context(
                                text, idx, idx + len(keyword_lower)
                            )

                            if len(value) >= 2:
                                confidence = min(base_confidence, 0.85)
                                if confidence > best_confidence:
                                    best_confidence = confidence
                                    best_match = {
                                        "key": field_name,
                                        "value": value,
                                        "where": context,
                                        "confidence": round(confidence, 2),
                                    }

        return best_match

    def _extract_invoice_like(
        self, field_name: str, text: str
    ) -> Optional[Dict[str, Optional[str, float]]]:
        """Try to extract invoice-like patterns (e.g., INV-12345, #12345)."""
        invoice_patterns = [
            r"(?:inv|invoice|#)[\s.-]*([A-Za-z0-9-]{3,20})",
            r"(?:ref|reference)[\s.:]*([A-Za-z0-9-]{3,20})",
        ]

        text_lower = text.lower()
        field_lower = field_name.lower()

        if any(kw in field_lower for kw in ["invoice", "reference", "number", "id"]):
            for pattern in invoice_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    value = match.group(1).upper()
                    idx = match.start()
                    context = self._get_context(text, idx, match.end())
                    return {
                        "key": field_name,
                        "value": value,
                        "where": context,
                        "confidence": 0.80,
                    }

        return None

    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate values keeping highest confidence."""
        seen: Dict[str, Dict] = {}
        for result in results:
            key = (result.get("key", ""), result.get("value", ""))
            if key not in seen or result.get("confidence", 0) > seen[key].get(
                "confidence", 0
            ):
                seen[key] = result
        return list(seen.values())

    def extract_structured(
        self,
        text: str,
        fields: List[str],
        system_prompt: str = None,
    ) -> List[Dict[str, Optional[str, float]]]:
        """
        Extract structured data using patterns and keyword proximity.

        Args:
            text: OCR-extracted document text
            fields: Requested field names (e.g., ["email", "phone", "invoice_number"])
            system_prompt: Ignored (no LLM used)

        Returns:
            List of {"key": field_name, "value": extracted_value,
                     "where": context, "confidence": score}
        """
        if not text or not text.strip():
            return []

        results: List[Dict] = []

        for field in fields:
            if not field or not field.strip():
                continue

            field = field.strip().lower()

            if field in PATTERNS:
                results.extend(self._extract_with_pattern(field, text))
            else:
                match = self._extract_with_keywords(field, text)
                if match:
                    results.append(match)
                else:
                    match = self._extract_invoice_like(field, text)
                    if match:
                        results.append(match)
                    else:
                        results.append(
                            {
                                "key": field,
                                "value": "NOT_FOUND",
                                "where": None,
                                "confidence": 0.0,
                            }
                        )

        results = self._deduplicate_results(results)

        results.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        return results
