let allBooks = [];
// Book IDs currently checked in the row-selection column. Persists across
// filter/sort/search re-renders so the selection isn't lost when the table
// re-paints.
const selectedBookIds = new Set();

// Escape untrusted text for safe interpolation into HTML — both text
// content and quoted attribute values. Book fields are user-typed and
// eBay listing titles/conditions come from third-party sellers, so
// everything from the API must pass through this before hitting .innerHTML.
function esc(text) {
    if (text === null || text === undefined) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

// Only allow http(s) URLs into href attributes. Blocks javascript:,
// data:, vbscript:, etc. that would execute on click.
function safeUrl(url) {
    if (!url) return '';
    const s = String(url).trim();
    if (/^https?:\/\//i.test(s)) return esc(s);
    return '';
}

// Header line for the eBay modals: only owned books have a "your copy" grade.
function copyGradeLine(book) {
    if (!book.owned) return '<strong>Not owned</strong>';
    return `<strong>Your Copy Grade: ${esc(book.grade)}</strong>`;
}

// Load authors on page load
async function loadAuthors() {
    try {
        const response = await fetch('/api/authors');
        const authors = await response.json();
        const select = document.getElementById('authorFilter');
        authors.forEach(author => {
            const option = document.createElement('option');
            option.value = author;
            option.textContent = author;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading authors:', error);
    }
}

// Fuzzy string matching function
function fuzzyMatch(str, pattern) {
    if (!pattern) return true;
    if (!str) return false;

    str = str.toLowerCase();
    pattern = pattern.toLowerCase().trim();
    const patternWords = pattern.split(/\s+/).filter(w => w.length > 0);

    // Short/single-word patterns: substring match, with fuzzy fallback for very short ones
    if (pattern.length <= 4 || patternWords.length === 1) {
        if (str.includes(pattern)) return true;
        if (pattern.length <= 3) {
            let patternIdx = 0;
            for (let i = 0; i < str.length && patternIdx < pattern.length; i++) {
                if (str[i] === pattern[patternIdx]) patternIdx++;
            }
            return patternIdx === pattern.length;
        }
        return false;
    }

    // Multi-word: every word must appear as a substring (prevents cross-field false matches like
    // "gray lensman" matching "galactic" in title + "lensman" in series)
    const allWordsMatch = patternWords.every(word => str.includes(word));
    if (allWordsMatch) return true;
    if (str.includes(pattern)) return true;
    return false;
}

// Similarity score for sorting search results by relevance
function similarityScore(str, pattern) {
    if (!str || !pattern) return 0;
    str = str.toLowerCase();
    pattern = pattern.toLowerCase();

    if (str === pattern) return 100;
    if (str.includes(pattern)) return 90;

    let matches = 0;
    let patternIdx = 0;
    for (let i = 0; i < str.length && patternIdx < pattern.length; i++) {
        if (str[i] === pattern[patternIdx]) {
            matches++;
            patternIdx++;
        }
    }
    const matchRatio = matches / pattern.length;
    const positionBonus = str.indexOf(pattern[0]) === 0 ? 10 : 0;
    return Math.round(matchRatio * 80 + positionBonus);
}

// Determine if a book entry is a magazine (using medium field)
function isMagazine(book) {
    return book.medium === 'Magazine';
}

function applySearch() {
    const searchTerm = document.getElementById('searchBox').value.trim();
    if (!searchTerm) {
        loadBooks();
        return;
    }

    const authorFilter = document.getElementById('authorFilter').value;
    const ownedFilter = document.getElementById('ownedFilter').value;
    const typeFilter = document.getElementById('typeFilter').value;

    const params = new URLSearchParams();
    if (authorFilter) params.append('author', authorFilter);
    if (ownedFilter) params.append('owned', ownedFilter);

    fetch(`/api/books?${params.toString()}`)
        .then(response => response.json())
        .then(books => {
            let filtered = books;
            if (typeFilter === 'book') {
                filtered = books.filter(book => book.medium === 'Paperback');
            } else if (typeFilter === 'magazine') {
                filtered = books.filter(book => book.medium === 'Magazine');
            }

            filtered = filtered.filter(book => {
                const searchFields = [
                    book.title || '', book.author || '', book.series || '',
                    book.publisher || '', book.stock_number || '', book.cover_artist || ''
                ];
                return searchFields.some(field => fuzzyMatch(field, searchTerm));
            });

            filtered.sort((a, b) => {
                const aScore = similarityScore([a.title, a.author, a.series, a.publisher].join(' '), searchTerm);
                const bScore = similarityScore([b.title, b.author, b.series, b.publisher].join(' '), searchTerm);
                return bScore - aScore;
            });

            displayBooks(filtered, true);
        })
        .catch(error => {
            console.error('Error searching books:', error);
        });
}

async function loadBooks() {
    const authorFilter = document.getElementById('authorFilter').value;
    const ownedFilter = document.getElementById('ownedFilter').value;
    const typeFilter = document.getElementById('typeFilter').value;
    const searchTerm = document.getElementById('searchBox').value.trim();

    const params = new URLSearchParams();
    if (authorFilter) params.append('author', authorFilter);
    if (ownedFilter) params.append('owned', ownedFilter);

    try {
        const response = await fetch(`/api/books?${params.toString()}`);
        allBooks = await response.json();

        let filtered = allBooks;
        if (typeFilter === 'book') {
            filtered = allBooks.filter(book => book.medium === 'Paperback');
        } else if (typeFilter === 'magazine') {
            filtered = allBooks.filter(book => book.medium === 'Magazine');
        }

        if (searchTerm) {
            filtered = filtered.filter(book => {
                const searchFields = [
                    book.title || '', book.author || '', book.series || '',
                    book.publisher || '', book.stock_number || '', book.cover_artist || ''
                ];
                return searchFields.some(field => fuzzyMatch(field, searchTerm));
            });

            filtered.sort((a, b) => {
                const aScore = similarityScore([a.title, a.author, a.series, a.publisher].join(' '), searchTerm);
                const bScore = similarityScore([b.title, b.author, b.series, b.publisher].join(' '), searchTerm);
                return bScore - aScore;
            });

            displayBooks(filtered, true);
        } else {
            displayBooks(filtered, false);
        }
    } catch (error) {
        console.error('Error loading books:', error);
        document.getElementById('booksTableBody').innerHTML =
            '<tr><td colspan="12" class="error">Error loading books. Please try again.</td></tr>';
    }
}

// Format the eBay-estimate cell. Estimate value if set, otherwise a
// "No results"/"No estimate" indicator derived from price_notes.
function formatEbayEstimate(book) {
    if (book.ebay_estimate) {
        let dateStr = '';
        let stale = false;
        if (book.price_date) {
            const dateParts = book.price_date.split('-');
            const priceDate = new Date(parseInt(dateParts[0]), parseInt(dateParts[1]) - 1, parseInt(dateParts[2]));
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            priceDate.setHours(0, 0, 0, 0);
            const daysDiff = Math.floor((today - priceDate) / (1000 * 60 * 60 * 24));
            const dateStrFormatted = priceDate.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
            dateStr = `<div style="font-size: 11px; font-weight: normal; color: #666; margin-top: 2px;">(as of ${dateStrFormatted})</div>`;
            if (daysDiff >= 90) stale = true;
        }
        return `<div${stale ? ' class="stale"' : ''}>$${book.ebay_estimate.toFixed(2)}</div>${dateStr}`;
    } else if (book.price_source && book.price_source.toLowerCase().includes('ebay')) {
        let dateStr = '';
        if (book.price_date) {
            const dateParts = book.price_date.split('-');
            const priceDate = new Date(parseInt(dateParts[0]), parseInt(dateParts[1]) - 1, parseInt(dateParts[2]));
            const dateStrFormatted = priceDate.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
            dateStr = `<div style="font-size: 11px; font-weight: normal; color: #666; margin-top: 2px;">(as of ${dateStrFormatted})</div>`;
        }
        let errorMsg = 'No estimate';
        if (book.price_notes) {
            if (book.price_notes.includes('No results')) errorMsg = 'No results';
            else if (book.price_notes.includes('No estimate')) errorMsg = 'No estimate';
        }
        // Green for "No estimate" (search found listings but no consensus); gray italic for "No results".
        const style = errorMsg === 'No estimate'
            ? 'color: #28a745; font-weight: 600;'
            : 'color: #999; font-style: italic;';
        return `<div style="${style}">${errorMsg}</div>${dateStr}`;
    }
    return '';
}

function displayBooks(books, skipSort = false) {
    const tbody = document.getElementById('booksTableBody');

    if (books.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" class="loading">No books found.</td></tr>';
        return;
    }

    // Extract series name and number for numeric-aware sorting ("Tarzan 3" before "Tarzan 10")
    function getSeriesSortKey(series) {
        if (!series) return ['zzz', 9999, 9999]; // Books without a series sink to the bottom
        const match = series.match(/^(.+?)\s+(\d+)(?:\/(\d+))?/);
        if (match) {
            return [match[1], parseInt(match[2]), match[3] ? parseInt(match[3]) : 0];
        }
        return [series, 0, 0];
    }

    // Publication-date sort key: extracts year (+ month if named) from strings like "1965", "Dec 1965",
    // "1965-01-01", or "1940/41". Missing dates sink to bottom.
    function getPublicationDateSortValue(pubDate) {
        if (!pubDate) return '9999-99-99';

        if (typeof pubDate === 'string') {
            const yearMatch = pubDate.match(/\b(19|20)\d{2}\b/);
            if (yearMatch) {
                const year = yearMatch[0];
                const monthNames = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
                let month = '99';
                for (let i = 0; i < monthNames.length; i++) {
                    if (pubDate.toLowerCase().includes(monthNames[i])) {
                        month = String(i + 1).padStart(2, '0');
                        break;
                    }
                }
                return `${year}-${month}-99`;
            }
        }

        if (pubDate.match(/^\d{4}-\d{2}-\d{2}$/)) return pubDate;
        return '9999-99-99';
    }

    if (!skipSort) {
        books.sort((a, b) => {
            const authorA = (a.author || '').toLowerCase();
            const authorB = (b.author || '').toLowerCase();
            if (authorA !== authorB) return authorA.localeCompare(authorB);

            const keyA = getSeriesSortKey(a.series);
            const keyB = getSeriesSortKey(b.series);
            if (keyA[0] !== keyB[0]) return keyA[0].localeCompare(keyB[0]);
            if (keyA[1] !== keyB[1]) return keyA[1] - keyB[1];
            if (keyA[2] !== keyB[2]) return keyA[2] - keyB[2];

            const dateA = getPublicationDateSortValue(a.publication_date);
            const dateB = getPublicationDateSortValue(b.publication_date);
            if (dateA !== dateB) return dateA.localeCompare(dateB);

            return (a.title || '').localeCompare(b.title || '');
        });
    }

    tbody.innerHTML = books.map(book => {
        // Compute the (as of ...) suffix for the eBay-estimate cell and detect stale (>= 90 days).
        let ebayEstimateDateStr = '';
        let ebayEstimateStale = false;

        if (book.price_date) {
            const dateParts = book.price_date.split('-');
            const priceDate = new Date(parseInt(dateParts[0]), parseInt(dateParts[1]) - 1, parseInt(dateParts[2]));
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            priceDate.setHours(0, 0, 0, 0);
            const daysDiff = Math.floor((today - priceDate) / (1000 * 60 * 60 * 24));
            const dateStr = priceDate.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });

            if (book.ebay_estimate || (book.price_source && book.price_source.toLowerCase().includes('ebay'))) {
                ebayEstimateDateStr = `<div style="font-size: 11px; font-weight: normal; color: #666; margin-top: 2px;">(as of ${dateStr})</div>`;
                if (daysDiff >= 90) ebayEstimateStale = true;
            }
        }

        // Publication-date display: pass-through range like "1940/41"; format YYYY-MM-DD nicely.
        let publicationDateStr = '';
        if (book.publication_date) {
            if (book.publication_date.includes('/') && /^\d{4}\/\d{1,2}$/.test(book.publication_date)) {
                publicationDateStr = book.publication_date;
            } else {
                try {
                    const dateParts = book.publication_date.split('-');
                    if (dateParts.length >= 3 && dateParts[1] === '01' && dateParts[2] === '01') {
                        publicationDateStr = dateParts[0];
                    } else if (dateParts.length >= 2 && dateParts[1] && dateParts[1] !== '01') {
                        const pubDate = new Date(parseInt(dateParts[0]), parseInt(dateParts[1]) - 1, 1);
                        publicationDateStr = pubDate.toLocaleDateString('en-US', { year: 'numeric', month: 'short' });
                    } else {
                        publicationDateStr = dateParts[0] || book.publication_date;
                    }
                } catch (e) {
                    publicationDateStr = book.publication_date;
                }
            }
        }

        return `
        <tr>
            <td style="text-align: center;">
                <input type="checkbox" class="row-select" data-book-id="${book.id}" onchange="toggleRowSelection(${book.id}, this)"${selectedBookIds.has(book.id) ? ' checked' : ''}>
            </td>
            <td class="editable-cell" data-field="series" data-book-id="${book.id}" data-value="${esc(book.series)}" ondblclick="startEditFromCell(this)">
                ${esc(book.series)}
                <span class="edit-indicator">✎</span>
            </td>
            <td class="editable-cell" data-field="author" data-book-id="${book.id}" data-value="${esc(book.author)}" ondblclick="startEditFromCell(this)">
                ${esc(book.author)}
                <span class="edit-indicator">✎</span>
            </td>
            <td class="editable-cell" data-field="title" data-book-id="${book.id}" data-value="${esc(book.title)}" ondblclick="startEditFromCell(this)">
                ${esc(book.title)}
                <span class="edit-indicator">✎</span>
            </td>
            <td class="editable-cell" data-field="publisher" data-book-id="${book.id}" data-value="${esc(book.publisher)}" ondblclick="startEditFromCell(this)">
                ${esc(book.publisher)}
                <span class="edit-indicator">✎</span>
            </td>
            <td class="editable-cell" data-field="publication_date" data-book-id="${book.id}" data-value="${esc(book.publication_date)}" data-edit-type="date" ondblclick="startEditFromCell(this)">
                ${esc(publicationDateStr)}
                <span class="edit-indicator">✎</span>
            </td>
            <td class="editable-cell" data-field="stock_number" data-book-id="${book.id}" data-value="${esc(book.stock_number)}" ondblclick="startEditFromCell(this)">
                ${esc(book.stock_number)}
                <span class="edit-indicator">✎</span>
            </td>
            <td class="editable-cell" data-field="price" data-book-id="${book.id}" data-value="${esc(book.price)}" ondblclick="startEditFromCell(this)">
                ${esc(book.price)}
                <span class="edit-indicator">✎</span>
            </td>
            <td class="editable-cell" data-field="grade" data-book-id="${book.id}" data-value="${esc(book.grade)}" data-edit-type="grade" ondblclick="startEditFromCell(this)">
                ${esc(book.grade)}
                <span class="edit-indicator">✎</span>
            </td>
            <td>
                <span class="owned-badge ${book.owned ? 'owned' : 'not-owned'}">
                    ${book.owned ? 'Owned' : 'Not Owned'}
                </span>
            </td>
            <td class="price">${formatEbayEstimate(book)}</td>
            <td>
                <div class="action-menu">
                    <button class="action-menu-btn" onclick="toggleActionMenu(${book.id}, event)">Actions ▼</button>
                    <div class="action-menu-content" id="menu-${book.id}">
                        <a class="action-menu-item ebay" onclick="searchEbay(${book.id}); closeActionMenu(${book.id})">eBay Search</a>
                        <a class="action-menu-item ebay" onclick="viewSavedEbayResults(${book.id}); closeActionMenu(${book.id})">View Saved Results</a>
                        <a class="action-menu-item owned" onclick="toggleOwned(${book.id}); closeActionMenu(${book.id})">Change to ${book.owned ? 'Not Owned' : 'Owned'}</a>
                        <a class="action-menu-item" onclick="updateBook(${book.id}); closeActionMenu(${book.id})" style="color: #007bff;">Update</a>
                    </div>
                </div>
            </td>
        </tr>
    `;
    }).join('');

    // Refresh selection UI so the header checkbox and the "N selected" counter reflect the
    // currently visible rows (previously-checked rows may now be filtered out; they stay in
    // the Set but aren't visible).
    updateSelectionUI();
}

// --- action menu --------------------------------------------------------

function toggleActionMenu(bookId, event) {
    event.stopPropagation();
    const menu = document.getElementById(`menu-${bookId}`);
    document.querySelectorAll('.action-menu-content').forEach(m => {
        if (m.id !== `menu-${bookId}`) m.classList.remove('show');
    });
    menu.classList.toggle('show');
}

function closeActionMenu(bookId) {
    document.getElementById(`menu-${bookId}`).classList.remove('show');
}

// Close menus and modals when clicking outside
window.onclick = function(event) {
    if (!event.target.matches('.action-menu-btn')) {
        document.querySelectorAll('.action-menu-content').forEach(menu => menu.classList.remove('show'));
    }
    if (event.target == document.getElementById('ebayModal')) closeModal();
    if (event.target == document.getElementById('updateModal')) closeUpdateModal();
};

async function toggleOwned(bookId) {
    try {
        const response = await fetch(`/api/books/${bookId}/toggle_owned`, { method: 'POST' });
        if (response.ok) {
            loadBooks();
        } else {
            const error = await response.json();
            alert('Error: ' + (error.error || 'Failed to update ownership status'));
        }
    } catch (error) {
        console.error('Error toggling owned status:', error);
        alert('Error updating ownership status. Please try again.');
    }
}

// --- update-book modal --------------------------------------------------

async function updateBook(bookId) {
    const modal = document.getElementById('updateModal');
    const content = document.getElementById('updateModalContent');

    modal.style.display = 'block';
    content.innerHTML = '<div class="loading">Loading book information...</div>';

    try {
        const books = await fetch('/api/books').then(r => r.json());
        const book = books.find(b => b.id === bookId);

        if (!book) {
            content.innerHTML = '<div class="error">Book not found.</div>';
            return;
        }

        content.innerHTML = `
            <div class="book-info">
                <strong>${esc(book.title)}</strong><br>
                ${esc(book.author)} | ${esc(book.publisher)} ${esc(book.stock_number)}
            </div>
            <form class="update-form" onsubmit="saveBookUpdate(${book.id}, event)">
                <div class="form-row">
                    <div class="form-group">
                        <label for="updateTitle">Title</label>
                        <input type="text" id="updateTitle" value="${esc(book.title)}">
                    </div>
                    <div class="form-group">
                        <label for="updateAuthor">Author</label>
                        <input type="text" id="updateAuthor" value="${esc(book.author)}">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="updatePublisher">Publisher</label>
                        <input type="text" id="updatePublisher" value="${esc(book.publisher)}">
                    </div>
                    <div class="form-group">
                        <label for="updateStockNumber">Stock Number</label>
                        <input type="text" id="updateStockNumber" value="${esc(book.stock_number)}">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="updatePrice">Cover Price</label>
                        <input type="text" id="updatePrice" placeholder="e.g., 40c, $1.25, 2'6" value="${esc(book.price)}">
                    </div>
                    <div class="form-group">
                        <label for="updateSeries">Series</label>
                        <input type="text" id="updateSeries" value="${esc(book.series)}">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="updateGrade">Grade</label>
                        <select id="updateGrade">
                            <option value="">-- Select Grade --</option>
                            <option value="Fine" ${book.grade === 'Fine' ? 'selected' : ''}>Fine</option>
                            <option value="Near Fine" ${book.grade === 'Near Fine' ? 'selected' : ''}>Near Fine</option>
                            <option value="Very Good" ${book.grade === 'Very Good' ? 'selected' : ''}>Very Good</option>
                            <option value="Good" ${book.grade === 'Good' ? 'selected' : ''}>Good</option>
                            <option value="Fair" ${book.grade === 'Fair' ? 'selected' : ''}>Fair</option>
                            <option value="Poor" ${book.grade === 'Poor' ? 'selected' : ''}>Poor</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="updatePrinting">Printing</label>
                        <input type="text" id="updatePrinting" placeholder="e.g., First US ppb printing" value="${esc(book.printing)}">
                    </div>
                </div>

                <div class="form-group">
                    <label for="updateConditionNotes">Condition Notes</label>
                    <textarea id="updateConditionNotes" placeholder="Describe the condition of the book...">${esc(book.condition_notes)}</textarea>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="updateCoverArtist">Cover Artist</label>
                        <input type="text" id="updateCoverArtist" value="${esc(book.cover_artist)}">
                    </div>
                    <div class="form-group">
                        <label for="updateCoverArtUrl">Cover Art URL</label>
                        <input type="url" id="updateCoverArtUrl" value="${esc(book.cover_art_url)}">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="updatePublicationDate">Publication Date</label>
                        <input type="date" id="updatePublicationDate" value="${esc(book.publication_date)}">
                    </div>
                    <div class="form-group">
                        <label for="updatePurchasePrice">Purchase Price (if known)</label>
                        <input type="number" id="updatePurchasePrice" step="0.01" placeholder="0.00" value="${esc(book.purchase_price)}">
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label for="updateOwned" style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="updateOwned" ${book.owned ? 'checked' : ''} style="width: auto; margin: 0;">
                            <span>Owned</span>
                        </label>
                    </div>
                </div>

                <div class="form-group">
                    <label for="updatePrintingNotes">Printing Notes</label>
                    <textarea id="updatePrintingNotes" placeholder="Notes on how printing was determined...">${esc(book.printing_notes)}</textarea>
                </div>

                <div class="form-group">
                    <label for="updateNotes">General Notes</label>
                    <textarea id="updateNotes" placeholder="Any additional notes...">${esc(book.notes)}</textarea>
                </div>

                <div class="form-actions">
                    <button type="button" class="btn-secondary" onclick="closeUpdateModal()">Cancel</button>
                    <button type="submit" class="btn-primary">Save Changes</button>
                </div>
            </form>
        `;
    } catch (error) {
        console.error('Error loading book:', error);
        content.innerHTML = `<div class="error">Error loading book: ${esc(error.message)}</div>`;
    }
}

async function saveBookUpdate(bookId, event) {
    event.preventDefault();

    const updateData = {};

    const title = document.getElementById('updateTitle').value;
    const author = document.getElementById('updateAuthor').value;
    const publisher = document.getElementById('updatePublisher').value;
    const stockNumber = document.getElementById('updateStockNumber').value;
    const price = document.getElementById('updatePrice').value;
    const series = document.getElementById('updateSeries').value;

    if (title) updateData.title = title;
    if (author) updateData.author = author;
    if (publisher !== undefined) updateData.publisher = publisher;
    if (stockNumber !== undefined) updateData.stock_number = stockNumber;
    if (price !== undefined) updateData.price = price;
    if (series !== undefined) updateData.series = series;

    const grade = document.getElementById('updateGrade').value;
    const conditionNotes = document.getElementById('updateConditionNotes').value;
    if (grade) updateData.grade = grade;
    if (conditionNotes !== undefined) updateData.condition_notes = conditionNotes;

    const printing = document.getElementById('updatePrinting').value;
    const printingNotes = document.getElementById('updatePrintingNotes').value;
    if (printing !== undefined) updateData.printing = printing;
    if (printingNotes !== undefined) updateData.printing_notes = printingNotes;

    const coverArtist = document.getElementById('updateCoverArtist').value;
    const coverArtUrl = document.getElementById('updateCoverArtUrl').value;
    if (coverArtist !== undefined) updateData.cover_artist = coverArtist;
    if (coverArtUrl !== undefined) updateData.cover_art_url = coverArtUrl;

    const publicationDate = document.getElementById('updatePublicationDate').value;
    const purchasePrice = document.getElementById('updatePurchasePrice').value;
    if (publicationDate) updateData.publication_date = publicationDate;
    if (purchasePrice) updateData.purchase_price = parseFloat(purchasePrice);

    updateData.owned = document.getElementById('updateOwned').checked;

    const notes = document.getElementById('updateNotes').value;
    if (notes !== undefined) updateData.notes = notes;

    try {
        const response = await fetch(`/api/books/${bookId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updateData)
        });

        if (response.ok) {
            closeUpdateModal();
            document.getElementById('searchBox').value = '';
            loadBooks();
        } else {
            const error = await response.json();
            alert('Error: ' + (error.error || 'Failed to update book'));
        }
    } catch (error) {
        console.error('Error updating book:', error);
        alert('Error updating book. Please try again.');
    }
}

function closeUpdateModal() {
    document.getElementById('updateModal').style.display = 'none';
}

// --- eBay search modal --------------------------------------------------

async function searchEbay(bookId) {
    const modal = document.getElementById('ebayModal');
    const content = document.getElementById('ebayModalContent');

    modal.style.display = 'block';
    content.innerHTML = '<div class="loading">Searching eBay...</div>';

    try {
        const response = await fetch(`/api/ebay_search/${bookId}`);
        const data = await response.json();

        if (data.error) {
            content.innerHTML = `<div class="error">Error: ${esc(data.error)}</div>`;
            return;
        }

        let html = `
            <div class="book-info">
                <strong>${esc(data.book.title)}</strong><br>
                ${esc(data.book.author)} | ${esc(data.book.publisher)} ${esc(data.book.stock_number)}<br>
                ${copyGradeLine(data.book)}
            </div>
        `;

        if (data.estimate_updated && data.estimate) {
            html += `
                <div style="background: #d4edda; padding: 10px; border-radius: 4px; margin-bottom: 15px; color: #155724;">
                    <strong>✓ eBay Estimate Updated!</strong><br>
                    eBay Estimate: $${data.estimate.ebay_estimate ? data.estimate.ebay_estimate.toFixed(2) : 'N/A'}<br>
                    <small>Date: ${esc(data.estimate.date)}</small>
                </div>
            `;
        } else if (data.estimate && data.estimate.error) {
            html += `<div class="error" style="margin-bottom: 15px;">${esc(data.estimate.error)}</div>`;
        } else if (data.count < 3) {
            html += `<div style="background: #fff3cd; padding: 10px; border-radius: 4px; margin-bottom: 15px; color: #856404;">
                <small>Not enough listings (${data.count}) to calculate estimate. Need at least 3.</small>
            </div>`;
        }

        html += '<div class="ebay-results">';

        if (data.results.length === 0) {
            html += '<div class="loading">No listings found on eBay.</div>';
        } else {
            data.results.forEach(item => {
                const safe = safeUrl(item.url);
                html += `
                    <div class="ebay-item">
                        <div class="ebay-item-title">${esc(item.title)}</div>
                        <div class="ebay-item-details">
                            <span><strong>Price:</strong> ${esc(item.price)}</span>
                            <span><strong>Shipping:</strong> ${esc(item.shipping)}</span>
                            <span><strong>Total:</strong> ${esc(item.total)}</span>
                            <span><strong>Condition:</strong> ${esc(item.condition)}</span>
                        </div>
                        ${safe ? `<a href="${safe}" target="_blank" rel="noopener noreferrer" class="ebay-item-link">View on eBay →</a>` : ''}
                    </div>
                `;
            });
        }

        html += '</div>';
        content.innerHTML = html;

        if (data.estimate_updated) {
            setTimeout(() => { loadBooks(); }, 500);
        }
    } catch (error) {
        console.error('Error searching eBay:', error);
        content.innerHTML = `<div class="error">Error searching eBay: ${esc(error.message)}</div>`;
    }
}

async function viewSavedEbayResults(bookId) {
    const modal = document.getElementById('ebayModal');
    const content = document.getElementById('ebayModalContent');

    modal.style.display = 'block';
    content.innerHTML = '<div class="loading">Loading saved results...</div>';

    try {
        const response = await fetch(`/api/ebay_search_results/${bookId}`);
        const data = await response.json();

        if (data.error) {
            content.innerHTML = `<div class="error">Error: ${esc(data.error)}</div>`;
            return;
        }

        let html = `
            <div class="book-info">
                <strong>${esc(data.book.title)}</strong><br>
                ${esc(data.book.author)} | ${esc(data.book.publisher)} ${esc(data.book.stock_number)}<br>
                ${copyGradeLine(data.book)}
                ${data.search_date ? `<br><small style="color: #666;">Search Date: ${esc(data.search_date)}</small>` : ''}
            </div>
        `;

        html += '<div class="ebay-results">';

        if (data.results.length === 0) {
            html += '<div class="loading">No saved listings found.</div>';
        } else {
            data.results.forEach(item => {
                const safe = safeUrl(item.url);
                html += `
                    <div class="ebay-item">
                        <div class="ebay-item-title">${esc(item.title)}</div>
                        <div class="ebay-item-details">
                            <span><strong>Price:</strong> ${esc(item.price)}</span>
                            <span><strong>Shipping:</strong> ${esc(item.shipping)}</span>
                            <span><strong>Total:</strong> ${esc(item.total)}</span>
                            <span><strong>Condition:</strong> ${esc(item.condition)}</span>
                        </div>
                        ${safe ? `<a href="${safe}" target="_blank" rel="noopener noreferrer" class="ebay-item-link">View on eBay →</a>` : ''}
                    </div>
                `;
            });
        }

        html += '</div>';
        content.innerHTML = html;
    } catch (error) {
        console.error('Error loading saved results:', error);
        content.innerHTML = `<div class="error">Error loading saved results: ${esc(error.message)}</div>`;
    }
}

function closeModal() {
    document.getElementById('ebayModal').style.display = 'none';
}

// --- selection + bulk estimate ------------------------------------------

function toggleRowSelection(bookId, checkbox) {
    if (checkbox.checked) selectedBookIds.add(bookId);
    else selectedBookIds.delete(bookId);
    updateSelectionUI();
}

function toggleSelectAllVisible(headerCheckbox) {
    document.querySelectorAll('input.row-select').forEach(box => {
        const id = parseInt(box.getAttribute('data-book-id'), 10);
        if (headerCheckbox.checked) {
            selectedBookIds.add(id);
            box.checked = true;
        } else {
            selectedBookIds.delete(id);
            box.checked = false;
        }
    });
    updateSelectionUI();
}

function clearSelection() {
    selectedBookIds.clear();
    document.querySelectorAll('input.row-select').forEach(box => { box.checked = false; });
    const header = document.getElementById('selectAllCheckbox');
    if (header) header.checked = false;
    updateSelectionUI();
}

function updateSelectionUI() {
    const countSpan = document.getElementById('selectedCount');
    const btn = document.getElementById('estimateSelectedBtn');
    if (countSpan) countSpan.textContent = selectedBookIds.size;
    if (btn) btn.disabled = selectedBookIds.size === 0;

    const header = document.getElementById('selectAllCheckbox');
    const boxes = document.querySelectorAll('input.row-select');
    if (header && boxes.length > 0) {
        const checkedCount = Array.from(boxes).filter(b => b.checked).length;
        header.checked = checkedCount === boxes.length;
        header.indeterminate = checkedCount > 0 && checkedCount < boxes.length;
    } else if (header) {
        header.checked = false;
        header.indeterminate = false;
    }
}

function runBulkEstimatesForSelected() {
    if (selectedBookIds.size === 0) return;
    const ids = Array.from(selectedBookIds);
    if (!confirm(`Run eBay estimates for ${ids.length} selected book${ids.length === 1 ? '' : 's'}? This may take a while.`)) {
        return;
    }
    _startBulkEstimate({ book_ids: ids }, event.target);
}

function runBulkEstimates(filterType) {
    const filterNames = {
        'all': 'All Books',
        'owned': 'Owned Books',
        'not_owned': 'Not Owned Books'
    };
    if (!confirm(`This will run eBay estimates for ${filterNames[filterType]}. This may take a while. Continue?`)) {
        return;
    }
    _startBulkEstimate({ filter: filterType }, event.target);
}

function _startBulkEstimate(payload, buttonEl) {
    const button = buttonEl;
    const originalText = button.textContent;
    button.disabled = true;

    const progressDiv = document.createElement('div');
    progressDiv.id = 'bulkEstimateProgress';
    progressDiv.style.cssText = 'position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); z-index: 2000; min-width: 300px; text-align: center;';
    progressDiv.innerHTML = `
        <h3 style="margin-top: 0;">Running Bulk Estimates</h3>
        <div id="progressMessage" style="margin: 15px 0; font-size: 16px; font-weight: 600; color: #007bff;">Starting...</div>
        <div id="progressFraction" style="margin: 10px 0; font-size: 14px; color: #666;">0/0</div>
        <button onclick="closeProgressModal()" style="margin-top: 15px; padding: 8px 16px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer;">Close</button>
    `;
    document.body.appendChild(progressDiv);

    const overlay = document.createElement('div');
    overlay.id = 'bulkEstimateOverlay';
    overlay.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1999;';
    document.body.appendChild(overlay);

    fetch('/api/ebay_estimate_bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(response => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function readChunk() {
            return reader.read().then(({ done, value }) => {
                if (done) return;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const data = JSON.parse(line.substring(6));

                        if (data.type === 'progress') {
                            const progressMessage = document.getElementById('progressMessage');
                            const progressFraction = document.getElementById('progressFraction');
                            if (progressMessage) progressMessage.textContent = data.message || `Processing ${data.current}/${data.total}`;
                            if (progressFraction) progressFraction.textContent = `${data.current}/${data.total} complete`;
                        } else if (data.type === 'complete') {
                            const results = data.results;
                            alert(
                                `Bulk estimate complete!\n\n` +
                                `Total: ${results.total}\n` +
                                `Success: ${results.success}\n` +
                                `No results: ${results.no_results}\n` +
                                `No estimate: ${results.no_estimate}\n` +
                                `Errors: ${results.errors}`
                            );
                            closeProgressModal();
                            button.disabled = false;
                            button.textContent = originalText;
                            // Re-fetch through current filters instead of a full page reload
                            // (would drop the user's author/type/owned/search state).
                            loadBooks();
                        } else if (data.type === 'error') {
                            alert('Error: ' + data.error);
                            closeProgressModal();
                            button.disabled = false;
                            button.textContent = originalText;
                        }
                    } catch (e) {
                        console.error('Error parsing SSE data:', e);
                    }
                }
                return readChunk();
            });
        }
        return readChunk();
    }).catch(error => {
        console.error('Error running bulk estimates:', error);
        alert('Error running bulk estimates. Please try again.');
        closeProgressModal();
        button.disabled = false;
        button.textContent = originalText;
    });
}

function closeProgressModal() {
    const progressDiv = document.getElementById('bulkEstimateProgress');
    const overlay = document.getElementById('bulkEstimateOverlay');
    if (progressDiv) progressDiv.remove();
    if (overlay) overlay.remove();
}

// --- inline editing -----------------------------------------------------

let currentEditCell = null;
let originalValue = null;

function startEditFromCell(cell) {
    const bookId = cell.getAttribute('data-book-id');
    const field = cell.getAttribute('data-field');
    const currentValue = cell.getAttribute('data-value') || '';
    const editType = cell.getAttribute('data-edit-type') || 'text';

    if (currentEditCell && currentEditCell !== cell) {
        cancelEdit(currentEditCell);
    }

    currentEditCell = cell;
    originalValue = currentValue;

    cell.classList.add('editing');

    if (editType === 'grade') {
        const select = document.createElement('select');
        select.style.width = '100%';
        const grades = ['', 'Fine', 'Near Fine', 'Very Good', 'Good', 'Fair', 'Poor'];
        grades.forEach(grade => {
            const option = document.createElement('option');
            option.value = grade;
            option.textContent = grade || '-- Select Grade --';
            if (grade === currentValue) option.selected = true;
            select.appendChild(option);
        });

        select.onblur = () => saveEdit(cell, bookId, field, select.value);
        select.onkeydown = (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                cancelEdit(cell);
            }
        };

        cell.innerHTML = '';
        cell.appendChild(select);
        select.focus();
    } else {
        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentValue || '';
        if (editType === 'date') {
            input.placeholder = 'e.g., 1965, Dec 1965, 1965-01-01, 1940/41';
        }
        input.style.width = '100%';
        input.onblur = () => saveEdit(cell, bookId, field, input.value);
        input.onkeydown = (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                input.blur();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                cancelEdit(cell);
            }
        };

        cell.innerHTML = '';
        cell.appendChild(input);
        input.focus();
        input.select();
    }
}

async function saveEdit(cell, bookId, field, newValue) {
    if (newValue === originalValue) {
        cancelEdit(cell);
        return;
    }

    cell.innerHTML = '<span style="color: #666; font-style: italic;">Saving...</span>';

    try {
        const response = await fetch(`/api/books/${bookId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [field]: newValue || null })
        });

        if (response.ok) {
            loadBooks();
        } else {
            const error = await response.json();
            alert('Error: ' + (error.error || 'Failed to update'));
            cancelEdit(cell);
        }
    } catch (error) {
        console.error('Error updating book:', error);
        alert('Error updating book. Please try again.');
        cancelEdit(cell);
    }

    currentEditCell = null;
}

function cancelEdit(cell) {
    if (!cell) return;
    loadBooks();
    currentEditCell = null;
}

// --- init ---------------------------------------------------------------

loadAuthors();
loadBooks();
updateSelectionUI();
