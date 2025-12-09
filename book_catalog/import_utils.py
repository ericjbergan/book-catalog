"""Utilities for importing book data from tables/spreadsheets."""

import csv
from datetime import datetime
from .book_manager import add_book


def parse_date(date_str):
    """Parse a date string into a date object or return as string for ranges."""
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # If it contains a slash, it's likely a date range (e.g., "1940/41", "1951/52")
    # Return as string to preserve the range
    if '/' in date_str and not date_str.count('/') == 2:  # Not a full date like "12/25/1951"
        return date_str
    
    # Try common date formats
    formats = ['%Y-%m-%d', '%m/%d/%Y', '%Y', '%m/%d/%y', '%d/%m/%Y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    # If just a year, create date for Jan 1 of that year
    try:
        year = int(date_str)
        return datetime(year, 1, 1).date()
    except ValueError:
        pass
    
    # If we can't parse it, return as string (might be a range or other format)
    return date_str


def import_from_csv(csv_path, db_path='book_catalog.db', encoding='utf-8'):
    """Import books from a CSV file.
    
    Expected CSV columns (case-insensitive):
    - author, title, series, publisher, stock_number, isbn, price, publisher_address,
    - number_line, copyright_date, copyright_text, cover_artist, cover_art_url, logo_description,
    - cover_description, printing, printing_number, printing_notes, publication_date, grade,
    - condition_notes, owned, notes, spine_info, back_cover_info,
    - market_value, ebay_estimate, purchase_price, price_date, price_source, price_notes
    """
    books_added = 0
    books_failed = 0
    
    try:
        with open(csv_path, 'r', encoding=encoding) as f:
            # Try to detect delimiter
            sample = f.read(1024)
            f.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.DictReader(f, delimiter=delimiter)
            
            # Normalize column names (case-insensitive, strip whitespace)
            fieldnames = {name.strip().lower(): name for name in reader.fieldnames}
            
            for row in reader:
                try:
                    # Extract and normalize data
                    data = {}
                    for key, value in row.items():
                        normalized_key = key.strip().lower()
                        if normalized_key in fieldnames:
                            data[normalized_key] = value.strip() if value else None
                    
                    # Map to function parameters
                    book_data = {
                        'author': data.get('author', '').strip(),
                        'title': data.get('title', '').strip(),
                        'series': data.get('series'),
                        'publisher': data.get('publisher'),
                        'stock_number': data.get('stock_number'),
                        'isbn': data.get('isbn'),
                        'price': data.get('price'),
                        'publisher_address': data.get('publisher_address'),
                        'number_line': data.get('number_line'),
                        'copyright_date': parse_date(data.get('copyright_date')),
                        'copyright_text': data.get('copyright_text'),
                        'cover_artist': data.get('cover_artist'),
                        'cover_art_url': data.get('cover_art_url'),
                        'logo_description': data.get('logo_description'),
                        'cover_description': data.get('cover_description'),
                        'printing': data.get('printing'),
                        'printing_number': int(data.get('printing_number')) if data.get('printing_number') and data.get('printing_number').strip().isdigit() else None,
                        'printing_notes': data.get('printing_notes'),
                        'publication_date': parse_date(data.get('publication_date')),  # Can be date object or string for ranges
                        'grade': data.get('grade'),
                        'condition_notes': data.get('condition_notes'),
                        'owned': data.get('owned', 'true').lower() in ('true', '1', 'yes', 'y', 'owned'),
                        'notes': data.get('notes'),
                        'spine_info': data.get('spine_info'),
                        'back_cover_info': data.get('back_cover_info'),
                        'market_value': float(data.get('market_value')) if data.get('market_value') and data.get('market_value').strip() else None,
                        'ebay_estimate': float(data.get('ebay_estimate')) if data.get('ebay_estimate') and data.get('ebay_estimate').strip() else None,
                        'purchase_price': float(data.get('purchase_price')) if data.get('purchase_price') and data.get('purchase_price').strip() else None,
                        'price_date': parse_date(data.get('price_date')),
                        'price_source': data.get('price_source'),
                        'price_notes': data.get('price_notes'),
                        'db_path': db_path
                    }
                    
                    if not book_data['author'] or not book_data['title']:
                        print(f"Skipping row: missing author or title")
                        books_failed += 1
                        continue
                    
                    add_book(**book_data)
                    books_added += 1
                    
                except Exception as e:
                    print(f"Error importing row: {e}")
                    print(f"Row data: {row}")
                    books_failed += 1
                    continue
        
        print(f"\nImport complete: {books_added} books added, {books_failed} failed")
        return books_added, books_failed
        
    except FileNotFoundError:
        print(f"Error: File '{csv_path}' not found")
        return 0, 0
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return 0, 0

