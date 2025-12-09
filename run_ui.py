"""
Simple script to run the book catalog UI.
"""

from app import app

if __name__ == '__main__':
    print("Starting Book Catalog UI...")
    print("Open your browser and go to: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    app.run(debug=True, port=5000, host='127.0.0.1')

