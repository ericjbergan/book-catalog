"""
Script to search for books on eBay.

Usage:
    python search_ebay.py "book title" [author] [publisher] [stock_number]
    
Examples:
    python search_ebay.py "Tarzan of the Apes"
    python search_ebay.py "Tarzan of the Apes" "Edgar Rice Burroughs"
    python search_ebay.py "Tarzan of the Apes" "ERB" "Ace" "F-156"
"""

import sys
from book_catalog.ebay_api import eBayAPI
from ebay_credentials import (
    EBAY_PRODUCTION_APP_ID, EBAY_PRODUCTION_CERT_ID, EBAY_PRODUCTION_DEV_ID,
    EBAY_SANDBOX_APP_ID, EBAY_SANDBOX_CERT_ID, EBAY_SANDBOX_DEV_ID
)
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: python search_ebay.py \"book title\" [author] [publisher] [stock_number]")
        print("\nExamples:")
        print('  python search_ebay.py "Tarzan of the Apes"')
        print('  python search_ebay.py "Tarzan of the Apes" "Edgar Rice Burroughs"')
        print('  python search_ebay.py "Tarzan of the Apes" "ERB" "Ace" "F-156"')
        sys.exit(1)
    
    title = sys.argv[1]
    author = sys.argv[2] if len(sys.argv) > 2 else None
    publisher = sys.argv[3] if len(sys.argv) > 3 else None
    stock_number = sys.argv[4] if len(sys.argv) > 4 else None
    
    print(f"Searching eBay for: {title}")
    if author:
        print(f"  Author: {author}")
    if publisher:
        print(f"  Publisher: {publisher}")
    if stock_number:
        print(f"  Stock Number: {stock_number}")
    print()
    
    try:
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
        
        print(f"Using {env} environment\n")
        
        # Initialize eBay API
        api = eBayAPI(
            app_id=app_id,
            cert_id=cert_id,
            dev_id=dev_id,
            sandbox=use_sandbox
        )
        
        # Search for books
        results = api.search_books(
            title=title,
            author=author,
            publisher=publisher,
            stock_number=stock_number,
            limit=20
        )
        
        if not results:
            print("No results found on eBay.")
            if use_sandbox:
                print("\nNote: Sandbox has limited test data.")
                print("Try without --sandbox flag to use Production environment.")
            return
        
        print(f"Found {len(results)} listings:\n")
        
        for i, item in enumerate(results, 1):
            price = item.get('price')
            if price is not None:
                try:
                    price_float = float(price)
                    price_str = f"${price_float:.2f}"
                except (ValueError, TypeError):
                    price_str = str(price)
            else:
                price_str = "Price not available"
            
            currency = item.get('currency', 'USD')
            condition = item.get('condition', 'Unknown')
            
            print(f"{i}. {item['title']}")
            print(f"   Price: {price_str} {currency}")
            print(f"   Condition: {condition}")
            
            shipping = item.get('shipping_cost')
            if shipping is not None:
                try:
                    shipping_float = float(shipping)
                    print(f"   Shipping: ${shipping_float:.2f}")
                except (ValueError, TypeError):
                    print(f"   Shipping: {shipping}")
            
            if item.get('url'):
                print(f"   URL: {item['url']}")
            print()
        
        # Show price statistics
        prices = []
        for r in results:
            price = r.get('price')
            if price is not None:
                try:
                    prices.append(float(price))
                except (ValueError, TypeError):
                    pass
        
        if prices:
            prices.sort()
            print(f"Price Statistics:")
            print(f"  Lowest: ${prices[0]:.2f}")
            print(f"  Highest: ${prices[-1]:.2f}")
            print(f"  Average: ${sum(prices) / len(prices):.2f}")
            median_idx = len(prices) // 2
            if len(prices) % 2 == 0:
                median = (prices[median_idx - 1] + prices[median_idx]) / 2
            else:
                median = prices[median_idx]
            print(f"  Median: ${median:.2f}")
    
    except Exception as e:
        print(f"Error: {e}")
        print("\nPossible issues:")
        print("  - API authentication failed")
        print("  - Network connectivity problems")
        print("  - Invalid credentials")
        print("  - Sandbox may have limited data")
        sys.exit(1)


if __name__ == "__main__":
    main()

