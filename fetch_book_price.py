"""
Script to fetch eBay prices for a book.

Usage:
    python fetch_book_price.py <book_id>
    
Example:
    python fetch_book_price.py 1
"""

import sys
from book_catalog.ebay_api import get_price_for_book
from ebay_credentials import (
    EBAY_PRODUCTION_APP_ID, EBAY_PRODUCTION_CERT_ID, EBAY_PRODUCTION_DEV_ID,
    EBAY_SANDBOX_APP_ID, EBAY_SANDBOX_CERT_ID, EBAY_SANDBOX_DEV_ID
)

# Try to import OpenAI credentials (optional)
try:
    from openai_credentials import OPENAI_API_KEY
except ImportError:
    OPENAI_API_KEY = None


def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_book_price.py <book_id>")
        sys.exit(1)
    
    try:
        book_id = int(sys.argv[1])
    except ValueError:
        print("Error: book_id must be a number")
        sys.exit(1)
    
    # Use Production by default, Sandbox if --sandbox flag is used
    use_sandbox = '--sandbox' in sys.argv
    if use_sandbox:
        app_id = EBAY_SANDBOX_APP_ID
        cert_id = EBAY_SANDBOX_CERT_ID
        dev_id = EBAY_SANDBOX_DEV_ID
        env = "Sandbox"
    else:
        app_id = EBAY_PRODUCTION_APP_ID
        cert_id = EBAY_PRODUCTION_CERT_ID
        dev_id = EBAY_PRODUCTION_DEV_ID
        env = "Production"
    
    print(f"Fetching price for book ID {book_id} (using {env} environment)...")
    
    try:
        result = get_price_for_book(
            book_id=book_id,
            app_id=app_id,
            cert_id=cert_id,
            dev_id=dev_id,
            sandbox=use_sandbox,
            openai_api_key=OPENAI_API_KEY
        )
        
        if result and "error" not in result:
            print(f"\neBay estimate updated:")
            print(f"  eBay Estimate: ${result['ebay_estimate']:.2f}")
            print(f"  Source: {result['price_info']['source']}")
            print(f"  Date: {result['price_info']['date']}")
            print(f"  Notes: {result['price_info']['notes']}")
            print(f"\nNote: Market value is not updated from eBay searches - set it manually if needed.")
        else:
            error_msg = result.get("error", "Unknown error") if result else "No result returned"
            print(f"\nError: {error_msg}")
            print("This might be due to:")
            print("  - Insufficient listings on eBay")
            print("  - API authentication issues")
            print("  - Network connectivity problems")
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

