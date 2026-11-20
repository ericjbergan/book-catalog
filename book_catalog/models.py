"""Database models for book cataloging."""

import dataclasses
from datetime import date as _date
from typing import Any, Optional

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, Date
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base."""


_session_factories = {}  # Cache session factories by db_path


# Columns not exposed by BookRow.to_dict — internal-only fields that don't need
# to travel to the UI (bulky JSON blobs, rarely-used identification metadata).
UI_HIDDEN_COLUMNS = frozenset({
    "copyright_date", "copyright_text", "printing_number",
    "logo_description", "cover_description",
    "spine_info", "back_cover_info",
    "ebay_search_results", "ebay_search_date",
})


class Book(Base):
    """Model for cataloging books with printing and grade information."""

    __tablename__ = 'books'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Basic identification
    author = Column(String(200), nullable=False, index=True)
    title = Column(String(300), nullable=False, index=True)
    series = Column(String(100), index=True)  # e.g., "Tarzan", "Barsoom", etc.
    publisher = Column(String(100), index=True)  # e.g., "Ace", "Ballantine", etc.
    stock_number = Column(String(50), index=True)  # e.g., "F-156"
    isbn = Column(String(20), index=True)

    # Printing identification
    price = Column(String(20))  # e.g., "40c", "$0.40", "$1.25"
    publisher_address = Column(String(200))  # e.g., "23 West 47th St, New York"
    number_line = Column(String(100))  # e.g., "1 2 3 4 5" or "First printing"
    copyright_date = Column(Date)
    copyright_text = Column(Text)  # Full copyright text if available

    # Cover and design
    cover_artist = Column(String(100))  # e.g., "Frazetta"
    cover_art_url = Column(String(500))  # URL to cover art image
    logo_description = Column(Text)  # Description of publisher logo
    cover_description = Column(Text)  # Description of cover design/colors

    # Printing determination
    printing = Column(String(50))  # e.g., "First", "Second", "Unknown"
    printing_number = Column(Integer)  # Numeric printing number (1, 2, 3, etc.)
    printing_notes = Column(Text)  # Notes on how printing was determined
    publication_date = Column(String(50))  # Can store date ranges like "1940/41" or "Aug 1951"

    # Medium/Format
    medium = Column(String(20), index=True)  # e.g., "Paperback", "Magazine", "Hardcover"

    # Condition and grade
    grade = Column(String(20))  # e.g., "Fine", "Very Good", "Good", "Fair"
    condition_notes = Column(Text)  # Detailed condition description

    # Collection status
    owned = Column(Boolean, default=True, index=True)

    # Price tracking
    ebay_estimate = Column(Float)  # eBay-based estimate from Buy It Now listings, considering condition/grade
    purchase_price = Column(Float)  # Price paid when acquired (if known)
    price_date = Column(Date)  # Date when price was estimated/recorded
    price_source = Column(String(200))  # Source of price estimate (e.g., "AbeBooks", "eBay sold listings")
    price_notes = Column(Text)  # Notes about pricing (e.g., "Based on Fine condition listings")

    # Additional information
    notes = Column(Text)  # General notes
    spine_info = Column(Text)  # Information from spine
    back_cover_info = Column(Text)  # Information from back cover
    ebay_search_results = Column(Text)  # JSON string of most recent eBay search results
    ebay_search_date = Column(Date)  # Date of most recent eBay search

    def __repr__(self):
        return (f"<Book(id={self.id}, author='{self.author}', title='{self.title}', "
                f"publisher='{self.publisher}', stock_number='{self.stock_number}', "
                f"owned={self.owned})>")


# --- BookRow: session-independent row shape --------------------------------
#
# Callers should never receive a detached ORM Book instance. book_manager
# hydrates a BookRow inside the session and returns that; it has the same
# attribute-access surface (`row.title`, `row.grade`, …) but doesn't rely
# on a live session, and serializes to a UI-friendly dict via to_dict().
#
# Fields are generated from Book.__table__.columns so adding a column to
# Book automatically flows through BookRow, book_manager, and the API
# allowlist — one source of truth.

BOOK_COLUMN_NAMES = tuple(col.name for col in Book.__table__.columns)


def _column_python_type(column) -> type:
    try:
        return column.type.python_type
    except (AttributeError, NotImplementedError):
        return str


BookRow = dataclasses.make_dataclass(
    "BookRow",
    [(name, Optional[Any], dataclasses.field(default=None)) for name in BOOK_COLUMN_NAMES],
)


def _serialize_column(value, column) -> Any:
    """UI-friendly serialization: empty string for missing text, str for dates,
    float for numerics, native for the rest."""
    pytype = _column_python_type(column)
    if value is None:
        return "" if pytype is str else None
    if isinstance(value, _date):
        return str(value)
    if pytype is float:
        return float(value)
    if pytype is bool:
        return bool(value)
    if pytype is int:
        return int(value)
    return value


def _row_to_dict(row, *, include_hidden: bool = False) -> dict:
    """Serialize a BookRow (or Book) into the UI dict shape."""
    out = {}
    for col in Book.__table__.columns:
        if not include_hidden and col.name in UI_HIDDEN_COLUMNS:
            continue
        out[col.name] = _serialize_column(getattr(row, col.name), col)
    return out


# Attach to_dict as a bound method on BookRow for ergonomics.
BookRow.to_dict = lambda self, include_hidden=False: _row_to_dict(self, include_hidden=include_hidden)


def hydrate_row(book: "Book") -> "BookRow":
    """Copy a live ORM Book into a session-independent BookRow."""
    return BookRow(**{name: getattr(book, name) for name in BOOK_COLUMN_NAMES})


def get_db_session(db_path='book_catalog.db'):
    """Create and return a database session, reusing the engine across calls."""
    if db_path not in _session_factories:
        engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Base.metadata.create_all(engine)
        _session_factories[db_path] = sessionmaker(bind=engine)
    return _session_factories[db_path]()


def init_database(db_path='book_catalog.db'):
    """Initialize the database with tables."""
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)
    print(f"Database initialized at {db_path}")

