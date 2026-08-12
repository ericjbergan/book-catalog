"""Edition matching (fuzzy publisher/stock #) and ChatGPT-based filtering."""

import re
from difflib import SequenceMatcher
from typing import Callable, Dict, List, Optional, Tuple

from .parse import normalize_condition


def fuzzy_similarity(str1: str, str2: str) -> float:
    return SequenceMatcher(None, str1.upper(), str2.upper()).ratio()


def fuzzy_match_stock_number(listing_title: str, target_stock: str, threshold: float = 0.8) -> bool:
    """Match F-206 / F 206 / F206 / 206, tolerating typos."""
    if not target_stock:
        return False

    title_upper = listing_title.upper()
    target_upper = target_stock.upper().strip()
    stock_clean = re.sub(r"^F[- ]?", "", target_upper).strip()
    if not stock_clean:
        return False

    patterns = [
        rf"\b{re.escape(target_upper)}\b",
        rf"\bF[- ]?{re.escape(stock_clean)}\b",
        rf"\b{re.escape(stock_clean)}\b",
    ]
    for pattern in patterns:
        if re.findall(pattern, title_upper):
            return True

    potentials = re.findall(r"\bF[- ]?\d+\b|\b\d{2,}\b", title_upper)
    for potential in potentials:
        potential_clean = re.sub(r"^F[- ]?", "", potential).strip()
        target_clean = re.sub(r"^F[- ]?", "", target_upper).strip()
        if fuzzy_similarity(potential_clean, target_clean) >= threshold:
            return True
    return False


def fuzzy_match_publisher(listing_title: str, target_publisher: str, threshold: float = 0.75) -> bool:
    if not target_publisher:
        return True

    title_upper = listing_title.upper()
    publisher_upper = target_publisher.upper()

    if publisher_upper in title_upper:
        return True

    title_words = title_upper.split()
    publisher_words = publisher_upper.split()

    if len(publisher_words) > 1:
        for i in range(len(title_words) - len(publisher_words) + 1):
            phrase = " ".join(title_words[i:i + len(publisher_words)])
            if fuzzy_similarity(phrase, publisher_upper) >= threshold:
                return True

    for word in title_words:
        if len(word) < 3:
            continue
        for pub_word in publisher_words:
            if len(pub_word) < 3:
                continue
            if fuzzy_similarity(word, pub_word) >= threshold:
                return True

    return False


def matches_edition(listing_title: str, publisher: Optional[str] = None,
                    stock_number: Optional[str] = None) -> bool:
    if not publisher and not stock_number:
        return True
    if publisher and not fuzzy_match_publisher(listing_title, publisher):
        return False
    if stock_number and not fuzzy_match_stock_number(listing_title, stock_number):
        return False
    return True


def grade_match_score(listing_grade: Optional[str], target_grade: Optional[str]) -> float:
    """0.0 = far apart, 1.0 = exact. 0.5 when either grade is unknown."""
    if not target_grade or not listing_grade:
        return 0.5
    if listing_grade == target_grade:
        return 1.0

    hierarchy = {"Fine": 5, "Near Fine": 4, "Very Good": 3, "Good": 2, "Fair": 1}
    listing_level = hierarchy.get(listing_grade, 0)
    target_level = hierarchy.get(target_grade, 0)
    if listing_level == 0 or target_level == 0:
        return 0.5

    diff = abs(listing_level - target_level)
    if diff == 1:
        return 0.7
    if diff == 2:
        return 0.4
    return 0.2


def prioritize_results(results: List[Dict], target_author: Optional[str] = None,
                       target_stock_number: Optional[str] = None) -> List[Dict]:
    """Keep only stock-number matches, then sort by price ascending."""
    if not target_stock_number:
        return results
    matches = [r for r in results if fuzzy_match_stock_number(r.get("title", ""), target_stock_number)]
    matches.sort(key=lambda x: x.get("price", 0) or 0)
    return matches


# Type alias for the item-details fetcher passed into ChatGPT filtering.
# Returns (description, publication_year), either possibly None.
FetchDetailsFn = Callable[[str], Tuple[Optional[str], Optional[int]]]


def filter_listings_with_chatgpt(
    openai_client,
    listings: List[Dict],
    target_title: str,
    target_author: Optional[str] = None,
    target_publisher: Optional[str] = None,
    target_stock_number: Optional[str] = None,
    target_publication_year: Optional[int] = None,
    require_condition_info: bool = False,
    fetch_details: Optional[FetchDetailsFn] = None,
) -> List[Dict]:
    """Ask ChatGPT which listings match the target edition, and grade them from descriptions."""
    if not openai_client or not listings:
        return listings

    try:
        target_description = f"Title: {target_title}"
        if target_author:
            target_description += f"\nAuthor: {target_author}"
        if target_publisher:
            target_description += f"\nPublisher: {target_publisher}"
        if target_stock_number:
            target_description += f"\nStock Number: {target_stock_number}"
        if target_publication_year:
            target_description += f"\nPublication Year: {target_publication_year}"

        # Prefilter: if we know the target year and a listing reports a different year, drop it.
        if target_publication_year:
            filtered = []
            for listing in listings:
                item_id = listing.get("item_id", "")
                year = listing.get("publication_year")
                if not year and item_id and fetch_details is not None:
                    try:
                        _, fetched_year = fetch_details(item_id)
                        if fetched_year:
                            listing["publication_year"] = fetched_year
                            year = fetched_year
                    except Exception:
                        pass
                if year and year != target_publication_year:
                    continue
                filtered.append(listing)
            listings = filtered

        listing_data = []
        for i, listing in enumerate(listings):
            title = listing.get("title", "")
            condition = listing.get("condition", "Unknown")
            condition_id = listing.get("conditionId")
            description = listing.get("description", "")
            item_id = listing.get("item_id", "")

            if require_condition_info and not description and item_id and fetch_details is not None:
                if condition == "Unknown" and not condition_id:
                    try:
                        fetched_desc, fetched_year = fetch_details(item_id)
                        if fetched_desc:
                            listing["description"] = fetched_desc
                            description = fetched_desc
                        if fetched_year and not listing.get("publication_year"):
                            listing["publication_year"] = fetched_year
                    except Exception:
                        pass

            listing_text = f"{i}: Title: {title}"
            publication_year = listing.get("publication_year")
            if publication_year:
                listing_text += f"\n   Publication Year: {publication_year}"
            if condition != "Unknown" or condition_id:
                listing_text += f"\n   Official Condition: {condition}"
            if description:
                listing_text += f"\n   Description: {description[:800]}"
            listing_data.append(listing_text)

        listings_text = "\n".join(listing_data)

        condition_requirement = ""
        if require_condition_info:
            condition_requirement = """
IMPORTANT: Only include listings that have sufficient condition information. A listing has sufficient condition information if:
- It has an official condition field (Condition ID or Condition text), OR
- The item description contains enough detail about the book's condition to grade it (e.g., mentions of wear, creasing, damage, marks, etc.)
- Generic descriptions like "good condition" or "used" without details are NOT sufficient
- Descriptions that mention specific condition details (e.g., "some creasing", "wear on edges", "no marks", "spine crease") ARE sufficient"""

        grading_instructions = ""
        if require_condition_info:
            grading_instructions = """
GRADING INSTRUCTIONS:
For each listing that matches the edition, you must also determine its grade from the description if the Condition field is blank or "Unknown". Use these paperback grading standards:

- **Fine (F)**: Appears unread, no defects, no creases, clean pages, tight binding, minimal wear
- **Near Fine (NF)**: Very minor defects, slight edge wear, no reading crease, clean pages
- **Very Good (VG)**: Shows careful use, may have reading crease, slight creases/scuffs, minor browning, all pages present
- **Good (G)**: More wear, multiple creases, may have markings, some wear to edges/corners, binding intact
- **Fair**: Significant wear, may have tears, heavy creasing, noticeable defects, but complete
- **Poor**: Heavy wear, missing pages, significant damage

Grade conservatively - when in doubt, grade lower. Consider specific details like:
- "no creases" or "no reading crease" suggests Fine or Near Fine
- "some creasing" or "minor creasing" suggests Very Good
- "reading crease" or "spine crease" suggests Very Good to Good
- "wear on edges" or "corner wear" suggests Very Good to Good depending on severity
- "marks" or "writing" suggests Good or lower
- "tears" or "damage" suggests Fair or lower"""

        prompt = f"""You are helping identify which eBay book listings match a specific edition and determine their condition grades.{condition_requirement}{grading_instructions}

Target book details:
{target_description}

eBay listings (numbered):
{listings_text}

Please analyze each listing and:
1. Determine if it matches the EXACT edition described above. Consider:
   - The title must match (allowing for minor variations in punctuation/capitalization)
   - The publisher must match (allowing for typos or abbreviations)
   - The stock number must match if provided (allowing for format variations like "F-206", "F 206", "F206", "206")
   - **CRITICAL: EXCLUDE listings that are clearly different printings/editions:**
     * **If target publication year is provided (e.g., 1963), you MUST EXCLUDE any listing with a different publication year (e.g., 1984, 1990, 2000s). This is a hard requirement - different publication years mean different editions.**
     * EXCLUDE listings that mention different printings (e.g., "45th print", "reprint", "later printing", "1990 edition") when looking for a specific early printing
     * EXCLUDE listings with different publishers (e.g., "Random House" when looking for "Ballantine")
     * EXCLUDE listings with different ISBNs or significantly different publication dates
     * EXCLUDE modern reprints when looking for vintage editions (1960s-1970s)
     * **If a listing shows "Publication Year: 1984" and the target is 1963, that listing MUST be excluded regardless of other matching factors.**
   - Be lenient with typos and formatting differences, but STRICT about edition matching - different printings are NOT matches{condition_requirement}
2. For matching listings, determine the grade:
   - If the listing has an official Condition field (not "Unknown"), use that
   - If the Condition field is blank or "Unknown", grade the book from the description using the grading standards above
   - Return the grade as: Fine, Near Fine, Very Good, Good, Fair, or Poor

Respond in this format:
For each matching listing, provide: INDEX:GRADE
For example: "0:Very Good,2:Fine,5:Good"
If none match, respond with "none".
Do not include any explanation, just the index:grade pairs or "none"."""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that identifies matching book editions from eBay listings and grades them based on condition descriptions."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1000,
        )

        result_text = response.choices[0].message.content.strip()
        if result_text.lower() == "none":
            return []

        try:
            matched = []
            if ":" in result_text:
                for pair in result_text.split(","):
                    pair = pair.strip()
                    if ":" not in pair:
                        continue
                    index_str, grade = pair.split(":", 1)
                    try:
                        index = int(index_str.strip())
                        grade = grade.strip()
                    except ValueError:
                        continue
                    if 0 <= index < len(listings):
                        listing = listings[index].copy()
                        if listing.get("condition") == "Unknown" or not listing.get("conditionId"):
                            listing["chatgpt_grade"] = grade
                            listing["condition_normalized"] = normalize_condition(grade)
                        matched.append(listing)
            else:
                indices = [int(x.strip()) for x in result_text.split(",") if x.strip().isdigit()]
                matched = [listings[i] for i in indices if 0 <= i < len(listings)]
            return matched
        except (ValueError, IndexError) as e:
            print(f"Warning: Could not parse ChatGPT response: {result_text}, error: {e}")
            return []

    except Exception as e:
        print(f"Warning: ChatGPT filtering failed: {e}. Using original listings.")
        return listings
