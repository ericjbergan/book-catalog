"""Weighted-median pricing over Buy-It-Now listings for a specific edition.

Orchestrates search + edition filtering + grade weighting into a single
(estimate, price_info) tuple, or an error dict when there isn't enough data.
"""

from datetime import date
from typing import Dict, List, Optional, Tuple, Union

from . import match


PriceResult = Union[Tuple[float, Dict], Dict]


def get_price_estimate(
    api,
    title: str,
    author: Optional[str] = None,
    publisher: Optional[str] = None,
    stock_number: Optional[str] = None,
    grade: Optional[str] = None,
    publication_year: Optional[int] = None,
    min_results: int = 3,
    search_results: Optional[List[Dict]] = None,
) -> Optional[PriceResult]:
    """Estimate a book's eBay price. Pass `search_results` to skip the internal search."""
    if search_results is None:
        search_results = api.search_books(title, None, publisher, None, limit=50)

    if stock_number:
        results = match.prioritize_results(search_results, author, stock_number)
    else:
        results = search_results

    if len(results) < min_results:
        if len(results) == 0:
            return {"error": "No results", "error_type": "no_results"}
        return {"error": "No estimate", "error_type": "insufficient_results",
                "result_count": len(results), "min_required": min_results}

    buy_it_now = [r for r in results if r.get("is_buy_it_now", False) and r.get("price") is not None]

    if publisher or stock_number:
        if api.openai_client:
            buy_it_now = match.filter_listings_with_chatgpt(
                api.openai_client,
                buy_it_now,
                title, author, publisher, stock_number,
                target_publication_year=publication_year,
                require_condition_info=True,
                fetch_details=lambda item_id: api.get_item_description(item_id),
            )
        else:
            buy_it_now = [r for r in buy_it_now if match.matches_edition(r.get("title", ""), publisher, stock_number)]

    # Relax the stock-number filter if the strict one didn't yield enough
    if len(buy_it_now) < min_results and (publisher or stock_number) and stock_number:
        pool = [r for r in results if r.get("is_buy_it_now", False) and r.get("price") is not None]
        relaxed = [r for r in pool if match.matches_edition(r.get("title", ""), publisher, None)]
        if len(relaxed) >= min_results:
            buy_it_now = relaxed

    # Last resort: all Buy-It-Now regardless of edition
    if len(buy_it_now) < min_results:
        all_bin = [r for r in results if r.get("is_buy_it_now", False) and r.get("price") is not None]
        if len(all_bin) >= min_results:
            buy_it_now = all_bin
        else:
            if len(search_results) == 0:
                return {"error": "No results", "error_type": "no_results"}
            return {"error": "No estimate", "error_type": "insufficient_results",
                    "result_count": len(buy_it_now), "min_required": min_results}

    # Backfill missing shipping costs from full item details
    for item in buy_it_now:
        if item.get("shipping_cost") in (0.0, None):
            item_id = item.get("item_id")
            if item_id:
                try:
                    details = api.get_item_details(item_id)
                    fetched = details.get("shipping_cost")
                    if fetched is not None and fetched > 0.0:
                        item["shipping_cost"] = fetched
                except Exception:
                    pass

    total_prices = []
    for item in buy_it_now:
        price = _as_float(item.get("price"))
        shipping = _as_float(item.get("shipping_cost"))
        condition = item.get("chatgpt_grade") or item.get("condition_normalized")
        total_prices.append({
            "total": price + shipping,
            "price": price,
            "shipping": shipping,
            "condition": condition,
            "title": item.get("title", ""),
        })

    if grade:
        weighted = []
        for d in total_prices:
            score = match.grade_match_score(d.get("condition"), grade)
            if d.get("total"):
                weighted.append((d["total"], score, d.get("condition"), d))
        if weighted:
            weighted.sort(key=lambda x: (-x[1], x[0]))
            reasonable = [w for w in weighted if w[1] >= 0.4]
            if len(reasonable) >= 2:
                totals = sorted(w[0] for w in reasonable)
                ebay_estimate = _median(totals)
                top_matches = reasonable
            elif len(reasonable) == 1:
                ebay_estimate = reasonable[0][0]
                top_matches = reasonable
            else:
                totals = sorted(w[0] for w in weighted)
                ebay_estimate = _median(totals)
                top_matches = weighted

            all_totals = [w[0] for w in weighted]
            if all_totals:
                ebay_estimate = max(ebay_estimate, min(all_totals))

            condition_counts: Dict[str, int] = {}
            for _, _, cond, _ in top_matches:
                condition_counts[cond] = condition_counts.get(cond, 0) + 1
            condition_breakdown = ", ".join(f"{k}: {v}" for k, v in condition_counts.items())
        else:
            ebay_estimate = None
            condition_breakdown = "No matching conditions"
    else:
        totals = sorted(d["total"] for d in total_prices)
        ebay_estimate = _median(totals)
        condition_breakdown = "Mixed conditions"

    all_totals = sorted(d["total"] for d in total_prices)
    sample_prices = all_totals[:5]

    edition_info = ""
    if publisher and stock_number:
        edition_info = f"Filtered to {publisher} {stock_number} edition. "
    elif publisher:
        edition_info = f"Filtered to {publisher} publisher. "
    elif stock_number:
        edition_info = f"Filtered to stock number {stock_number}. "

    shipping_values = [_as_float(item.get("shipping_cost")) for item in buy_it_now]
    avg_shipping = sum(shipping_values) / len(shipping_values) if shipping_values else 0.0

    filter_method = "ChatGPT" if api.openai_client and (publisher or stock_number) else "fuzzy matching"
    if publisher or stock_number:
        edition_info += f"Filtered using {filter_method}. "

    price_info = {
        "source": "eBay API (Buy It Now listings, current prices)",
        "date": date.today(),
        "notes": (
            f"{edition_info}Based on {len(buy_it_now)} current Buy It Now listings "
            f"(prices include shipping). Sample total prices: "
            f"${sample_prices[0]:.2f} - ${sample_prices[-1]:.2f}. "
            f"Conditions: {condition_breakdown}. Avg shipping: ${avg_shipping:.2f}"
        ),
        "sample_prices": sample_prices,
        "total_listings": len(buy_it_now),
        "condition_breakdown": condition_breakdown,
        "edition_filtered": bool(publisher or stock_number),
        "filter_method": filter_method if (publisher or stock_number) else None,
        "includes_shipping": True,
    }

    return (ebay_estimate, price_info)


def _as_float(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _median(sorted_values: List[float]) -> float:
    n = len(sorted_values)
    mid = n // 2
    if n % 2 == 1:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2
