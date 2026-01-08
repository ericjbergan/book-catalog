"""Book management utilities for adding, querying, and updating books."""

from .models import Book, get_db_session
from datetime import datetime


def add_book(
    author,
    title,
    series=None,
    publisher=None,
    stock_number=None,
    isbn=None,
    price=None,
    publisher_address=None,
    number_line=None,
    copyright_date=None,
    copyright_text=None,
    cover_artist=None,
    cover_art_url=None,
    logo_description=None,
    cover_description=None,
    printing=None,
    printing_number=None,
    printing_notes=None,
    publication_date=None,
    grade=None,
    condition_notes=None,
    owned=True,
    notes=None,
    spine_info=None,
    back_cover_info=None,
    market_value=None,
    ebay_estimate=None,
    purchase_price=None,
    price_date=None,
    price_source=None,
    price_notes=None,
    medium=None,
    db_path='book_catalog.db'
):
    """Add a new book to the catalog."""
    session = get_db_session(db_path)
    
    try:
        book = Book(
            author=author,
            title=title,
            series=series,
            publisher=publisher,
            stock_number=stock_number,
            isbn=isbn,
            price=price,
            publisher_address=publisher_address,
            number_line=number_line,
            copyright_date=copyright_date,
            copyright_text=copyright_text,
            cover_artist=cover_artist,
            cover_art_url=cover_art_url,
            logo_description=logo_description,
            cover_description=cover_description,
            printing=printing,
            printing_number=printing_number,
            printing_notes=printing_notes,
            publication_date=publication_date,
            grade=grade,
            condition_notes=condition_notes,
            owned=owned,
            notes=notes,
            spine_info=spine_info,
            back_cover_info=back_cover_info,
            market_value=market_value,
            ebay_estimate=ebay_estimate,
            purchase_price=purchase_price,
            price_date=price_date,
            price_source=price_source,
            price_notes=price_notes,
            medium=medium
        )
        
        session.add(book)
        session.commit()
        print(f"Added book: {author} - {title} (ID: {book.id})")
        return book
    except Exception as e:
        session.rollback()
        print(f"Error adding book: {e}")
        raise
    finally:
        session.close()


def get_book_by_id(book_id, db_path='book_catalog.db'):
    """Get a book by its ID."""
    session = get_db_session(db_path)
    try:
        return session.query(Book).filter(Book.id == book_id).first()
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
    """Search for books by various criteria."""
    session = get_db_session(db_path)
    try:
        query = session.query(Book)
        
        if author:
            query = query.filter(Book.author.ilike(f'%{author}%'))
        if title:
            query = query.filter(Book.title.ilike(f'%{title}%'))
        if publisher:
            query = query.filter(Book.publisher.ilike(f'%{publisher}%'))
        if stock_number:
            query = query.filter(Book.stock_number.ilike(f'%{stock_number}%'))
        if owned is not None:
            query = query.filter(Book.owned == owned)
        
        return query.all()
    finally:
        session.close()


def list_all_books(db_path='book_catalog.db'):
    """List all books in the catalog."""
    session = get_db_session(db_path)
    try:
        # Sort by author, then series, then title
        # Note: Series sorting by number is handled in frontend for better parsing
        return session.query(Book).order_by(Book.author, Book.series, Book.title).all()
    finally:
        session.close()


def update_book(book_id, db_path='book_catalog.db', **kwargs):
    """Update a book's information."""
    session = get_db_session(db_path)
    try:
        book = session.query(Book).filter(Book.id == book_id).first()
        if not book:
            print(f"Book with ID {book_id} not found")
            return None
        
        for key, value in kwargs.items():
            if hasattr(book, key):
                setattr(book, key, value)
        
        session.commit()
        print(f"Updated book ID {book_id}")
        return book
    except Exception as e:
        session.rollback()
        print(f"Error updating book: {e}")
        raise
    finally:
        session.close()


def delete_book(book_id, db_path='book_catalog.db'):
    """Delete a book from the catalog."""
    session = get_db_session(db_path)
    try:
        book = session.query(Book).filter(Book.id == book_id).first()
        if not book:
            print(f"Book with ID {book_id} not found")
            return False
        
        session.delete(book)
        session.commit()
        print(f"Deleted book ID {book_id}")
        return True
    except Exception as e:
        session.rollback()
        print(f"Error deleting book: {e}")
        raise
    finally:
        session.close()

