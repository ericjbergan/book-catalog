"""Book management utilities for adding, querying, and updating books.

Reads return `BookRow` dataclass instances (hydrated inside the session),
never detached ORM objects. That way callers can safely hold onto the
result after the session closes.
"""

from sqlalchemy import select

from .models import BOOK_COLUMN_NAMES, Book, BookRow, get_db_session, hydrate_row


# Fields update_book / add_book accept — everything on Book except the primary
# key. Derived from Book.__table__.columns so a new column flows through
# automatically; the API allowlist in app.py imports this list.
MUTABLE_COLUMN_NAMES = tuple(name for name in BOOK_COLUMN_NAMES if name != "id")


def add_book(*, db_path='book_catalog.db', **fields) -> BookRow:
    """Add a new book. Keyword-only; any subset of MUTABLE_COLUMN_NAMES."""
    author = fields.get('author')
    title = fields.get('title')
    if not author or not title:
        raise ValueError("author and title are required")

    unknown = set(fields) - set(MUTABLE_COLUMN_NAMES)
    if unknown:
        raise ValueError(f"Unknown book fields: {sorted(unknown)}")

    session = get_db_session(db_path)
    try:
        book = Book(**fields)
        session.add(book)
        session.commit()
        row = hydrate_row(book)
        print(f"Added book: {author} - {title} (ID: {row.id})")
        return row
    except Exception as e:
        session.rollback()
        print(f"Error adding book: {e}")
        raise
    finally:
        session.close()


def get_book_by_id(book_id, db_path='book_catalog.db'):
    """Get a book by its ID as a BookRow, or None if not found."""
    session = get_db_session(db_path)
    try:
        book = session.scalars(select(Book).where(Book.id == book_id)).first()
        return hydrate_row(book) if book else None
    finally:
        session.close()


def search_books(
    author=None,
    title=None,
    publisher=None,
    stock_number=None,
    owned=None,
    db_path='book_catalog.db'
):
    """Search for books by various criteria; returns a list of BookRow."""
    session = get_db_session(db_path)
    try:
        stmt = select(Book)
        if author:
            stmt = stmt.where(Book.author.ilike(f'%{author}%'))
        if title:
            stmt = stmt.where(Book.title.ilike(f'%{title}%'))
        if publisher:
            stmt = stmt.where(Book.publisher.ilike(f'%{publisher}%'))
        if stock_number:
            stmt = stmt.where(Book.stock_number.ilike(f'%{stock_number}%'))
        if owned is not None:
            stmt = stmt.where(Book.owned == owned)
        return [hydrate_row(b) for b in session.scalars(stmt).all()]
    finally:
        session.close()


def list_all_books(db_path='book_catalog.db'):
    """List all books; returns a list of BookRow sorted by author/series/title."""
    session = get_db_session(db_path)
    try:
        # Series sorting by number is handled in the frontend for better parsing.
        stmt = select(Book).order_by(Book.author, Book.series, Book.title)
        return [hydrate_row(b) for b in session.scalars(stmt).all()]
    finally:
        session.close()


def update_book(book_id, db_path='book_catalog.db', **kwargs) -> bool:
    """Update a book's fields. Returns True on success, False if not found."""
    unknown = set(kwargs) - set(MUTABLE_COLUMN_NAMES)
    if unknown:
        raise ValueError(f"Unknown book fields: {sorted(unknown)}")

    session = get_db_session(db_path)
    try:
        book = session.scalars(select(Book).where(Book.id == book_id)).first()
        if not book:
            print(f"Book with ID {book_id} not found")
            return False

        for key, value in kwargs.items():
            setattr(book, key, value)

        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error updating book: {e}")
        raise
    finally:
        session.close()


def delete_book(book_id, db_path='book_catalog.db') -> bool:
    """Delete a book by ID. Returns True on success, False if not found."""
    session = get_db_session(db_path)
    try:
        book = session.scalars(select(Book).where(Book.id == book_id)).first()
        if not book:
            print(f"Book with ID {book_id} not found")
            return False

        session.delete(book)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error deleting book: {e}")
        raise
    finally:
        session.close()
