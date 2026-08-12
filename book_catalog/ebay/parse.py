"""Normalize raw eBay Browse API responses into the shapes the app consumes.

parse_search_item returns None to indicate a listing that should be skipped —
currently used to exclude hardcovers and items whose format is unknown.
"""

import re
from typing import Dict, Optional, Tuple


CONDITION_ID_TEXT = {
    "1000": "New",
    "1500": "New other",
    "2000": "Certified - Refurbished",
    "2500": "Excellent - Refurbished",
    "3000": "Used",
    "4000": "Very Good",
    "5000": "Good",
    "6000": "Acceptable",
    "7000": "For parts or not working",
}

HARDCOVER_ASPECT_INDICATORS = [
    "hardcover", "hard cover", "hc", "h/c", "cloth", "hardbound", "hard bound",
]
PAPERBACK_ASPECT_INDICATORS = [
    "paperback", "pb", "mass market", "trade", "softcover", "soft cover",
]
HARDCOVER_TEXT_INDICATORS = [
    "hardcover", "hard cover", "hc", "h/c", "h.c.", "cloth", "dj",
    "dust jacket", "dustjacket", "hardbound", "hard bound",
]
PAPERBACK_TEXT_INDICATORS = [
    "paperback", "pb", "p/b", "mass market", "mm pb", "trade pb",
    "softcover", "soft cover",
]


def condition_id_to_text(condition_id) -> str:
    return CONDITION_ID_TEXT.get(str(condition_id), "Unknown")


def normalize_condition(condition: Optional[str]) -> Optional[str]:
    """Map an eBay condition string or ChatGPT grade to our Fine/VG/Good/Fair scale."""
    if not condition:
        return None
    c = condition.lower()
    if "new" in c or "mint" in c or "very fine" in c:
        return "Fine"
    if "fine" in c and "near" not in c:
        return "Fine"
    if "near fine" in c or "near-fine" in c:
        return "Near Fine"
    if "very good" in c or "excellent" in c:
        return "Very Good"
    if "good" in c:
        return "Good"
    if "fair" in c:
        return "Fair"
    if "acceptable" in c or "poor" in c:
        return "Fair"
    return None


def _extract_shipping(item: Dict) -> float:
    """Try shippingOptions → top-level shippingCost → free-shipping markers → 0.0."""
    shipping_options = item.get("shippingOptions", []) or []

    for option in shipping_options:
        cost = option.get("shippingCost") or {}
        value = cost.get("value")
        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                pass

    top = item.get("shippingCost") or {}
    value = top.get("value")
    if value is not None:
        try:
            return float(value)
        except (ValueError, TypeError):
            pass

    for option in shipping_options:
        cost = option.get("shippingCost") or {}
        cost_type = (cost.get("shippingCostType") or "").upper()
        raw = cost.get("value")
        if "FREE" in cost_type or raw == "0" or raw == 0:
            return 0.0

    return 0.0


def _format_from_aspects(item: Dict) -> Optional[str]:
    """Return the lowercased 'format'/'binding' aspect value if eBay provided one."""
    localized = item.get("localizedAspects") or []
    if isinstance(localized, list):
        for aspect in localized:
            if not isinstance(aspect, dict):
                continue
            name = (aspect.get("localizedName") or aspect.get("name") or "").lower()
            value = aspect.get("value")
            if not value:
                continue
            if any(k in name for k in ["format", "binding", "book format", "book type"]):
                return value.lower()

    aspects = item.get("aspects") or item.get("itemAspects") or {}
    if isinstance(aspects, dict):
        for key in ["Format", "format", "Binding", "binding", "Book Format", "Book Type"]:
            if key in aspects:
                v = aspects[key]
                if isinstance(v, str):
                    return v.lower()
    return None


def _detect_format(item: Dict) -> Tuple[bool, bool]:
    """Return (is_paperback, is_hardcover). Prefer eBay aspects; fall back to title/description text."""
    aspect_format = _format_from_aspects(item)
    if aspect_format:
        is_hardcover = any(i in aspect_format for i in HARDCOVER_ASPECT_INDICATORS)
        is_paperback = any(i in aspect_format for i in PAPERBACK_ASPECT_INDICATORS)
        return is_paperback, is_hardcover

    title_text = (item.get("title") or "").lower()
    desc_text = (item.get("shortDescription") or "").lower()
    combined = f"{title_text} {desc_text}"
    is_hardcover = any(i in combined for i in HARDCOVER_TEXT_INDICATORS)
    is_paperback = any(i in combined for i in PAPERBACK_TEXT_INDICATORS)
    return is_paperback, is_hardcover


def _extract_publication_year(item: Dict) -> Optional[int]:
    """Look for a Publication Year in localizedAspects then aspects; return int or None."""
    localized = item.get("localizedAspects") or []
    if isinstance(localized, list):
        for aspect in localized:
            if not isinstance(aspect, dict):
                continue
            name = (aspect.get("localizedName") or aspect.get("name") or "").lower()
            if "publication" in name and "year" in name:
                year = _coerce_year(aspect.get("value"))
                if year:
                    return year

    aspects = item.get("aspects") or item.get("itemAspects") or {}
    if isinstance(aspects, dict):
        for key in ["Publication Year", "publicationYear", "PublicationYear", "Year", "year"]:
            if key in aspects:
                year = _coerce_year(aspects[key])
                if year:
                    return year
    return None


def _coerce_year(value) -> Optional[int]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            m = re.search(r"\b(19|20)\d{2}\b", value)
            if m:
                return int(m.group())
        elif isinstance(value, (int, float)):
            return int(value)
    except (ValueError, TypeError):
        pass
    return None


def parse_search_item(item: Dict) -> Optional[Dict]:
    """Normalize one raw itemSummary into our dict shape.

    Returns None to signal the caller should skip this listing (hardcover, or
    format-unknown with no paperback indicators — we exclude both because the
    catalog is paperback-focused and hardcover contamination corrupts prices).
    """
    price_info = item.get("price") or {}
    price_value = price_info.get("value")
    if price_value is not None:
        try:
            price_value = float(price_value)
        except (ValueError, TypeError):
            price_value = None

    currency = price_info.get("currency")

    condition_id = item.get("conditionId")
    condition = item.get("condition", "Unknown")
    if condition == "Unknown" and condition_id:
        condition = condition_id_to_text(condition_id)
    condition_normalized = normalize_condition(condition)

    is_buy_it_now = "FIXED_PRICE" in (item.get("buyingOptions") or [])
    item_web_url = item.get("itemWebUrl", "")
    shipping_value = _extract_shipping(item)
    short_description = item.get("shortDescription", "")

    is_paperback, is_hardcover = _detect_format(item)
    if is_hardcover:
        return None
    if not is_paperback and not _format_from_aspects(item):
        return None

    publication_year = _extract_publication_year(item)

    format_type = "Unknown"
    if is_paperback:
        format_type = "Paperback"
    elif is_hardcover:
        format_type = "Hardcover"

    return {
        "title": item.get("title", ""),
        "price": price_value,
        "currency": currency,
        "condition": condition,
        "conditionId": condition_id,
        "condition_normalized": condition_normalized,
        "is_buy_it_now": is_buy_it_now,
        "url": item_web_url,
        "item_id": item.get("itemId", ""),
        "seller": (item.get("seller") or {}).get("username", ""),
        "shipping_cost": shipping_value,
        "description": short_description,
        "publication_year": publication_year,
        "format": format_type,
        "is_paperback": is_paperback,
        "is_hardcover": is_hardcover,
    }


def parse_item_details(data: Dict) -> Dict:
    """Normalize the /item/{id} response into our shipping/description/year dict."""
    return {
        "shipping_cost": _extract_shipping(data),
        "description": data.get("shortDescription") or data.get("description") or data.get("itemDescription"),
        "publication_year": _extract_publication_year(data),
    }
