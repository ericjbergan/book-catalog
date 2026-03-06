"""eBay API integration for price lookups."""

import requests
import base64
import re
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple, Union
import time
from difflib import SequenceMatcher

# Optional OpenAI import for ChatGPT filtering
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class eBayAPI:
    """eBay API client for searching book prices."""
    
    # Sandbox endpoints
    SANDBOX_TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    SANDBOX_BROWSE_URL = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
    
    # Production endpoints
    PRODUCTION_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    PRODUCTION_BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    PRODUCTION_ITEM_URL = "https://api.ebay.com/buy/browse/v1/item/"
    
    # Sandbox item endpoint
    SANDBOX_ITEM_URL = "https://api.sandbox.ebay.com/buy/browse/v1/item/"
    
    def __init__(self, app_id: str, cert_id: str, dev_id: str, sandbox: bool = True, openai_api_key: Optional[str] = None):
        """
        Initialize eBay API client.
        
        Args:
            app_id: App ID (Client ID)
            cert_id: Cert ID (Client Secret)
            dev_id: Dev ID (Developer ID)
            sandbox: Whether to use Sandbox (True) or Production (False)
            openai_api_key: Optional OpenAI API key for ChatGPT filtering
        """
        self.app_id = app_id
        self.cert_id = cert_id
        self.dev_id = dev_id
        self.sandbox = sandbox
        
        self.token_url = self.SANDBOX_TOKEN_URL if sandbox else self.PRODUCTION_TOKEN_URL
        self.browse_url = self.SANDBOX_BROWSE_URL if sandbox else self.PRODUCTION_BROWSE_URL
        self.item_url = self.SANDBOX_ITEM_URL if sandbox else self.PRODUCTION_ITEM_URL
        
        self.access_token = None
        self.token_expires_at = None
        
        # Initialize OpenAI client if key provided
        self.openai_client = None
        if openai_api_key and OPENAI_AVAILABLE:
            try:
                self.openai_client = OpenAI(api_key=openai_api_key)
            except Exception as e:
                print(f"Warning: Could not initialize OpenAI client: {e}")
        elif openai_api_key and not OPENAI_AVAILABLE:
            print("Warning: OpenAI library not installed. Install with: pip install openai")
    
    def _get_access_token(self) -> str:
        """Get OAuth 2.0 access token."""
        # If we have a valid token, return it
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return self.access_token
        
        # Create credentials string
        credentials = f"{self.app_id}:{self.cert_id}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        # Request token
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_credentials}"
        }
        
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        }
        
        try:
            response = requests.post(self.token_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data["access_token"]
            
            # Set expiration (usually 7200 seconds, but we'll use 7000 to be safe)
            expires_in = token_data.get("expires_in", 7200)
            from datetime import timedelta
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 200)
            
            return self.access_token
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get eBay access token: {e}")
    
    def search_books(
        self,
        title: str,
        author: Optional[str] = None,
        publisher: Optional[str] = None,
        stock_number: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Search for books on eBay.
        
        Args:
            title: Book title
            author: Author name (optional)
            publisher: Publisher name (optional)
            stock_number: Stock number (optional)
            limit: Maximum number of results (default 20)
        
        Returns:
            List of book listings with price information
        """
        # Get access token
        token = self._get_access_token()
        
        # Build search query
        query_parts = [title]
        if author:
            query_parts.append(author)
        if publisher:
            query_parts.append(publisher)
        if stock_number:
            query_parts.append(stock_number)
        
        query = " ".join(query_parts)
        
        # Add category filter for books (category ID 267 for Books)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
        }
        
        # Build filter string - prioritize Buy It Now listings
        filters = ["deliveryCountry:US", "buyingOptions:{FIXED_PRICE}"]  # Buy It Now filter
        
        params = {
            "q": query,
            "limit": min(limit, 200),  # eBay max is 200
            "category_ids": "267",  # Books category
            "sort": "price",  # Sort by price
            "filter": ",".join(filters)  # Multiple filters
        }
        
        try:
            response = requests.get(self.browse_url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get("itemSummaries", [])
            
            results = []
            for item in items:
                price_info = item.get("price", {})
                price_value = price_info.get("value") if price_info else None
                # Convert to float if it's a string
                if price_value is not None:
                    try:
                        price_value = float(price_value)
                    except (ValueError, TypeError):
                        price_value = None
                
                currency = price_info.get("currency") if price_info else None
                
                # Get condition if available - eBay uses conditionId or condition
                condition_id = item.get("conditionId")
                condition = item.get("condition", "Unknown")
                # If we have conditionId, try to get condition text
                if condition == "Unknown" and condition_id:
                    condition = self._condition_id_to_text(condition_id)
                
                # Normalize condition to match our grading system
                condition_normalized = self._normalize_condition(condition)
                
                # Check if it's Buy It Now (should be filtered, but double-check)
                buying_options = item.get("buyingOptions", [])
                is_buy_it_now = "FIXED_PRICE" in buying_options
                
                # Get item URL
                item_web_url = item.get("itemWebUrl", "")
                
                # Get shipping cost and convert to float
                # Try multiple ways to get shipping information
                shipping_value = None
                
                # Method 1: Check shippingOptions array
                shipping_options = item.get("shippingOptions", [])
                if shipping_options:
                    for option in shipping_options:
                        shipping_cost = option.get("shippingCost", {})
                        if shipping_cost:
                            value = shipping_cost.get("value")
                            if value is not None:
                                try:
                                    shipping_value = float(value)
                                    break  # Use first available shipping cost
                                except (ValueError, TypeError):
                                    pass
                
                # Method 2: Check for shippingCost at top level
                if shipping_value is None:
                    top_level_shipping = item.get("shippingCost", {})
                    if top_level_shipping:
                        value = top_level_shipping.get("value")
                        if value is not None:
                            try:
                                shipping_value = float(value)
                            except (ValueError, TypeError):
                                pass
                
                # Method 3: Check for "FREE" shipping indicators
                if shipping_value is None:
                    # Check if shipping is explicitly marked as free
                    for option in shipping_options:
                        shipping_cost = option.get("shippingCost", {})
                        if shipping_cost:
                            # Check for "FREE" or 0 value
                            cost_type = shipping_cost.get("shippingCostType", "").upper()
                            if "FREE" in cost_type or shipping_cost.get("value") == "0" or shipping_cost.get("value") == 0:
                                shipping_value = 0.0
                                break
                
                # Default to 0.0 if no shipping info found
                if shipping_value is None:
                    shipping_value = 0.0
                
                # Try to get shortDescription if available (some items have it in search results)
                short_description = item.get("shortDescription", "")
                
                # Check eBay's format/binding information from aspects first (most reliable)
                format_from_aspects = None
                localized_aspects = item.get("localizedAspects", [])
                if isinstance(localized_aspects, list):
                    for aspect in localized_aspects:
                        if isinstance(aspect, dict):
                            name = aspect.get("localizedName", "") or aspect.get("name", "")
                            value = aspect.get("value", "").lower() if aspect.get("value") else ""
                            # Check for format/binding fields
                            if any(keyword in name.lower() for keyword in ["format", "binding", "book format", "book type"]):
                                format_from_aspects = value
                                break
                
                # Also check aspects dict
                if not format_from_aspects:
                    item_aspects = item.get("aspects", {}) or item.get("itemAspects", {})
                    if isinstance(item_aspects, dict):
                        for key in ["Format", "format", "Binding", "binding", "Book Format", "Book Type"]:
                            if key in item_aspects:
                                format_value = item_aspects[key]
                                if isinstance(format_value, str):
                                    format_from_aspects = format_value.lower()
                                    break
                
                # Check if this is a paperback or hardcover
                # Combine title and description to check format
                title_text = item.get("title", "").lower()
                desc_text = short_description.lower() if short_description else ""
                combined_text = f"{title_text} {desc_text}"
                
                # If we have format from aspects, use that as primary source
                if format_from_aspects:
                    # Check if it's hardcover
                    hardcover_format_indicators = ["hardcover", "hard cover", "hc", "h/c", "cloth", "hardbound", "hard bound"]
                    is_hardcover = any(indicator in format_from_aspects for indicator in hardcover_format_indicators)
                    # Check if it's paperback
                    paperback_format_indicators = ["paperback", "pb", "mass market", "trade", "softcover", "soft cover"]
                    is_paperback = any(indicator in format_from_aspects for indicator in paperback_format_indicators)
                else:
                    # Fall back to text analysis if no format info in aspects
                    # Check for hardcover indicators (exclude these)
                    hardcover_indicators = ["hardcover", "hard cover", "hc", "h/c", "h.c.", "cloth", "dj", "dust jacket", "dustjacket", "hardbound", "hard bound"]
                    is_hardcover = any(indicator in combined_text for indicator in hardcover_indicators)
                    
                    # Check for paperback indicators (prefer these)
                    paperback_indicators = ["paperback", "pb", "p/b", "mass market", "mm pb", "trade pb", "softcover", "soft cover"]
                    is_paperback = any(indicator in combined_text for indicator in paperback_indicators)
                
                # STRICT FILTERING: Only include paperbacks, exclude all hardcovers
                # If it's hardcover (regardless of other indicators), skip it
                if is_hardcover:
                    continue
                
                # If format is unknown and no paperback indicators found, be conservative and skip it
                # (We want to be sure it's a paperback, not just "maybe")
                if not is_paperback and not format_from_aspects:
                    # Skip items with no clear format indication to avoid including hardcovers
                    continue
                
                # Try to extract publication year from item specifics or other fields
                # eBay Browse API may have this in localizedAspects (array) or aspects (dict)
                publication_year = None
                
                # Try localizedAspects first (array of objects with localizedName and value)
                # Note: localized_aspects was already retrieved above for format checking, reuse it
                if isinstance(localized_aspects, list):
                    for aspect in localized_aspects:
                        if isinstance(aspect, dict):
                            name = aspect.get("localizedName", "") or aspect.get("name", "")
                            value = aspect.get("value", "")
                            # Check if this is a publication year field (skip format/binding fields we already checked)
                            if "publication" in name.lower() and "year" in name.lower():
                                try:
                                    if isinstance(value, str):
                                        year_match = re.search(r'\b(19|20)\d{2}\b', value)
                                        if year_match:
                                            publication_year = int(year_match.group())
                                    elif isinstance(value, (int, float)):
                                        publication_year = int(value)
                                    if publication_year:
                                        break
                                except (ValueError, TypeError):
                                    pass
                
                # Fallback to aspects dict
                if not publication_year:
                    item_aspects = item.get("aspects", {}) or item.get("itemAspects", {})
                    if isinstance(item_aspects, dict):
                        # Look for publication year in various possible keys
                        for key in ["Publication Year", "publicationYear", "PublicationYear", "Year", "year"]:
                            if key in item_aspects:
                                try:
                                    year_val = item_aspects[key]
                                    if isinstance(year_val, str):
                                        # Extract year from string (e.g., "1984" or "1984-01-01")
                                        year_match = re.search(r'\b(19|20)\d{2}\b', year_val)
                                        if year_match:
                                            publication_year = int(year_match.group())
                                    elif isinstance(year_val, (int, float)):
                                        publication_year = int(year_val)
                                    if publication_year:
                                        break
                                except (ValueError, TypeError):
                                    pass
                
                # Determine format
                format_type = "Unknown"
                if is_paperback:
                    format_type = "Paperback"
                elif is_hardcover:
                    format_type = "Hardcover"
                
                results.append({
                    "title": item.get("title", ""),
                    "price": price_value,
                    "currency": currency,
                    "condition": condition,
                    "conditionId": condition_id,
                    "condition_normalized": condition_normalized,
                    "is_buy_it_now": is_buy_it_now,
                    "url": item_web_url,
                    "item_id": item.get("itemId", ""),
                    "seller": item.get("seller", {}).get("username", ""),
                    "shipping_cost": shipping_value,
                    "description": short_description,  # May be empty, will fetch full description if needed
                    "publication_year": publication_year,  # May be None if not available
                    "format": format_type,  # Paperback, Hardcover, or Unknown
                    "is_paperback": is_paperback,
                    "is_hardcover": is_hardcover
                })
            
            # Sort results: paperbacks first, then by price
            results.sort(key=lambda x: (
                0 if x.get("is_paperback") else (1 if not x.get("is_hardcover") else 2),
                x.get("price") or float('inf')
            ))

            return results
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to search eBay: {e}")
    
    def get_item_details(self, item_id: str) -> Dict:
        """
        Fetch full item details including shipping cost for a specific eBay item.
        
        Args:
            item_id: eBay item ID
        
        Returns:
            Dictionary with item details including shipping_cost, description, and publication_year
        """
        try:
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
            }
            
            response = requests.get(f"{self.item_url}{item_id}", headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract shipping cost
            shipping_value = None
            shipping_options = data.get("shippingOptions", [])
            if shipping_options:
                for option in shipping_options:
                    shipping_cost = option.get("shippingCost", {})
                    if shipping_cost:
                        value = shipping_cost.get("value")
                        if value is not None:
                            try:
                                shipping_value = float(value)
                                break
                            except (ValueError, TypeError):
                                pass
            
            # Try to get description from various possible fields
            description = data.get("shortDescription") or data.get("description") or data.get("itemDescription")
            
            # Try to extract publication year from item aspects
            # eBay Browse API uses "localizedAspects" or "aspects" arrays
            publication_year = None
            
            # Try localizedAspects first (array of objects with localizedName and value)
            localized_aspects = data.get("localizedAspects", [])
            if isinstance(localized_aspects, list):
                for aspect in localized_aspects:
                    if isinstance(aspect, dict):
                        name = aspect.get("localizedName", "") or aspect.get("name", "")
                        value = aspect.get("value", "")
                        # Check if this is a publication year field
                        if "publication" in name.lower() and "year" in name.lower():
                            try:
                                if isinstance(value, str):
                                    year_match = re.search(r'\b(19|20)\d{2}\b', value)
                                    if year_match:
                                        publication_year = int(year_match.group())
                                elif isinstance(value, (int, float)):
                                    publication_year = int(value)
                                if publication_year:
                                    break
                            except (ValueError, TypeError):
                                pass
            
            # Fallback to aspects dict
            if not publication_year:
                item_aspects = data.get("aspects", {}) or data.get("itemAspects", {})
                if isinstance(item_aspects, dict):
                    # Look for publication year in various possible keys
                    for key in ["Publication Year", "publicationYear", "PublicationYear", "Year", "year"]:
                        if key in item_aspects:
                            try:
                                year_val = item_aspects[key]
                                if isinstance(year_val, str):
                                    year_match = re.search(r'\b(19|20)\d{2}\b', year_val)
                                    if year_match:
                                        publication_year = int(year_match.group())
                                elif isinstance(year_val, (int, float)):
                                    publication_year = int(year_val)
                                if publication_year:
                                    break
                            except (ValueError, TypeError):
                                pass
            
            return {
                "shipping_cost": shipping_value if shipping_value is not None else 0.0,
                "description": description,
                "publication_year": publication_year
            }
        except requests.exceptions.RequestException as e:
            return {
                "shipping_cost": 0.0,
                "description": None,
                "publication_year": None
            }
    
    def get_item_description(self, item_id: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Fetch the full item description and publication year for a specific eBay item.
        
        Args:
            item_id: eBay item ID
        
        Returns:
            Tuple of (description text, publication_year) or (None, None) if unavailable
        """
        details = self.get_item_details(item_id)
        return (details.get("description"), details.get("publication_year"))
    
    def _fuzzy_match_stock_number(self, listing_title: str, target_stock: str, threshold: float = 0.8) -> bool:
        """
        Check if listing title contains the stock number with fuzzy matching.
        Handles variations like "F-206", "F 206", "F206", "206", etc., and typos.
        
        Args:
            listing_title: The listing title to search
            target_stock: Target stock number (e.g., "F-206", "F777")
            threshold: Minimum similarity ratio for fuzzy match (default 0.8)
        
        Returns:
            True if stock number is found (with fuzzy matching)
        """
        if not target_stock:
            return False
        
        title_upper = listing_title.upper()
        target_upper = target_stock.upper().strip()
        
        # Extract the numeric part
        stock_clean = re.sub(r'^F[- ]?', '', target_upper).strip()
        
        if not stock_clean:
            return False
        
        # First try exact pattern matching (format variations)
        patterns = [
            rf'\b{re.escape(target_upper)}\b',  # Exact match: "F-206"
            rf'\bF[- ]?{re.escape(stock_clean)}\b',  # "F-206", "F 206", "F206"
            rf'\b{re.escape(stock_clean)}\b',  # Just the number: "206"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, title_upper)
            if matches:
                return True
        
        # If no exact pattern match, try fuzzy matching on potential stock numbers in title
        # Look for patterns that might be stock numbers (F followed by numbers, or just numbers)
        potential_stocks = re.findall(r'\bF[- ]?\d+\b|\b\d{2,}\b', title_upper)
        
        for potential in potential_stocks:
            # Normalize both for comparison (remove F- prefix variations)
            potential_clean = re.sub(r'^F[- ]?', '', potential).strip()
            target_clean = re.sub(r'^F[- ]?', '', target_upper).strip()
            
            # Check similarity
            similarity = self._fuzzy_similarity(potential_clean, target_clean)
            if similarity >= threshold:
                return True
        
        return False
    
    def prioritize_results(
        self,
        results: List[Dict],
        target_author: Optional[str] = None,
        target_stock_number: Optional[str] = None
    ) -> List[Dict]:
        """
        Prioritize search results to show best matches first.
        Results matching the exact edition (stock_number) are scored higher.
        
        Args:
            results: List of search results from eBay
            target_author: Target author name (optional, not used for scoring)
            target_stock_number: Target stock number (optional)
        
        Returns:
            List of results sorted by match score (best matches first)
        """
        if not target_stock_number:
            return results  # No prioritization needed

        # Filter to only results that match the stock number, then sort by price
        matches = []
        for result in results:
            if self._fuzzy_match_stock_number(result.get("title", ""), target_stock_number):
                matches.append(result)

        matches.sort(key=lambda x: x.get("price", 0) or 0)
        return matches
    
    def _condition_id_to_text(self, condition_id: str) -> str:
        """
        Convert eBay condition ID to text description.
        
        Args:
            condition_id: eBay condition ID (e.g., "1000", "3000")
        
        Returns:
            Condition text description
        """
        condition_map = {
            "1000": "New",
            "1500": "New other",
            "2000": "Certified - Refurbished",
            "2500": "Excellent - Refurbished",
            "3000": "Used",
            "4000": "Very Good",
            "5000": "Good",
            "6000": "Acceptable",
            "7000": "For parts or not working"
        }
        return condition_map.get(str(condition_id), "Unknown")
    
    def _normalize_condition(self, condition: str) -> Optional[str]:
        """
        Normalize eBay condition or ChatGPT grade to match our grading system.
        
        Args:
            condition: eBay condition string or ChatGPT-determined grade
        
        Returns:
            Normalized condition (Fine, Very Good, Good, Fair, etc.) or None
        """
        if not condition:
            return None
        
        condition_lower = condition.lower()
        
        # Map eBay conditions and grades to our grading system
        if "new" in condition_lower or "mint" in condition_lower or "very fine" in condition_lower:
            return "Fine"
        elif "fine" in condition_lower and "near" not in condition_lower:
            return "Fine"
        elif "near fine" in condition_lower or "near-fine" in condition_lower:
            return "Near Fine"
        elif "very good" in condition_lower or "excellent" in condition_lower:
            return "Very Good"
        elif "good" in condition_lower:
            return "Good"
        elif "fair" in condition_lower:
            return "Fair"
        elif "acceptable" in condition_lower or "poor" in condition_lower:
            return "Fair"  # Map both to Fair for simplicity
        else:
            return None  # Unknown condition
    
    def _grade_match_score(self, listing_grade: Optional[str], target_grade: Optional[str]) -> float:
        """
        Calculate how well a listing's grade matches the target grade.
        
        Returns:
            Score from 0.0 (no match) to 1.0 (exact match)
        """
        if not target_grade or not listing_grade:
            return 0.5  # Neutral score if we can't compare
        
        # Exact match
        if listing_grade == target_grade:
            return 1.0
        
        # Grade hierarchy for partial matches
        grade_hierarchy = {"Fine": 5, "Near Fine": 4, "Very Good": 3, "Good": 2, "Fair": 1}
        
        listing_level = grade_hierarchy.get(listing_grade, 0)
        target_level = grade_hierarchy.get(target_grade, 0)
        
        if listing_level == 0 or target_level == 0:
            return 0.5  # Unknown grade
        
        # Closer grades get higher scores
        difference = abs(listing_level - target_level)
        if difference == 1:
            return 0.7  # One grade away
        elif difference == 2:
            return 0.4  # Two grades away
        else:
            return 0.2  # Far apart
    
    def _fuzzy_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity ratio between two strings using SequenceMatcher.
        Returns a value between 0.0 (no similarity) and 1.0 (identical).
        
        Args:
            str1: First string
            str2: Second string
        
        Returns:
            Similarity ratio (0.0 to 1.0)
        """
        return SequenceMatcher(None, str1.upper(), str2.upper()).ratio()
    
    def _fuzzy_match_publisher(self, listing_title: str, target_publisher: str, threshold: float = 0.75) -> bool:
        """
        Check if listing title contains publisher with fuzzy matching.
        Uses string similarity to handle typos and variations.
        
        Args:
            listing_title: The listing title to search
            target_publisher: Target publisher name
            threshold: Minimum similarity ratio (0.0 to 1.0, default 0.75 = 75% similar)
        
        Returns:
            True if publisher is found (with fuzzy matching)
        """
        if not target_publisher:
            return True
        
        title_upper = listing_title.upper()
        publisher_upper = target_publisher.upper()
        
        # Direct match
        if publisher_upper in title_upper:
            return True
        
        # Split title into words and check each word/phrase against publisher
        # Also check multi-word combinations
        title_words = title_upper.split()
        publisher_words = publisher_upper.split()
        
        # Check if publisher as a whole phrase appears (fuzzy)
        # Try sliding window approach for multi-word publishers
        if len(publisher_words) > 1:
            # Check for the full publisher phrase
            for i in range(len(title_words) - len(publisher_words) + 1):
                phrase = " ".join(title_words[i:i + len(publisher_words)])
                similarity = self._fuzzy_similarity(phrase, publisher_upper)
                if similarity >= threshold:
                    return True
        
        # Check individual words (for single-word publishers or if phrase doesn't match)
        for word in title_words:
            # Skip very short words
            if len(word) < 3:
                continue
            
            # Check against each publisher word
            for pub_word in publisher_words:
                if len(pub_word) < 3:
                    continue
                
                similarity = self._fuzzy_similarity(word, pub_word)
                if similarity >= threshold:
                    return True
        
        return False
    
    def _matches_edition(
        self,
        listing_title: str,
        publisher: Optional[str] = None,
        stock_number: Optional[str] = None
    ) -> bool:
        """
        Check if a listing matches the specific edition (publisher and stock number).
        Uses fuzzy matching to handle typos and variations.
        
        Args:
            listing_title: The listing title from eBay
            publisher: Target publisher (e.g., "Ace", "Ballantine")
            stock_number: Target stock number (e.g., "F-156", "F777")
        
        Returns:
            True if the listing appears to match the specific edition (with fuzzy matching)
        """
        if not publisher and not stock_number:
            return True  # No specific edition to match
        
        matches = True
        
        # Check publisher match with fuzzy matching
        if publisher:
            publisher_found = self._fuzzy_match_publisher(listing_title, publisher)
            if not publisher_found:
                matches = False
        
        # Check stock number match using fuzzy matching
        if stock_number and matches:
            stock_found = self._fuzzy_match_stock_number(listing_title, stock_number)
            if not stock_found:
                matches = False
        
        return matches
    
    def _filter_listings_with_chatgpt(
        self,
        listings: List[Dict],
        target_title: str,
        target_author: Optional[str] = None,
        target_publisher: Optional[str] = None,
        target_stock_number: Optional[str] = None,
        target_publication_year: Optional[int] = None,
        require_condition_info: bool = False
    ) -> List[Dict]:
        """
        Use ChatGPT to identify which listings truly match the target edition.
        Optionally filters to only listings with sufficient condition information.
        
        Args:
            listings: List of eBay listing dictionaries
            target_title: Target book title
            target_author: Target author (optional)
            target_publisher: Target publisher (optional)
            target_stock_number: Target stock number (optional)
            require_condition_info: If True, only return listings with condition info (default False)
        
        Returns:
            List of listings that ChatGPT identified as matching (and have condition info if required)
        """
        if not self.openai_client or not listings:
            return listings
        
        try:
            # Build description of target book
            target_description = f"Title: {target_title}"
            if target_author:
                target_description += f"\nAuthor: {target_author}"
            if target_publisher:
                target_description += f"\nPublisher: {target_publisher}"
            if target_stock_number:
                target_description += f"\nStock Number: {target_stock_number}"
            if target_publication_year:
                target_description += f"\nPublication Year: {target_publication_year}"
            
            # Pre-filter: If we have a target publication year, fetch publication years for all listings
            # and exclude those with different years before sending to ChatGPT
            if target_publication_year:
                filtered_listings = []
                for listing in listings:
                    item_id = listing.get("item_id", "")
                    listing_year = listing.get("publication_year")
                    
                    # If we don't have publication year, try to fetch it from full item details
                    # This is important because search results may not include publication year
                    if not listing_year and item_id:
                        try:
                            _, fetched_year = self.get_item_description(item_id)
                            if fetched_year:
                                listing["publication_year"] = fetched_year
                                listing_year = fetched_year
                        except Exception as e:
                            # If we can't fetch, continue (let ChatGPT decide based on other info)
                            pass
                    
                    # If we have a year and it doesn't match, exclude it
                    if listing_year and listing_year != target_publication_year:
                        continue  # Skip this listing - different publication year
                    
                    # Include if no year (let ChatGPT decide based on other clues) or if year matches
                    filtered_listings.append(listing)
                
                listings = filtered_listings
            
            # Prepare listing data for ChatGPT
            # Include title, condition field, description, and publication year if available
            listing_data = []
            for i, listing in enumerate(listings):
                title = listing.get("title", "")
                condition = listing.get("condition", "Unknown")
                condition_id = listing.get("conditionId")
                description = listing.get("description", "")
                item_id = listing.get("item_id", "")
                publication_year = listing.get("publication_year")
                
                # If we need condition info and don't have it, try to fetch description
                if require_condition_info and not description and item_id:
                    if condition == "Unknown" and not condition_id:
                        # Fetch description and publication year from API
                        fetched_description, fetched_year = self.get_item_description(item_id)
                        if fetched_description:
                            listing["description"] = fetched_description
                        if fetched_year and not listing.get("publication_year"):
                            listing["publication_year"] = fetched_year
                            publication_year = fetched_year
                
                listing_text = f"{i}: Title: {title}"
                
                # Include publication year if available (critical for edition matching)
                publication_year = listing.get("publication_year")
                if publication_year:
                    listing_text += f"\n   Publication Year: {publication_year}"
                
                # Include publisher if available (from description or title)
                # Note: Publisher is usually in the title, but we can check description too
                
                if condition != "Unknown" or condition_id:
                    listing_text += f"\n   Official Condition: {condition}"
                if description:
                    listing_text += f"\n   Description: {description[:800]}"  # Increased limit to capture more details
                
                listing_data.append(listing_text)
            
            listings_text = "\n".join(listing_data)
            
            # Create prompt for ChatGPT
            condition_requirement = ""
            if require_condition_info:
                condition_requirement = """
IMPORTANT: Only include listings that have sufficient condition information. A listing has sufficient condition information if:
- It has an official condition field (Condition ID or Condition text), OR
- The item description contains enough detail about the book's condition to grade it (e.g., mentions of wear, creasing, damage, marks, etc.)
- Generic descriptions like "good condition" or "used" without details are NOT sufficient
- Descriptions that mention specific condition details (e.g., "some creasing", "wear on edges", "no marks", "spine crease") ARE sufficient"""
            
            # Build grading instructions
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
            
            # Call ChatGPT
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Using cheaper model for cost efficiency
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that identifies matching book editions from eBay listings and grades them based on condition descriptions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for more deterministic results
                max_tokens=1000  # Enough for 50 listings with index:grade pairs
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse response
            if result_text.lower() == "none":
                return []
            
            # Extract indices and grades
            try:
                matched_listings = []
                # Parse format: "0:Very Good,2:Fine,5:Good" or fallback to "0,2,5"
                if ":" in result_text:
                    # New format with grades
                    pairs = result_text.split(",")
                    for pair in pairs:
                        pair = pair.strip()
                        if ":" in pair:
                            index_str, grade = pair.split(":", 1)
                            try:
                                index = int(index_str.strip())
                                grade = grade.strip()
                                if 0 <= index < len(listings):
                                    listing = listings[index].copy()
                                    # Store ChatGPT-determined grade if condition was blank
                                    if listing.get("condition") == "Unknown" or not listing.get("conditionId"):
                                        listing["chatgpt_grade"] = grade
                                        listing["condition_normalized"] = self._normalize_condition(grade)
                                    matched_listings.append(listing)
                            except (ValueError, IndexError):
                                continue
                else:
                    # Fallback: old format without grades (comma-separated indices)
                    indices = [int(x.strip()) for x in result_text.split(",") if x.strip().isdigit()]
                    valid_indices = [i for i in indices if 0 <= i < len(listings)]
                    matched_listings = [listings[i] for i in valid_indices]
                
                return matched_listings
            except (ValueError, IndexError) as e:
                # If parsing fails entirely, return nothing rather than all unfiltered listings
                print(f"Warning: Could not parse ChatGPT response: {result_text}, error: {e}")
                return []
        
        except Exception as e:
            print(f"Warning: ChatGPT filtering failed: {e}. Using original listings.")
            return listings
    
    def get_price_estimate(
        self,
        title: str,
        author: Optional[str] = None,
        publisher: Optional[str] = None,
        stock_number: Optional[str] = None,
        grade: Optional[str] = None,
        publication_year: Optional[int] = None,
        min_results: int = 3
    ) -> Optional[Union[Tuple[float, Dict], Dict]]:
        """
        Get price estimates (market value and eBay estimate) for a book.
        eBay estimate is based on Buy It Now listings, considering condition/grade.
        Only uses listings that match the specific edition (publisher and stock number).
        
        Args:
            title: Book title
            author: Author name (optional)
            publisher: Publisher name (optional)
            stock_number: Stock number (optional)
            grade: Book grade (optional, for filtering similar condition)
            min_results: Minimum number of results needed for estimate (default 3)
        
        Returns:
            Tuple of (ebay_estimate, price_info_dict) or None if insufficient data
            price_info_dict contains: source, date, notes, sample_prices, condition_breakdown
            Note: market_value is NOT calculated here - it should be set manually or from other sources
        """
        # Search for the book using only title and publisher to get more results
        # We'll filter/prioritize by edition after getting results
        search_results = self.search_books(title, None, publisher, None, limit=50)
        
        # Prioritize results to match the exact edition (stock_number only)
        if stock_number:
            results = self.prioritize_results(search_results, author, stock_number)
        else:
            results = search_results
        
        if len(results) < min_results:
            # Check if we have any results at all
            if len(results) == 0:
                return {"error": "No results", "error_type": "no_results"}
            else:
                return {"error": "No estimate", "error_type": "insufficient_results", "result_count": len(results), "min_required": min_results}
        
        # Filter to only Buy It Now listings and extract prices with condition info
        buy_it_now_results = [r for r in results if r.get("is_buy_it_now", False) and r.get("price") is not None]
        
        # IMPORTANT: Filter to only listings that match the specific edition
        # AND have condition information (official condition field OR sufficient description)
        # Use ChatGPT if available, otherwise use fuzzy matching
        if publisher or stock_number:
            if self.openai_client:
                # Use ChatGPT to filter listings - require condition info for price estimates
                buy_it_now_results = self._filter_listings_with_chatgpt(
                    buy_it_now_results,
                    title,
                    author,
                    publisher,
                    stock_number,
                    target_publication_year=publication_year,
                    require_condition_info=True  # Only use listings with condition info
                )
            else:
                # Fall back to fuzzy matching
                edition_matched = []
                for r in buy_it_now_results:
                    if self._matches_edition(r.get("title", ""), publisher, stock_number):
                        edition_matched.append(r)
                buy_it_now_results = edition_matched
            
            # Update notes to reflect filtering
            if len(buy_it_now_results) < len([r for r in results if r.get("is_buy_it_now", False)]):
                filtered_count = len([r for r in results if r.get("is_buy_it_now", False)]) - len(buy_it_now_results)
                # Note: We filtered out listings that didn't match the specific edition
        
        # If we filtered by edition and don't have enough results, try relaxing the filter
        if len(buy_it_now_results) < min_results and (publisher or stock_number):
            # First try relaxing stock number requirement (keep publisher)
            if stock_number:
                relaxed_results = []
                for r in [r for r in results if r.get("is_buy_it_now", False) and r.get("price") is not None]:
                    if self._matches_edition(r.get("title", ""), publisher, None):  # No stock number requirement
                        relaxed_results.append(r)
                if len(relaxed_results) >= min_results:
                    buy_it_now_results = relaxed_results
                    # Note: Using listings matching publisher but not specific stock number
        
        if len(buy_it_now_results) < min_results:
            # Last resort: use all Buy It Now results (but note this in the estimate)
            all_buy_it_now = [r for r in results if r.get("is_buy_it_now", False) and r.get("price") is not None]
            if len(all_buy_it_now) >= min_results:
                buy_it_now_results = all_buy_it_now
                # Note: Using all matching listings (may include different editions)
            else:
                # Return error info: check if we have any results at all
                if len(search_results) == 0:
                    return {"error": "No results", "error_type": "no_results"}
                else:
                    return {"error": "No estimate", "error_type": "insufficient_results", "result_count": len(buy_it_now_results), "min_required": min_results}
        
        # Fetch shipping costs from item details if missing from search results
        # Only do this for items we'll actually use in price estimates
        for item in buy_it_now_results:
            if item.get("shipping_cost") == 0.0 or item.get("shipping_cost") is None:
                item_id = item.get("item_id")
                if item_id:
                    try:
                        details = self.get_item_details(item_id)
                        fetched_shipping = details.get("shipping_cost")
                        if fetched_shipping is not None and fetched_shipping > 0.0:
                            item["shipping_cost"] = fetched_shipping
                    except Exception as e:
                        # If fetching fails, keep the 0.0 value
                        pass
        
        # Calculate total prices (price + shipping) for all listings
        total_prices = []
        for item in buy_it_now_results:
            # Ensure both price and shipping are floats
            price = item.get("price")
            if price is None:
                price = 0.0
            else:
                try:
                    price = float(price)
                except (ValueError, TypeError):
                    price = 0.0
            
            shipping = item.get("shipping_cost")
            if shipping is None:
                shipping = 0.0
            else:
                try:
                    shipping = float(shipping)
                except (ValueError, TypeError):
                    shipping = 0.0
            
            total = price + shipping
            
            # Use ChatGPT grade if available, otherwise use condition_normalized
            condition = item.get("chatgpt_grade") or item.get("condition_normalized")
            
            total_prices.append({
                "total": total,
                "price": price,
                "shipping": shipping,
                "condition": condition,
                "title": item.get("title", "")
            })
        
        # If we have a target grade, weight results by condition match
        if grade:
            # Calculate weighted total prices based on condition match
            weighted_totals = []
            for item_data in total_prices:
                listing_grade = item_data.get("condition")
                match_score = self._grade_match_score(listing_grade, grade)
                total = item_data.get("total")
                if total:
                    # Weight total price by match score (better matches count more)
                    weighted_totals.append((total, match_score, listing_grade, item_data))
            
            if weighted_totals:
                # Sort by match score (best matches first), then by total price
                weighted_totals.sort(key=lambda x: (-x[1], x[0]))
                
                # Calculate eBay estimate: use median of all matching listings for stability
                # Use all listings that have a reasonable match score (>= 0.4, which is 2 grades away)
                # This ensures we include listings that are reasonably close in condition
                reasonable_matches = [item for item in weighted_totals if item[1] >= 0.4]
                
                if len(reasonable_matches) >= 2:
                    # Use median of all reasonable matches
                    match_totals = [total for total, _, _, _ in reasonable_matches]
                    match_totals.sort()
                    median_idx = len(match_totals) // 2
                    ebay_estimate = match_totals[median_idx] if len(match_totals) % 2 == 1 else (match_totals[median_idx - 1] + match_totals[median_idx]) / 2
                    top_matches = reasonable_matches  # For condition breakdown
                elif len(reasonable_matches) == 1:
                    # Single match - use that price
                    ebay_estimate = reasonable_matches[0][0]
                    top_matches = reasonable_matches
                else:
                    # No reasonable matches, use all available
                    match_totals = [total for total, _, _, _ in weighted_totals]
                    match_totals.sort()
                    median_idx = len(match_totals) // 2
                    ebay_estimate = match_totals[median_idx] if len(match_totals) % 2 == 1 else (match_totals[median_idx - 1] + match_totals[median_idx]) / 2
                    top_matches = weighted_totals
                
                # Safety check: ensure estimate is not lower than the minimum listing price
                all_totals = [total for total, _, _, _ in weighted_totals]
                if all_totals:
                    min_price = min(all_totals)
                    if ebay_estimate < min_price:
                        # Use minimum price if estimate is somehow lower (shouldn't happen, but safeguard)
                        ebay_estimate = min_price
                
                # Get condition breakdown for notes
                condition_counts = {}
                for _, _, cond, _ in top_matches:
                    condition_counts[cond] = condition_counts.get(cond, 0) + 1
                
                condition_breakdown = ", ".join([f"{k}: {v}" for k, v in condition_counts.items()])
            else:
                ebay_estimate = None
                condition_breakdown = "No matching conditions"
        else:
            # No target grade - use median of total prices (including shipping)
            totals = [item["total"] for item in total_prices]
            totals.sort()
            median_idx = len(totals) // 2
            ebay_estimate = totals[median_idx] if len(totals) % 2 == 1 else (totals[median_idx - 1] + totals[median_idx]) / 2
            condition_breakdown = "Mixed conditions"
        
        # Get sample prices for notes (total prices including shipping)
        # Note: market_value is NOT calculated from eBay searches - it should be set manually
        all_totals = [item["total"] for item in total_prices]
        all_totals.sort()
        sample_prices = all_totals[:5]  # First 5 lowest total prices
        
        # Build notes with edition matching info
        edition_info = ""
        if publisher and stock_number:
            edition_info = f"Filtered to {publisher} {stock_number} edition. "
        elif publisher:
            edition_info = f"Filtered to {publisher} publisher. "
        elif stock_number:
            edition_info = f"Filtered to stock number {stock_number}. "
        
        # Calculate average shipping for context
        shipping_values = []
        for item in buy_it_now_results:
            shipping = item.get("shipping_cost")
            if shipping is not None:
                try:
                    shipping_values.append(float(shipping))
                except (ValueError, TypeError):
                    pass
        avg_shipping = sum(shipping_values) / len(shipping_values) if shipping_values else 0.0
        
        # Add ChatGPT info to notes if used
        filter_method = "ChatGPT" if self.openai_client and (publisher or stock_number) else "fuzzy matching"
        if publisher or stock_number:
            edition_info += f"Filtered using {filter_method}. "
        
        price_info = {
            "source": "eBay API (Buy It Now listings, current prices)",
            "date": date.today(),
            "notes": f"{edition_info}Based on {len(buy_it_now_results)} current Buy It Now listings (prices include shipping). Sample total prices: ${sample_prices[0]:.2f} - ${sample_prices[-1]:.2f}. Conditions: {condition_breakdown}. Avg shipping: ${avg_shipping:.2f}",
            "sample_prices": sample_prices,
            "total_listings": len(buy_it_now_results),
            "condition_breakdown": condition_breakdown,
            "edition_filtered": bool(publisher or stock_number),
            "filter_method": filter_method if (publisher or stock_number) else None,
            "includes_shipping": True
        }
        
        return (ebay_estimate, price_info)


def get_price_for_book(
    book_id: int,
    app_id: str,
    cert_id: str,
    dev_id: str,
    sandbox: bool = True,
    db_path: str = 'book_catalog.db',
    openai_api_key: Optional[str] = None
) -> Optional[Dict]:
    """
    Get price estimates for a book and update the database.
    
    Args:
        book_id: Book ID in database
        app_id: eBay App ID
        cert_id: eBay Cert ID
        dev_id: eBay Dev ID
        sandbox: Whether to use Sandbox (True) or Production (False)
        db_path: Path to database
    
    Returns:
        Dictionary with price information or None if failed
    """
    from .book_manager import get_book_by_id, update_book
    
    # Get book from database
    book = get_book_by_id(book_id, db_path)
    if not book:
        return None
    
    # Initialize eBay API
    api = eBayAPI(app_id, cert_id, dev_id, sandbox, openai_api_key=openai_api_key)
    
    # Get publication year if available
    publication_year = None
    if book.publication_date:
        # Handle both date objects and string dates (including ranges)
        if isinstance(book.publication_date, str):
            # Try to extract year from string (could be "1940/41", "Aug 1951", "1951", etc.)
            import re
            year_match = re.search(r'\b(19|20)\d{2}\b', book.publication_date)
            if year_match:
                publication_year = int(year_match.group())
        else:
            # It's a date object
            publication_year = book.publication_date.year
    
    # Get price estimate
    result = api.get_price_estimate(
        title=book.title,
        author=book.author,
        publisher=book.publisher,
        stock_number=book.stock_number,
        grade=book.grade,
        publication_year=publication_year
    )
    
    if not result:
        return {"error": "Insufficient data for price estimate"}
    
    # Check if result is an error dict
    if isinstance(result, dict) and "error" in result:
        return result
    
    ebay_estimate, price_info = result
    
    # Update book in database (only ebay_estimate, NOT market_value)
    update_book(
        book_id,
        ebay_estimate=ebay_estimate,
        price_date=price_info["date"],
        price_source=price_info["source"],
        price_notes=price_info["notes"],
        db_path=db_path
    )
    
    return {
        "ebay_estimate": ebay_estimate,
        "price_info": price_info
    }

