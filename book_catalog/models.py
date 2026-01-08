"""Database models for book cataloging."""

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import date

Base = declarative_base()


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
    market_value = Column(Float)  # Best guess at current market value in USD (optimistic estimate)
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
        return f"<Book(id={self.id}, author='{self.author}', title='{self.title}', " \
               f"publisher='{self.publisher}', stock_number='{self.stock_number}', owned={self.owned})>"


def get_db_session(db_path='book_catalog.db'):
    """Create and return a database session."""
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def init_database(db_path='book_catalog.db'):
    """Initialize the database with tables."""
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)
    print(f"Database initialized at {db_path}")

