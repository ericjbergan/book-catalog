"""
Database migration script to rename estimated_value to ebay_estimate.

Run this script once to update your existing database.
"""

import sqlite3
import sys
import os


def migrate_database(db_path='book_catalog.db'):
    """Migrate estimated_value column to ebay_estimate."""
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. Nothing to migrate.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if estimated_value column exists
        cursor.execute("PRAGMA table_info(books)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'estimated_value' in columns and 'ebay_estimate' not in columns:
            print("Migrating estimated_value to ebay_estimate...")
            
            # SQLite doesn't support RENAME COLUMN in older versions
            # So we need to:
            # 1. Create new table with ebay_estimate
            # 2. Copy data
            # 3. Drop old table
            # 4. Rename new table
            
            # Get all column names
            cursor.execute("PRAGMA table_info(books)")
            column_info = cursor.fetchall()
            
            # Build new column list
            new_columns = []
            for col in column_info:
                col_name = col[1]
                if col_name == 'estimated_value':
                    new_columns.append('ebay_estimate')
                else:
                    new_columns.append(col_name)
            
            # Create new table
            cursor.execute("""
                CREATE TABLE books_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author VARCHAR(200) NOT NULL,
                    title VARCHAR(300) NOT NULL,
                    publisher VARCHAR(100),
                    stock_number VARCHAR(50),
                    isbn VARCHAR(20),
                    price VARCHAR(20),
                    publisher_address VARCHAR(200),
                    number_line VARCHAR(100),
                    copyright_date DATE,
                    copyright_text TEXT,
                    cover_artist VARCHAR(100),
                    cover_art_url VARCHAR(500),
                    logo_description TEXT,
                    cover_description TEXT,
                    printing VARCHAR(50),
                    printing_number INTEGER,
                    printing_notes TEXT,
                    publication_date DATE,
                    grade VARCHAR(20),
                    condition_notes TEXT,
                    owned BOOLEAN DEFAULT 1,
                    market_value FLOAT,
                    ebay_estimate FLOAT,
                    purchase_price FLOAT,
                    price_date DATE,
                    price_source VARCHAR(200),
                    price_notes TEXT,
                    notes TEXT,
                    spine_info TEXT,
                    back_cover_info TEXT
                )
            """)
            
            # Copy data, mapping estimated_value to ebay_estimate
            column_names = [col[1] for col in column_info]
            select_cols = []
            for col in column_names:
                if col == 'estimated_value':
                    select_cols.append('estimated_value AS ebay_estimate')
                else:
                    select_cols.append(col)
            
            insert_sql = f"""
                INSERT INTO books_new ({', '.join(new_columns)})
                SELECT {', '.join(select_cols)} FROM books
            """
            cursor.execute(insert_sql)
            
            # Drop old table
            cursor.execute("DROP TABLE books")
            
            # Rename new table
            cursor.execute("ALTER TABLE books_new RENAME TO books")
            
            # Recreate indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_books_author ON books(author)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_books_title ON books(title)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_books_publisher ON books(publisher)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_books_stock_number ON books(stock_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_books_isbn ON books(isbn)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_books_owned ON books(owned)")
            
            conn.commit()
            print("Migration completed successfully!")
            print("Column 'estimated_value' has been renamed to 'ebay_estimate'")
        
        elif 'ebay_estimate' in columns:
            print("Database already migrated (ebay_estimate column exists).")
        
        else:
            print("No estimated_value column found. Database may be new or already migrated.")
    
    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
        sys.exit(1)
    
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'book_catalog.db'
    migrate_database(db_path)

