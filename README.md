# Book Catalog

A Python tool for cataloging books, particularly focused on identifying first printings and determining book condition/grade. This project is designed for book collectors who need to track detailed information about their collection, including books they own and books they're researching.

## What is This Project?

This is a specialized cataloging system for book collectors, especially those interested in:
- **Identifying first printings** - Tracking publisher addresses, number lines, copyright information, cover artists, and other indicators that help determine if a book is a first printing
- **Grading books** - Recording condition and grade information for valuation purposes
- **Managing collections** - Keeping track of both owned books and books you're researching or want to acquire
- **Historical research** - Documenting publisher information, addresses, and design elements that change over time

The system captures detailed bibliographic information that collectors use to authenticate and value books, such as:
- Publisher addresses (which changed over time - e.g., Ace Books moved from "23 West 47th St" to other locations)
- Cover artists (first printings often feature original commissioned artwork)
- Logo designs (publisher logos evolved over the years)
- Price points (which indicate publication era)
- Number lines or printing statements
- Copyright information

## Features

### Comprehensive Data Model

The catalog captures extensive information needed for printing identification and grading:

**Basic Identification:**
- Author, title, publisher
- Stock number (e.g., "F-156" for Ace Books)
- ISBN (for modern books)

**Printing Identification:**
- **Price** - Original cover price (e.g., "40c", "$0.40") helps date the book
- **Publisher Address** - Critical for identifying printings (e.g., "23 West 47th St, New York" indicates Ace Books from 1952-1972)
- **Number Line** - Printing indicators (e.g., "1 2 3 4 5" or absence thereof)
- **Copyright Date** - Earliest copyright date
- **Copyright Text** - Full copyright page text

**Cover and Design:**
- **Cover Artist** - Important for first printings (e.g., Frazetta covers on first Ace editions)
- **Cover Art URL** - Link to cover art image (useful for reference and identification)
- **Logo Description** - Publisher logo details (e.g., "lowercase 'a' with ace across the middle")
- **Cover Description** - Colors, design elements, typography

**Printing Determination:**
- **Printing** - Determined printing (First, Second, Unknown, etc.)
- **Printing Notes** - Reasoning and evidence for printing determination
- **Publication Date** - When the book was published

**Condition and Grade:**
- **Grade** - Condition grade (Fine, Very Good, Good, Fair, etc.)
- **Condition Notes** - Detailed condition description
- **Printing Number** - Numeric printing number (1, 2, 3, etc.)

**Collection Management:**
- **Owned** - Boolean flag to track owned vs. researched books
- **Notes** - General notes
- **Spine Info** - Information from the spine
- **Back Cover Info** - Information from the back cover

**Price Tracking:**
- **Market Value** - Best guess at current market value in USD (optimistic estimate)
- **eBay Estimate** - eBay-based estimate from Buy It Now listings, considering condition/grade matching
- **Purchase Price** - Price paid when acquired (if known)
- **Price Date** - Date when price was estimated/recorded
- **Price Source** - Source of price estimate (e.g., "eBay API (Buy It Now listings)")
- **Price Notes** - Notes about pricing methodology or factors affecting value

**Dual Pricing Methodology:**
The catalog uses a **dual pricing system** to provide both optimistic and eBay-based estimates:

- **Market Value** - Represents a thorough, slightly conservative estimate of what a book might sell for in favorable market conditions. Market values are researched using multiple sources including online book dealers, auction records, and collector pricing guides. The research considers factors such as first printing status, condition/grade, cover artist, publisher, and current market trends. Estimates are intentionally slightly conservative to provide realistic valuations. This is useful for:
  - Insurance purposes
  - Collection valuation
  - Understanding potential upside value
  
- **eBay Estimate** - Represents an eBay-based estimate calculated from Buy It Now listings, weighted by condition/grade matching. This is useful for:
  - Realistic selling expectations based on current eBay market
  - Understanding what similar condition books are listed for
  - Planning purposes

**Price Addition Policy:**
- Prices are **not automatically added** when books are entered into the catalog
- Price estimates are added **only when explicitly requested** to avoid unnecessary processing time
- When prices are requested, both market value and eBay estimates are researched and added together
- This approach allows you to control when pricing research is performed

**eBay Estimate Calculation:**
The eBay estimate is calculated from Buy It Now listings on eBay, with the following considerations:

- **Edition Matching** - Only listings that match the specific edition are used:
  - **Publisher Match** - Listings must match the book's publisher (e.g., "Ace", "Ballantine")
  - **Stock Number Match** - Listings must match the book's stock number (e.g., "F-156", "F777")
  - This ensures that different printings/editions of the same title are not mixed together
- **Buy It Now Listings Only** - Only fixed-price listings are considered (auctions excluded)
- **Condition Matching** - If your book has a grade, listings with matching or similar conditions are weighted more heavily
- **Grade Hierarchy** - Fine > Very Good > Good > Fair (closer matches count more)
- **Weighted Average** - Top matching listings (by condition) are used to calculate the estimate
- **Median Fallback** - If no grade is specified, uses median of all Buy It Now prices
- **Relaxed Filtering** - If not enough exact matches are found, the system may relax the stock number requirement (keeping publisher match) or use all matching listings with a note

**Factors Considered:**
- **First printings** command premium prices, especially with original cover art (e.g., Frazetta covers)
- **Condition** significantly affects value (Fine/Near Fine > Very Good > Good)
- **Market fluctuations** - Prices can vary widely based on demand, availability, and market conditions
- **Cover artists** - Frazetta covers on Ace first printings are highly collectible and command significant premiums
- Prices should be updated regularly as market conditions change
- Actual sale prices may vary significantly from estimates based on buyer interest, timing, and specific condition details

**Note:** The eBay Browse API does not provide access to completed/sold listings. The estimate is based on current Buy It Now listings only. For historical sold prices, you would need to use other data sources or eBay's Finding API (which has different access requirements).

### Technical Features

- **SQLite Database** - Local file-based storage, no server required
- **CSV Import** - Bulk import from spreadsheet data
- **Search Capabilities** - Query by author, title, publisher, stock number, ownership status
- **Python API** - Programmatic access for scripting and automation
- **Data Verification** - Online verification of bibliographic information when entering books
- **eBay API Integration** - Automated price fetching from eBay listings

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Initialize the database:
```bash
python -m book_catalog.init_db
```

3. (Optional) Set up eBay API credentials for automated price fetching:
   - Copy `ebay_credentials_example.py` to `ebay_credentials.py`
   - Fill in your eBay API credentials (see eBay API Setup below)

## Web UI

A simple web-based user interface is available for browsing and searching your book catalog.

**To start the UI:**
```bash
python run_ui.py
```

Then open your browser and go to: http://localhost:5000

**Features:**
- **Book Listing** - View all books in a sortable table
- **Filtering** - Filter by author and ownership status (owned/not owned)
- **eBay Search** - Click "eBay Search" button on any book to search eBay for current listings
- **Direct Links** - eBay search results include direct links to listings

The UI displays:
- Book ID, Author, Title, Publisher, Stock Number
- Grade and ownership status
- Market Value and eBay Estimate (if available)
- Quick access to eBay search for each book

## eBay API Integration

The catalog includes integration with eBay's Browse API for automated price fetching. This allows you to get current market prices for your books based on actual eBay listings.

### eBay API Setup

1. **Create an eBay Developer Account**:
   - Go to [eBay Developer Program](https://developer.ebay.com/)
   - Sign up for a developer account (separate from your regular eBay account)

2. **Get API Credentials**:
   - Sign in to your developer account
   - Click on your username → "Application Keys"
   - Create a keyset for Sandbox (testing) or Production (live)
   - You'll receive:
     - **App ID (Client ID)**
     - **Cert ID (Client Secret)**
     - **Dev ID (Developer ID)**

3. **Configure Credentials**:
   - Copy `ebay_credentials_example.py` to `ebay_credentials.py`
   - Fill in your Sandbox credentials (start with Sandbox for testing)
   - When ready for production, add your Production credentials

### Using eBay Price Fetching

**Command Line:**
```bash
python fetch_book_price.py <book_id>
```

**Python API:**
```python
from book_catalog.ebay_api import get_price_for_book
from ebay_credentials import EBAY_SANDBOX_APP_ID, EBAY_SANDBOX_CERT_ID, EBAY_SANDBOX_DEV_ID

result = get_price_for_book(
    book_id=1,
    app_id=EBAY_SANDBOX_APP_ID,
    cert_id=EBAY_SANDBOX_CERT_ID,
    dev_id=EBAY_SANDBOX_DEV_ID,
    sandbox=True
)
```

The function will:
- Search eBay for listings matching the book
- Calculate market value (optimistic) and estimated value (conservative)
- Update the book record in the database with price information

**Note:** The eBay API has rate limits. For production use, you may want to implement rate limiting and caching.

## Data Verification

When entering books into the catalog, bibliographic information is verified against online sources (bibliographic databases, publisher records, collector resources) to ensure accuracy. This verification process helps:

- **Confirm publication details** - Verify publisher, publication dates, stock numbers, and ISBNs
- **Validate cover artists** - Confirm artist attributions for first printing identification
- **Check pricing information** - Verify historical price points match publication era
- **Identify discrepancies** - Report any differences between provided data and verified sources
- **Fill missing data** - When table entries contain blanks (missing information), the verification process attempts to find and fill in missing data such as publication dates, stock numbers, cover artists, prices, or other bibliographic details

### Handling Missing Data

**If you provide a table entry with blanks:**
- The verification process will search for the missing information during online verification
- Any missing data found will be **reported to you** before being added to the database
- You can review the findings and decide whether to accept the discovered information
- The database will be updated with the found information unless you indicate otherwise

**Examples of commonly found missing data:**
- Publication dates (when only year or approximate date is known)
- Stock numbers or catalog numbers
- Cover artist names
- Prices (when price information is missing)
- Publisher addresses
- ISBNs (for modern books)

**Important:** When discrepancies are found during verification, they are **reported to you** rather than automatically changed. You decide whether to update the data based on the verification findings. This ensures your catalog reflects your actual books and any specific variants or information you've documented.

Common sources used for verification include:
- Bibliographic databases (WorldCat, Library of Congress)
- Publisher historical records
- Collector resources and reference books
- Online book databases and marketplaces

## Usage

### Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize the database:**
   ```bash
   python -m book_catalog.init_db
   ```
   This creates a `book_catalog.db` SQLite database file in the current directory.

3. **Run the example:**
   ```bash
   python example_usage.py
   ```

### Programmatic Usage

#### Initialize Database

```python
from book_catalog.database import init_database

init_database()  # Creates book_catalog.db
```

#### Add a Book

```python
from book_catalog.book_manager import add_book
from datetime import date

# Example: Adding a first printing identification
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
    printing_notes="Frazetta cover, no number line, 23 West 47th St address, no copyright info found",
    grade="Very Good",
    condition_notes="Minor edge wear, pages slightly yellowed"
)

# Example: Adding a book you don't own (for research)
add_book(
    author="Tolkien",
    title="The Hobbit",
    publisher="Ballantine",
    stock_number="U2010",
    price="$0.75",
    owned=False,
    printing="Unknown",
    notes="Researching first printing indicators"
)
```

### Search Books

```python
from book_catalog.book_manager import search_books

# Search by author
books = search_books(author="ERB")

# Search by publisher
books = search_books(publisher="Ace")

# Search owned books only
books = search_books(owned=True)
```

#### Update a Book

```python
from book_catalog.book_manager import update_book

# Update printing determination after research
update_book(
    1,  # book_id
    printing="First",
    printing_notes="Confirmed: Frazetta cover matches first printing, address confirms 1962-1963 era",
    grade="Fine"
)
```

#### List All Books

```python
from book_catalog.book_manager import list_all_books

all_books = list_all_books()
for book in all_books:
    print(f"{book.author}: {book.title} - {book.publisher} {book.stock_number}")
```

#### Get Book by ID

```python
from book_catalog.book_manager import get_book_by_id

book = get_book_by_id(1)
print(f"Printing: {book.printing}")
print(f"Notes: {book.printing_notes}")
```

### Import from CSV

If you have book data in a spreadsheet or table, you can import it:

```python
from book_catalog.import_utils import import_from_csv

import_from_csv('books.csv')
```

**CSV Format:** The CSV should have columns matching the book fields (case-insensitive). Required columns:
- `author` (required)
- `title` (required)

Optional columns:
- `publisher`, `stock_number`, `isbn`, `price`, `publisher_address`
- `number_line`, `copyright_date`, `copyright_text`, `cover_artist`, `cover_art_url`, `logo_description`
- `cover_description`, `printing`, `printing_number`, `printing_notes`, `publication_date`, `grade`
- `condition_notes`, `owned` (true/false), `notes`, `spine_info`, `back_cover_info`
- `market_value`, `estimated_value`, `purchase_price`, `price_date`, `price_source`, `price_notes`

**Date Formats:** The importer accepts various date formats:
- `YYYY-MM-DD` (e.g., "1962-01-15")
- `MM/DD/YYYY` (e.g., "01/15/1962")
- `YYYY` (e.g., "1962" - will use January 1st)

**Owned Field:** Use `true`, `1`, `yes`, `y`, or `owned` for owned books; anything else is treated as not owned.

## Database Schema

The database uses SQLite with a single `books` table containing all catalog information. The schema is defined in `book_catalog/models.py` using SQLAlchemy.

**Key Fields:**
- `id` - Primary key (auto-increment)
- `author`, `title` - Required fields
- `publisher`, `stock_number`, `isbn` - Publisher identification
- `price`, `publisher_address`, `number_line` - Printing indicators
- `copyright_date`, `copyright_text` - Copyright information
- `cover_artist`, `cover_art_url`, `logo_description`, `cover_description` - Design elements
- `printing`, `printing_number`, `printing_notes`, `publication_date` - Printing determination
- `grade`, `condition_notes` - Condition information
- `owned` - Boolean flag (True = owned, False = not owned)
- `market_value`, `estimated_value`, `purchase_price`, `price_date`, `price_source`, `price_notes` - Price tracking
- `notes`, `spine_info`, `back_cover_info` - Additional information

All text fields support full descriptions and notes. The database is indexed on commonly searched fields (author, title, publisher, stock_number, owned).

## Project Structure

```
book-catalog/
├── book_catalog/              # Main package
│   ├── __init__.py           # Package initialization
│   ├── models.py             # SQLAlchemy database models
│   ├── database.py           # Database initialization utilities
│   ├── book_manager.py       # CRUD operations (add, search, update, delete)
│   ├── import_utils.py       # CSV import functionality
│   └── init_db.py            # Database initialization script
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── example_usage.py          # Example usage script
└── book_catalog.db          # SQLite database (created after initialization)
```

## Paperback Grading Standards

Accurate grading is essential for collectors to determine a book's value and condition. The following standardized grading scale is widely accepted in the book collecting community, with specific attention to paperback characteristics:

### Grade Definitions

**As New / Mint / Very Fine (VF):**
- The book appears unread and is in pristine condition
- No defects, markings, or signs of wear
- Spine is tight with no creases whatsoever
- Cover is crisp and unworn
- Pages are clean and unmarked
- No fading, discoloration, or edge wear
- Binding is tight and firm

**Fine (F):**
- The book has been read but remains in excellent condition
- No obvious defects; may lack the crispness of "As New"
- Spine may show minimal handling but no reading crease
- Cover may have very minor edge wear or slight corner blunting
- Pages are clean with no markings, underlining, or highlighting
- Binding is tight
- Any minor blemishes must be noted

**Near Fine (NF):**
- The book is close to Fine but may have very minor defects
- Slight wear at edges or corners
- Spine may show slight creasing but no full reading crease
- Pages may show slight browning but are not brittle
- Clean with no significant markings
- Binding remains tight

**Very Good (VG):**
- Shows signs of careful use but remains sound and attractive
- Cover may have slight creases, minor scuffs, or light wear
- Spine may have a reading crease (single vertical crease from reading) but remains intact
- Pages may show slight browning, minor foxing, or light edge discoloration
- May have minor defects such as small tears, owner's inscription, or remainder marks
- All pages present and binding is intact
- Any defects must be noted

**Good (G):**
- Average used and worn book with all pages present
- Cover and spine show signs of wear including creases, scuffing, or edge wear
- Spine may have multiple creases or significant wear
- Pages may have minor markings, underlining, highlighting, or library markings
- May have loose binding or slight separation at hinges
- May show discoloration, foxing, or minor stains
- Binding remains functional but may show wear

**Fair (FR):**
- Heavily worn but remains complete
- Cover may be detached or significantly damaged
- Spine may be heavily creased, cracked, or split
- Binding may be loose with pages separating
- May have significant defects such as large tears, stains, water damage, or soiling
- May lack endpapers, half-title, or other non-essential pages
- Text pages are complete and readable
- Any major defects must be noted

**Poor (P):**
- Extremely worn and may be incomplete
- Significant damage including detached cover, missing pages, or extensive damage
- May have extensive moisture damage, insect damage, or severe staining
- Binding may be broken or pages may be loose
- Only suitable as a reading copy if text is complete and legible
- Marginally collectible unless very unusual or rare

### Key Factors for Paperback Grading

**Spine Condition:**
- **No crease** - Required for Fine or better
- **Reading crease** - Single vertical crease from being opened; acceptable in Very Good
- **Multiple creases** - Indicates Good or lower
- **Cracked or split spine** - Indicates Fair or Poor

**Cover Condition:**
- Check for creases, tears, stains, fading, or discoloration
- Edge wear and corner blunting
- Rubbing or scuffing
- Stickers, price tags, or library markings

**Pages:**
- Look for tears, stains, foxing (brown spots), or discoloration
- Check for markings: underlining, highlighting, writing, or library stamps
- Ensure all pages are present and legible
- Check for brittleness or yellowing

**Binding:**
- Check if binding is tight and firm
- Look for loose pages or separation at hinges
- Ensure text block is secure

**Odor:**
- Detect any musty, smoky, or mildew smells
- These can significantly affect desirability and value

**Completeness:**
- Ensure no pages, maps, or plates are missing
- Check for presence of endpapers, half-title, and other elements

### Grading Best Practices

1. **Grade conservatively** - When in doubt, grade lower
2. **Note all defects** - Always document any issues in condition notes
3. **Be specific** - Use detailed condition notes to describe exact issues
4. **Consider age** - Older books may naturally show more wear; grade relative to age
5. **Check completeness** - Verify all pages and elements are present
6. **Examine thoroughly** - Check cover, spine, pages, and binding carefully

## Use Cases

### Identifying First Printings

This tool helps collectors identify first printings by tracking:
- **Publisher addresses** that changed over time (e.g., Ace Books addresses)
- **Cover artists** who created original art for first editions
- **Number lines** or their absence
- **Price points** that indicate publication era
- **Logo designs** that evolved over publisher history

### Collection Management

- Track books you own vs. books you're researching
- Document condition and grade for insurance/valuation
- Build a reference database of printing indicators
- Compare multiple copies of the same title

### Research and Documentation

- Document publisher information for future reference
- Record detailed observations about each book
- Build a searchable database of bibliographic information
- Export data for analysis or sharing

## Future Enhancements

Potential additions to the project:
- **Web UI** - Browser-based interface for browsing and editing
- **Export Functionality** - Export to CSV, JSON, or other formats
- **Printing Identification Algorithms** - Automated suggestions based on collected data
- **Grade Calculation Tools** - Standardized grading system
- **Image Storage** - Store cover photos and condition images
- **Price Tracking** - Track book values over time
- **Bibliography Integration** - Link to external bibliographic databases
- **Duplicate Detection** - Identify potential duplicate entries

## Requirements

- Python 3.7+
- SQLAlchemy 2.0+

## License

This project is for personal use. Modify as needed for your collection management needs.

