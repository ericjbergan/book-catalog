"""Thin HTTP + OAuth wrapper around the eBay Browse API.

Returns raw response dicts. Interpretation lives in parse.py.
"""

import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests


class EbayClient:
    """OAuth token cache + raw search/item calls against the Browse API."""

    SANDBOX_TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    SANDBOX_BROWSE_URL = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
    SANDBOX_ITEM_URL = "https://api.sandbox.ebay.com/buy/browse/v1/item/"

    PRODUCTION_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    PRODUCTION_BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    PRODUCTION_ITEM_URL = "https://api.ebay.com/buy/browse/v1/item/"

    def __init__(self, app_id: str, cert_id: str, dev_id: str, sandbox: bool = True):
        self.app_id = app_id
        self.cert_id = cert_id
        self.dev_id = dev_id
        self.sandbox = sandbox

        self.token_url = self.SANDBOX_TOKEN_URL if sandbox else self.PRODUCTION_TOKEN_URL
        self.browse_url = self.SANDBOX_BROWSE_URL if sandbox else self.PRODUCTION_BROWSE_URL
        self.item_url = self.SANDBOX_ITEM_URL if sandbox else self.PRODUCTION_ITEM_URL

        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    def _get_access_token(self) -> str:
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token

        credentials = f"{self.app_id}:{self.cert_id}"
        encoded = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded}",
        }
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        }

        try:
            response = requests.post(self.token_url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 7200)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 200)
            return self.access_token
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get eBay access token: {e}")

    def search_raw(self, query: str, limit: int = 20) -> List[Dict]:
        """Run a Buy-It-Now Books-category search. Returns raw itemSummaries."""
        token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        }
        params = {
            "q": query,
            "limit": min(limit, 200),
            "category_ids": "267",
            "sort": "price",
            "filter": "deliveryCountry:US,buyingOptions:{FIXED_PRICE}",
        }
        try:
            response = requests.get(self.browse_url, headers=headers, params=params)
            response.raise_for_status()
            return response.json().get("itemSummaries", [])
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to search eBay: {e}")

    def get_item_raw(self, item_id: str) -> Optional[Dict]:
        """Fetch full item details. Returns None on failure."""
        try:
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            }
            response = requests.get(f"{self.item_url}{item_id}", headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return None
