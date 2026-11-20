"""Unified CLI: `python -m book_catalog <serve|search|price|import>`.

Replaces the historical run_ui.py / search_ebay.py / fetch_book_price.py /
example_usage.py scripts. All commands read credentials from the .env file at
the repo root via python-dotenv.
"""

import argparse
import os
import sys

from dotenv import load_dotenv


def _load_env() -> None:
    """Populate os.environ from .env at the repo root."""
    load_dotenv()


def _ebay_credentials(sandbox: bool):
    """Return (app_id, cert_id, dev_id) for the requested environment."""
    prefix = "EBAY_SANDBOX" if sandbox else "EBAY_PRODUCTION"
    app_id = os.getenv(f"{prefix}_APP_ID")
    cert_id = os.getenv(f"{prefix}_CERT_ID")
    dev_id = os.getenv(f"{prefix}_DEV_ID")
    if not (app_id and cert_id and dev_id):
        env = "sandbox" if sandbox else "production"
        sys.exit(f"Missing {env} eBay credentials in .env (need {prefix}_APP_ID/_CERT_ID/_DEV_ID)")
    return app_id, cert_id, dev_id


# --- serve ------------------------------------------------------------------

def cmd_serve(args: argparse.Namespace) -> None:
    """Start the Flask web UI."""
    from app import app  # imported lazily so `python -m book_catalog --help` is fast
    print(f"Book Catalog UI -> http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    # debug=False intentionally: Werkzeug's debugger console is an RCE vector.
    # The reloader is separate and safe: it restarts on Python file changes.
    app.run(host=args.host, port=args.port, debug=False, use_reloader=True)


# --- search -----------------------------------------------------------------

def cmd_search(args: argparse.Namespace) -> None:
    """Search eBay by title/author/publisher/stock #, print raw listings."""
    from book_catalog.ebay_api import eBayAPI

    app_id, cert_id, dev_id = _ebay_credentials(args.sandbox)
    api = eBayAPI(app_id=app_id, cert_id=cert_id, dev_id=dev_id, sandbox=args.sandbox)

    env = "Sandbox" if args.sandbox else "Production"
    print(f"Searching eBay ({env}) for: {args.title}")
    if args.author:
        print(f"  Author: {args.author}")
    if args.publisher:
        print(f"  Publisher: {args.publisher}")
    if args.stock_number:
        print(f"  Stock Number: {args.stock_number}")
    print()

    try:
        results = api.search_books(
            title=args.title, author=args.author,
            publisher=args.publisher, stock_number=args.stock_number,
            limit=args.limit,
        )
    except Exception as e:
        sys.exit(f"eBay search failed: {e}")

    if not results:
        print("No results found on eBay.")
        if args.sandbox:
            print("(Sandbox has very limited test data — try --production or omit --sandbox.)")
        return

    print(f"Found {len(results)} listings:\n")
    prices = []
    for i, item in enumerate(results, 1):
        price = item.get("price")
        try:
            price_str = f"${float(price):.2f}" if price is not None else "Price not available"
            if price is not None:
                prices.append(float(price))
        except (ValueError, TypeError):
            price_str = str(price)
        currency = item.get("currency", "USD")
        condition = item.get("condition", "Unknown")
        shipping = item.get("shipping_cost")
        print(f"{i}. {item['title']}")
        print(f"   Price: {price_str} {currency}")
        print(f"   Condition: {condition}")
        if shipping is not None:
            try:
                print(f"   Shipping: ${float(shipping):.2f}")
            except (ValueError, TypeError):
                print(f"   Shipping: {shipping}")
        if item.get("url"):
            print(f"   URL: {item['url']}")
        print()

    if prices:
        prices.sort()
        median = (prices[len(prices) // 2 - 1] + prices[len(prices) // 2]) / 2 if len(prices) % 2 == 0 else prices[len(prices) // 2]
        print("Price Statistics:")
        print(f"  Lowest:  ${prices[0]:.2f}")
        print(f"  Highest: ${prices[-1]:.2f}")
        print(f"  Average: ${sum(prices) / len(prices):.2f}")
        print(f"  Median:  ${median:.2f}")


# --- price ------------------------------------------------------------------

def cmd_price(args: argparse.Namespace) -> None:
    """Fetch an eBay-based price estimate for a book by ID and persist it."""
    from book_catalog.ebay_api import get_price_for_book

    app_id, cert_id, dev_id = _ebay_credentials(args.sandbox)
    env = "Sandbox" if args.sandbox else "Production"
    print(f"Fetching price for book ID {args.book_id} ({env})...")

    try:
        result = get_price_for_book(
            book_id=args.book_id,
            app_id=app_id, cert_id=cert_id, dev_id=dev_id,
            sandbox=args.sandbox,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )
    except Exception as e:
        sys.exit(f"Error: {e}")

    if not result:
        sys.exit("Book not found.")
    if "error" in result:
        sys.exit(f"Error: {result['error']}")

    print("\neBay estimate updated:")
    print(f"  eBay Estimate: ${result['ebay_estimate']:.2f}")
    print(f"  Source: {result['price_info']['source']}")
    print(f"  Date:   {result['price_info']['date']}")
    print(f"  Notes:  {result['price_info']['notes']}")


# --- import -----------------------------------------------------------------

def cmd_import(args: argparse.Namespace) -> None:
    """Import books from a CSV file into the catalog."""
    from book_catalog.import_utils import import_from_csv
    added, failed = import_from_csv(args.csv_path, db_path=args.db, encoding=args.encoding)
    print(f"\nImported {added} books; {failed} failed.")


# --- argparse plumbing ------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m book_catalog",
        description="Book Catalog CLI: run the web UI, query eBay, price a book, or import a CSV.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="Start the Flask web UI")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=5000)
    p_serve.set_defaults(func=cmd_serve)

    p_search = sub.add_parser("search", help="Search eBay and print listings")
    p_search.add_argument("title")
    p_search.add_argument("author", nargs="?", default=None)
    p_search.add_argument("publisher", nargs="?", default=None)
    p_search.add_argument("stock_number", nargs="?", default=None)
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--sandbox", action="store_true", help="Use eBay Sandbox instead of Production")
    p_search.set_defaults(func=cmd_search)

    p_price = sub.add_parser("price", help="Fetch and persist an eBay price estimate for a book")
    p_price.add_argument("book_id", type=int)
    p_price.add_argument("--sandbox", action="store_true")
    p_price.set_defaults(func=cmd_price)

    p_import = sub.add_parser("import", help="Import books from a CSV file")
    p_import.add_argument("csv_path")
    p_import.add_argument("--db", default="book_catalog.db")
    p_import.add_argument("--encoding", default="utf-8")
    p_import.set_defaults(func=cmd_import)

    return parser


def main(argv=None) -> None:
    _load_env()
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
