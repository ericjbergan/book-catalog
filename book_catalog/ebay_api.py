"""Facade over the ebay/ subpackage.

Preserves the historical `eBayAPI` surface so callers (app.py, CLI scripts) do
not need import changes. Real logic lives in ebay/client.py (HTTP + OAuth),
ebay/parse.py (response normalization), ebay/match.py (edition matching +
ChatGPT filter), and ebay/pricing.py (weighted-median estimate).
"""

from typing import Dict, List, Optional, Tuple

from .ebay import match, parse, pricing
from .ebay.client import EbayClient

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class eBayAPI:
    """Historical eBay client + pricing facade. Delegates to the ebay/ modules."""

    def __init__(self, app_id: str, cert_id: str, dev_id: str,
                 sandbox: bool = True, openai_api_key: Optional[str] = None):
        self._client = EbayClient(app_id, cert_id, dev_id, sandbox)

        self.openai_client = None
        if openai_api_key and OPENAI_AVAILABLE:
            try:
                self.openai_client = OpenAI(api_key=openai_api_key)
            except Exception as e:
                print(f"Warning: Could not initialize OpenAI client: {e}")
        elif openai_api_key and not OPENAI_AVAILABLE:
            print("Warning: OpenAI library not installed. Install with: pip install openai")

    # --- attributes used by legacy tests/callers -----------------------------

    @property
    def sandbox(self) -> bool:
        return self._client.sandbox

    # --- search / item details ----------------------------------------------

    def search_books(self, title: str, author: Optional[str] = None,
                     publisher: Optional[str] = None,
                     stock_number: Optional[str] = None,
                     limit: int = 20) -> List[Dict]:
        """Search eBay for a book. Returns normalized dicts, paperbacks first then by price."""
        query_parts = [title]
        if author:
            query_parts.append(author)
        if publisher:
            query_parts.append(publisher)
        if stock_number:
            query_parts.append(stock_number)
        query = " ".join(query_parts)

        raw_items = self._client.search_raw(query, limit=limit)

        results = []
        for raw in raw_items:
            parsed = parse.parse_search_item(raw)
            if parsed is not None:
                results.append(parsed)

        results.sort(key=lambda x: (
            0 if x.get("is_paperback") else (1 if not x.get("is_hardcover") else 2),
            x.get("price") or float("inf"),
        ))
        return results

    def get_item_details(self, item_id: str) -> Dict:
        """Fetch full item details; returns dict with shipping_cost/description/publication_year."""
        raw = self._client.get_item_raw(item_id)
        if raw is None:
            return {"shipping_cost": 0.0, "description": None, "publication_year": None}
        return parse.parse_item_details(raw)

    def get_item_description(self, item_id: str) -> Tuple[Optional[str], Optional[int]]:
        details = self.get_item_details(item_id)
        return details.get("description"), details.get("publication_year")

    # --- matching / grading helpers (kept public for backwards compat) -------

    def prioritize_results(self, results: List[Dict],
                           target_author: Optional[str] = None,
                           target_stock_number: Optional[str] = None) -> List[Dict]:
        return match.prioritize_results(results, target_author, target_stock_number)

    def _matches_edition(self, listing_title: str,
                         publisher: Optional[str] = None,
                         stock_number: Optional[str] = None) -> bool:
        return match.matches_edition(listing_title, publisher, stock_number)

    def _grade_match_score(self, listing_grade: Optional[str],
                           target_grade: Optional[str]) -> float:
        return match.grade_match_score(listing_grade, target_grade)

    def _fuzzy_similarity(self, str1: str, str2: str) -> float:
        return match.fuzzy_similarity(str1, str2)

    def _fuzzy_match_stock_number(self, listing_title: str, target_stock: str,
                                  threshold: float = 0.8) -> bool:
        return match.fuzzy_match_stock_number(listing_title, target_stock, threshold)

    def _fuzzy_match_publisher(self, listing_title: str, target_publisher: str,
                               threshold: float = 0.75) -> bool:
        return match.fuzzy_match_publisher(listing_title, target_publisher, threshold)

    def _condition_id_to_text(self, condition_id) -> str:
        return parse.condition_id_to_text(condition_id)

    def _normalize_condition(self, condition: Optional[str]) -> Optional[str]:
        return parse.normalize_condition(condition)

    def _filter_listings_with_chatgpt(
        self, listings: List[Dict], target_title: str,
        target_author: Optional[str] = None,
        target_publisher: Optional[str] = None,
        target_stock_number: Optional[str] = None,
        target_publication_year: Optional[int] = None,
        require_condition_info: bool = False,
    ) -> List[Dict]:
        return match.filter_listings_with_chatgpt(
            self.openai_client, listings, target_title, target_author,
            target_publisher, target_stock_number, target_publication_year,
            require_condition_info,
            fetch_details=lambda item_id: self.get_item_description(item_id),
        )

    # --- pricing -------------------------------------------------------------

    def get_price_estimate(
        self, title: str, author: Optional[str] = None,
        publisher: Optional[str] = None, stock_number: Optional[str] = None,
        grade: Optional[str] = None, publication_year: Optional[int] = None,
        min_results: int = 3,
        search_results: Optional[List[Dict]] = None,
    ):
        """Delegate to pricing.get_price_estimate; pass search_results to skip re-fetching."""
        return pricing.get_price_estimate(
            self, title, author, publisher, stock_number, grade, publication_year,
            min_results=min_results, search_results=search_results,
        )


def get_price_for_book(
    book_id: int, app_id: str, cert_id: str, dev_id: str,
    sandbox: bool = True, db_path: str = "book_catalog.db",
    openai_api_key: Optional[str] = None,
) -> Optional[Dict]:
    """CLI helper: look up a book, run get_price_estimate, persist the result."""
    from .book_manager import get_book_by_id, update_book

    book = get_book_by_id(book_id, db_path)
    if not book:
        return None

    api = eBayAPI(app_id, cert_id, dev_id, sandbox, openai_api_key=openai_api_key)

    publication_year = None
    if book.publication_date:
        if isinstance(book.publication_date, str):
            import re
            m = re.search(r"\b(19|20)\d{2}\b", book.publication_date)
            if m:
                publication_year = int(m.group())
        else:
            publication_year = book.publication_date.year

    result = api.get_price_estimate(
        title=book.title, author=book.author, publisher=book.publisher,
        stock_number=book.stock_number, grade=book.grade,
        publication_year=publication_year,
    )

    if not result:
        return {"error": "Insufficient data for price estimate"}
    if isinstance(result, dict) and "error" in result:
        return result

    ebay_estimate, price_info = result
    update_book(
        book_id, ebay_estimate=ebay_estimate,
        price_date=price_info["date"], price_source=price_info["source"],
        price_notes=price_info["notes"], db_path=db_path,
    )
    return {"ebay_estimate": ebay_estimate, "price_info": price_info}
