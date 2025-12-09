from book_catalog.book_manager import add_book

books = [
    {
        'author': 'ERB',
        'title': 'The Mucker (full book)',
        'publisher': 'Ballantine',
        'stock_number': 'U6039',
        'price': '75c',
        'cover_artist': 'Robert Abbett',
        'publication_date': 'Jan 1966',
        'owned': True
    },
    {
        'author': 'ERB',
        'title': 'The Mucker (part 1)',
        'publisher': 'Ace',
        'stock_number': '54460',
        'price': '95c',
        'cover_artist': 'Frank Frazetta',
        'publication_date': 'Jun 1974',
        'owned': True
    },
    {
        'author': 'ERB',
        'title': 'The Return of the Mucker (part 2)',
        'publisher': 'Ace',
        'stock_number': '71815',
        'price': '95c',
        'cover_artist': 'Frank Frazetta',
        'publication_date': 'Jun 1974',
        'owned': True
    },
    {
        'author': 'ERB',
        'title': 'The Oakdale Affair',
        'publisher': 'Ace',
        'stock_number': '60563',
        'price': '$1.25',
        'cover_artist': 'Frank Frazetta',
        'publication_date': 'Jul 1974',
        'owned': True
    }
]

for book in books:
    add_book(**book)

print("\nAll books added!")

