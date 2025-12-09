"""
Simple web UI for book catalog with filtering and eBay search.
"""

from flask import Flask, render_template, jsonify, request, Response, stream_with_context
import json
from book_catalog.book_manager import list_all_books, get_book_by_id
from book_catalog.ebay_api import eBayAPI
from ebay_credentials import EBAY_PRODUCTION_APP_ID, EBAY_PRODUCTION_CERT_ID, EBAY_PRODUCTION_DEV_ID
from datetime import date
import json

# Try to import OpenAI credentials (optional)
try:
    from openai_credentials import OPENAI_API_KEY
except ImportError:
    OPENAI_API_KEY = None

app = Flask(__name__)


@app.route('/')
def index():
    """Main page with book listing."""
    return render_template('index.html')


@app.route('/api/books')
def api_books():
    """API endpoint to get all books with optional filters."""
    try:
        books = list_all_books()
        
        # Convert SQLAlchemy objects to dictionaries
        books_data = []
        for book in books:
            book_dict = {
                'id': book.id,
                'author': book.author,
                'title': book.title,
                'series': book.series or '',
                'publisher': book.publisher or '',
                'stock_number': book.stock_number or '',
                'price': book.price or '',
                'grade': book.grade or '',
                'owned': book.owned,
                'market_value': float(book.market_value) if book.market_value else None,
                'ebay_estimate': float(book.ebay_estimate) if book.ebay_estimate else None,
                'price_date': str(book.price_date) if book.price_date else None,
                'price_source': book.price_source or '',
                'publication_date': str(book.publication_date) if book.publication_date else None,  # Can be date string or range like "1940/41"
                'cover_artist': book.cover_artist or '',
                'notes': book.notes or '',
                'condition_notes': book.condition_notes or '',
                'printing': book.printing or '',
                'printing_notes': book.printing_notes or '',
                'cover_art_url': book.cover_art_url or '',
                'purchase_price': float(book.purchase_price) if book.purchase_price else None,
                'isbn': book.isbn or '',
                'publisher_address': book.publisher_address or '',
                'number_line': book.number_line or ''
            }
            books_data.append(book_dict)
        
        # Apply filters
        author_filter = request.args.get('author')
        owned_filter = request.args.get('owned')
        
        if author_filter:
            books_data = [b for b in books_data if b['author'].lower() == author_filter.lower()]
        
        if owned_filter is not None:
            owned_bool = owned_filter.lower() == 'true'
            books_data = [b for b in books_data if b['owned'] == owned_bool]
        
        return jsonify(books_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/authors')
def api_authors():
    """API endpoint to get list of all authors."""
    try:
        books = list_all_books()
        authors = sorted(set(book.author for book in books if book.author))
        return jsonify(authors)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/books/<int:book_id>/toggle_owned', methods=['POST'])
def api_toggle_owned(book_id):
    """API endpoint to toggle owned status of a book."""
    try:
        from book_catalog.book_manager import get_book_by_id, update_book
        
        book = get_book_by_id(book_id)
        if not book:
            return jsonify({'error': 'Book not found'}), 404
        
        # Toggle owned status
        new_owned_status = not book.owned
        update_book(book_id, owned=new_owned_status)
        
        return jsonify({
            'success': True,
            'book_id': book_id,
            'owned': new_owned_status
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/books/<int:book_id>', methods=['PUT'])
def api_update_book(book_id):
    """API endpoint to update book information."""
    try:
        from book_catalog.book_manager import get_book_by_id, update_book
        
        book = get_book_by_id(book_id)
        if not book:
            return jsonify({'error': 'Book not found'}), 404
        
        # Get update data from request
        data = request.get_json()
        
        # Build update dictionary with only provided fields
        update_fields = {}
        allowed_fields = [
            'grade', 'condition_notes', 'purchase_price', 'notes', 
            'market_value', 'ebay_estimate', 'price', 'printing', 
            'printing_notes', 'cover_artist', 'cover_art_url', 
            'publication_date', 'series', 'stock_number', 'publisher',
            'title', 'author', 'isbn', 'publisher_address', 'number_line'
        ]
        
        for field in allowed_fields:
            if field in data:
                # Handle empty strings for optional fields
                if data[field] == '':
                    update_fields[field] = None
                else:
                    update_fields[field] = data[field]
        
        # Update the book
        update_book(book_id, **update_fields)
        
        return jsonify({
            'success': True,
            'book_id': book_id,
            'updated_fields': list(update_fields.keys())
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ebay_search/<int:book_id>')
def api_ebay_search(book_id):
    """API endpoint to search eBay for a specific book and optionally update estimate."""
    try:
        from book_catalog.book_manager import update_book
        from datetime import date
        
        book = get_book_by_id(book_id)
        if not book:
            return jsonify({'error': 'Book not found'}), 404
        
        # Initialize eBay API (with OpenAI key if available)
        api = eBayAPI(
            app_id=EBAY_PRODUCTION_APP_ID,
            cert_id=EBAY_PRODUCTION_CERT_ID,
            dev_id=EBAY_PRODUCTION_DEV_ID,
            sandbox=False,
            openai_api_key=OPENAI_API_KEY
        )
        
        # Search eBay (using only title and publisher to get more results)
        results = api.search_books(
            title=book.title,
            author=None,  # Don't include in search to widen results
            publisher=book.publisher,
            stock_number=None,  # Don't include in search to widen results
            limit=50  # Get more results for better estimate
        )
        
        # Filter results to match the exact edition
        # Use ChatGPT if available, otherwise use prioritize_results (fuzzy matching)
        if api.openai_client and (book.publisher or book.stock_number):
            # Filter Buy It Now listings using ChatGPT
            buy_it_now_results = [r for r in results if r.get("is_buy_it_now", False)]
            if buy_it_now_results:
                # Get publication year if available
                publication_year = None
                if book.publication_date:
                    # Handle both date objects and string dates (including ranges)
                    if isinstance(book.publication_date, str):
                        # Try to extract year from string (could be "1940/41", "Aug 1951", "1951", etc.)
                        import re
                        year_match = re.search(r'\b(19|20)\d{2}\b', book.publication_date)
                        if year_match:
                            publication_year = int(year_match.group())
                    else:
                        # It's a date object
                        publication_year = book.publication_date.year
                
                filtered_results = api._filter_listings_with_chatgpt(
                    buy_it_now_results,
                    book.title,
                    book.author,
                    book.publisher,
                    book.stock_number,
                    target_publication_year=publication_year,
                    require_condition_info=False  # For display, show all matches
                )
                # Combine filtered results with non-Buy It Now results for display
                other_results = [r for r in results if not r.get("is_buy_it_now", False)]
                results = filtered_results + other_results
        else:
            # Fall back to prioritize_results (fuzzy matching)
            if book.stock_number:
                results = api.prioritize_results(results, book.author, book.stock_number)
        
        # Fetch shipping costs from item details if missing from search results
        # Limit to top 10 results to avoid too many API calls
        for i, r in enumerate(results[:10]):
            if (r.get("shipping_cost") == 0.0 or r.get("shipping_cost") is None) and r.get("item_id"):
                try:
                    details = api.get_item_details(r.get("item_id"))
                    fetched_shipping = details.get("shipping_cost")
                    if fetched_shipping is not None and fetched_shipping > 0.0:
                        r["shipping_cost"] = fetched_shipping
                except Exception:
                    # If fetching fails, keep the existing value
                    pass
        
        # Format results for display
        formatted_results = []
        for r in results:
            formatted_results.append({
                'title': r.get('title', ''),
                'price': f"${r.get('price', 0):.2f}" if r.get('price') else 'N/A',
                'shipping': f"${float(r.get('shipping_cost', 0)):.2f}" if r.get('shipping_cost') else 'Free',
                'condition': r.get('condition', 'Unknown'),
                'url': r.get('url', ''),
                'total': f"${(float(r.get('price', 0)) + float(r.get('shipping_cost', 0))):.2f}" if r.get('price') and r.get('shipping_cost') else r.get('price', 'N/A')
            })
        
        # Save search results to database
        update_book(
            book_id,
            ebay_search_results=json.dumps(formatted_results),
            ebay_search_date=date.today()
        )
        
        # Try to calculate and update eBay estimate if we have enough data
        estimate_updated = False
        estimate_info = None
        
        if len(results) >= 3:  # Minimum results needed for estimate
            try:
                price_result = api.get_price_estimate(
                    title=book.title,
                    author=book.author,
                    publisher=book.publisher,
                    stock_number=book.stock_number,
                    grade=book.grade,
                    min_results=3
                )
                
                if price_result:
                    # Check if result is an error dict
                    if isinstance(price_result, dict) and "error" in price_result:
                        # Handle error case
                        error_type = price_result.get("error_type", "unknown")
                        error_msg = price_result.get("error", "Unknown error")
                        update_book(
                            book_id,
                            ebay_estimate=None,
                            price_date=date.today(),
                            price_source='eBay search',
                            price_notes=f'eBay search performed: {error_msg}'
                        )
                        estimate_updated = True
                        estimate_info = {
                            'error': error_msg,
                            'error_type': error_type
                        }
                    else:
                        # Success case
                        ebay_estimate, price_info = price_result
                        
                        # Update the book in database (only ebay_estimate, NOT market_value)
                        update_book(
                            book_id,
                            ebay_estimate=ebay_estimate,
                            price_date=price_info["date"],
                            price_source=price_info["source"],
                            price_notes=price_info["notes"]
                        )
                        
                        estimate_updated = True
                        estimate_info = {
                            'ebay_estimate': ebay_estimate,
                            'date': str(price_info["date"]),
                            'notes': price_info["notes"]
                        }
            except Exception as e:
                # If estimate calculation fails, clear the estimate and record the error
                update_book(
                    book_id,
                    ebay_estimate=None,
                    price_date=date.today(),
                    price_source='eBay search (calculation failed)',
                    price_notes=f'eBay search performed but estimate calculation failed: {str(e)}'
                )
                estimate_updated = True  # Trigger UI reload to show cleared estimate
                estimate_info = {'error': f'Could not calculate estimate: {str(e)}'}
        else:
            # Not enough listings, but record that a search was performed
            # Clear the estimate since we can't calculate one
            error_msg = "No results" if len(results) == 0 else "No estimate"
            update_book(
                book_id,
                ebay_estimate=None,
                price_date=date.today(),
                price_source='eBay search',
                price_notes=f'eBay search performed: {error_msg}'
            )
            estimate_updated = True  # Trigger UI reload to show cleared estimate
            estimate_info = {
                'error': error_msg,
                'error_type': 'no_results' if len(results) == 0 else 'insufficient_results'
            }
        
        return jsonify({
            'book': {
                'title': book.title,
                'author': book.author,
                'publisher': book.publisher,
                'stock_number': book.stock_number,
                'grade': book.grade or 'Not graded'
            },
            'results': formatted_results,
            'count': len(formatted_results),
            'estimate_updated': estimate_updated,
            'estimate': estimate_info
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ebay_estimate_bulk', methods=['POST'])
def api_ebay_estimate_bulk():
    """API endpoint to run eBay estimates for multiple books with progress updates."""
    def generate():
        try:
            from book_catalog.book_manager import list_all_books, update_book
            from datetime import date
            import re
            
            data = request.get_json()
            filter_type = data.get('filter', 'all')  # 'all', 'owned', 'not_owned'
            
            # Get books based on filter
            all_books = list_all_books()
            if filter_type == 'owned':
                books = [b for b in all_books if b.owned]
            elif filter_type == 'not_owned':
                books = [b for b in all_books if not b.owned]
            else:
                books = all_books
            
            # Initialize eBay API
            api = eBayAPI(
                app_id=EBAY_PRODUCTION_APP_ID,
                cert_id=EBAY_PRODUCTION_CERT_ID,
                dev_id=EBAY_PRODUCTION_DEV_ID,
                sandbox=False,
                openai_api_key=OPENAI_API_KEY
            )
            
            total = len(books)
            results = {
                'total': total,
                'processed': 0,
                'success': 0,
                'no_results': 0,
                'no_estimate': 0,
                'errors': 0,
                'details': []
            }
            
            # Send initial progress
            yield f"data: {json.dumps({'type': 'progress', 'current': 0, 'total': total, 'message': f'Starting... 0/{total}'})}\n\n"
            
            # Process each book
            for idx, book in enumerate(books, 1):
                try:
                    # Send progress update
                    yield f"data: {json.dumps({'type': 'progress', 'current': idx, 'total': total, 'message': f'Processing {idx}/{total}: {book.title}'})}\n\n"
                    
                    # Get publication year if available
                    publication_year = None
                    if book.publication_date:
                        if isinstance(book.publication_date, str):
                            year_match = re.search(r'\b(19|20)\d{2}\b', book.publication_date)
                            if year_match:
                                publication_year = int(year_match.group())
                        else:
                            publication_year = book.publication_date.year
                    
                    # Get price estimate
                    price_result = api.get_price_estimate(
                        title=book.title,
                        author=book.author,
                        publisher=book.publisher,
                        stock_number=book.stock_number,
                        grade=book.grade,
                        publication_year=publication_year,
                        min_results=3
                    )
                    
                    results['processed'] += 1
                    
                    if price_result:
                        # Check if result is an error dict
                        if isinstance(price_result, dict) and "error" in price_result:
                            error_type = price_result.get("error_type", "unknown")
                            error_msg = price_result.get("error", "Unknown error")
                            
                            update_book(
                                book.id,
                                ebay_estimate=None,
                                price_date=date.today(),
                                price_source='eBay search',
                                price_notes=f'eBay search performed: {error_msg}'
                            )
                            
                            if error_type == "no_results":
                                results['no_results'] += 1
                            else:
                                results['no_estimate'] += 1
                            
                            results['details'].append({
                                'book_id': book.id,
                                'title': book.title,
                                'status': error_msg,
                                'error_type': error_type
                            })
                        else:
                            # Success case
                            ebay_estimate, price_info = price_result
                            
                            update_book(
                                book.id,
                                ebay_estimate=ebay_estimate,
                                price_date=price_info["date"],
                                price_source=price_info["source"],
                                price_notes=price_info["notes"]
                            )
                            
                            results['success'] += 1
                            results['details'].append({
                                'book_id': book.id,
                                'title': book.title,
                                'status': 'success',
                                'estimate': ebay_estimate
                            })
                    else:
                        results['errors'] += 1
                        results['details'].append({
                            'book_id': book.id,
                            'title': book.title,
                            'status': 'error',
                            'error': 'Unknown error'
                        })
                    
                except Exception as e:
                    results['errors'] += 1
                    results['details'].append({
                        'book_id': book.id,
                        'title': book.title,
                        'status': 'error',
                        'error': str(e)
                    })
            
            # Send final results
            yield f"data: {json.dumps({'type': 'complete', 'results': results})}\n\n"
        
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })


@app.route('/api/ebay_search_results/<int:book_id>')
def api_ebay_search_results(book_id):
    """API endpoint to get saved eBay search results for a book."""
    try:
        book = get_book_by_id(book_id)
        if not book:
            return jsonify({'error': 'Book not found'}), 404
        
        if not book.ebay_search_results:
            return jsonify({'error': 'No saved search results'}), 404
        
        results = json.loads(book.ebay_search_results)
        
        return jsonify({
            'book': {
                'title': book.title,
                'author': book.author,
                'publisher': book.publisher,
                'stock_number': book.stock_number,
                'grade': book.grade or 'Not graded'
            },
            'results': results,
            'count': len(results),
            'search_date': str(book.ebay_search_date) if book.ebay_search_date else None
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)

