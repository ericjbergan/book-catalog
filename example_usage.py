"""Example usage of the book catalog."""

from book_catalog.database import init_database
from book_catalog.book_manager import add_book, search_books, list_all_books
from datetime import date

# Initialize database
print("Initializing database...")
init_database()

# Add the example book
print("\nAdding example book...")
add_book(
    author="ERB",
    title="At the Earth's Core",
    publisher="Ace",
    stock_number="F-156",
    price="40c",
    publisher_address="23 West 47th St, New York",
    cover_artist="Frazetta",
    logo_description="lowercase 'a' with ace across the middle",
    owned=True,
    printing="First",
    printing_notes="Frazetta cover, no number line, 23 West 47th St address, no copyright info found"
)

# Search for books
print("\nSearching for ERB books...")
erb_books = search_books(author="ERB")
for book in erb_books:
    print(f"  - {book.author}: {book.title} ({book.publisher} {book.stock_number})")

# List all books
print("\nAll books in catalog:")
all_books = list_all_books()
for book in all_books:
    print(f"  [{book.id}] {book.author}: {book.title} - Owned: {book.owned}")

