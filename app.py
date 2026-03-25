import os
import json
import sqlite3
import re
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

DB_PATH = os.path.join(os.path.dirname(__file__), 'bidfinder.db')

# --- Database ---

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL UNIQUE,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS search_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT,
            source_name TEXT,
            source_url TEXT,
            snippet TEXT,
            found_date TEXT DEFAULT (datetime('now')),
            keyword TEXT
        );

        CREATE TABLE IF NOT EXISTS crm_tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT,
            source TEXT,
            client TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'nowy',
            notes TEXT,
            priority TEXT DEFAULT 'normalny',
            value TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS client_research (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            email TEXT,
            research_data TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    ''')

    # Insert default sources
    default_sources = [
        ("Nowy Marketing", "https://nowymarketing.pl/?s=przetarg"),
        ("MMP Online", "https://mmponline.pl/przetargi/"),
        ("Wirtualne Media", "https://www.wirtualnemedia.pl/wyniki?zapytanie=przetarg"),
        ("OnePlace MarketPlanet", "https://oneplace.marketplanet.pl/zapytania-ofertowe-przetargi/"),
        ("Press.pl", "https://www.press.pl/tag/przetarg-publiczny"),
        ("Marketing przy Kawie", "https://marketingprzykawie.pl/?s=przetarg"),
        ("eZamowienia BZP", "https://ezamowienia.gov.pl/mo-client-board/bzp/list"),
        ("eZamowienia MP", "https://ezamowienia.gov.pl/mp-client/search/list"),
        ("Brief4U", "https://brief4u.com/home"),
        ("Platforma Zakupowa", "https://platformazakupowa.pl/"),
        ("OnePlace Marketing/Reklama", "https://oneplace.marketplanet.pl/zapytania-ofertowe-przetargi/-/rfp/cat/11075/marketing-reklama-i-pr"),
        ("OWG Przetargi", "https://www.owg.pl/przetarg/zaawansowana/wynik?pageSize=100&typ_oglosz_410=checked&typ_oglosz_454=checked&zakup_sprzedaz_441=checked"),
        ("PZP24", "https://platformazakupowa.pzp24.pl/?filter%5Bbusiness_sector%5D=58"),
        ("Przetargi.info", "https://www.przetargi.info/"),
    ]

    for name, url in default_sources:
        try:
            conn.execute("INSERT OR IGNORE INTO sources (name, url) VALUES (?, ?)", (name, url))
        except sqlite3.IntegrityError:
            pass

    # Insert default keywords
    default_keywords = [
        "kampania marketingowa",
        "marketing",
        "usługi marketingowe",
        "social media",
        "reklama",
        "strategia komunikacji",
        "media planning",
        "kreacja",
        "branding",
        "PR",
    ]
    for kw in default_keywords:
        try:
            conn.execute("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (kw,))
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()


# --- Web Scraping ---

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
}


def scrape_page(url, keyword=None, timeout=15):
    """Scrape a single page for tender-related content."""
    results = []
    try:
        parsed = urlparse(url)

        # Build search URL if keyword is provided
        search_url = url
        if keyword:
            if 'nowymarketing.pl' in parsed.netloc:
                search_url = f"https://nowymarketing.pl/?s={quote_plus(keyword)}"
            elif 'wirtualnemedia.pl' in parsed.netloc:
                search_url = f"https://www.wirtualnemedia.pl/wyniki?zapytanie={quote_plus(keyword)}"
            elif 'marketingprzykawie.pl' in parsed.netloc:
                search_url = f"https://marketingprzykawie.pl/?s={quote_plus(keyword)}"
            elif 'press.pl' in parsed.netloc:
                search_url = f"https://www.press.pl/szukaj?q={quote_plus(keyword)}"
            elif 'mmponline.pl' in parsed.netloc:
                search_url = f"https://mmponline.pl/szukaj?q={quote_plus(keyword)}"
            elif 'platformazakupowa.pl' in parsed.netloc and 'pzp24' not in parsed.netloc:
                search_url = f"https://platformazakupowa.pl/all?search={quote_plus(keyword)}"
            elif 'oneplace.marketplanet.pl' in parsed.netloc:
                search_url = f"https://oneplace.marketplanet.pl/zapytania-ofertowe-przetargi?query={quote_plus(keyword)}"

        resp = requests.get(search_url, headers=HEADERS, timeout=timeout, verify=False)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')

        source_name = parsed.netloc.replace('www.', '')

        # Generic extraction - find article-like elements
        selectors = [
            'article', '.article', '.post', '.entry',
            '.search-result', '.result-item', '.tender-item',
            '.list-item', '.card', '.news-item',
            'h2 a', 'h3 a', '.title a',
        ]

        seen_titles = set()

        for selector in selectors:
            elements = soup.select(selector)
            for el in elements[:20]:
                title = None
                link = None
                snippet = None

                if el.name == 'a':
                    title = el.get_text(strip=True)
                    link = el.get('href', '')
                else:
                    # Try to find title within the element
                    title_el = el.select_one('h1, h2, h3, h4, .title, .name, a')
                    if title_el:
                        title = title_el.get_text(strip=True)
                        link_el = title_el if title_el.name == 'a' else title_el.find('a')
                        if link_el:
                            link = link_el.get('href', '')

                    # snippet
                    snippet_el = el.select_one('p, .excerpt, .description, .snippet, .summary')
                    if snippet_el:
                        snippet = snippet_el.get_text(strip=True)[:300]

                if not title or len(title) < 10:
                    continue

                if title in seen_titles:
                    continue
                seen_titles.add(title)

                # Make link absolute
                if link and not link.startswith('http'):
                    link = urljoin(search_url, link)

                # If keyword specified, check relevance
                if keyword:
                    text_to_check = (title + ' ' + (snippet or '')).lower()
                    kw_lower = keyword.lower()
                    kw_words = kw_lower.split()
                    if not any(w in text_to_check for w in kw_words):
                        continue

                results.append({
                    'title': title[:200],
                    'url': link or search_url,
                    'source_name': source_name,
                    'source_url': search_url,
                    'snippet': snippet or '',
                    'keyword': keyword or '',
                })

    except Exception as e:
        results.append({
            'title': f'[Błąd pobierania: {source_name if "source_name" in dir() else url}]',
            'url': url,
            'source_name': urlparse(url).netloc,
            'source_url': url,
            'snippet': str(e)[:200],
            'keyword': keyword or '',
            'error': True,
        })

    return results


# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')


# -- Bid Finder API --

@app.route('/api/sources', methods=['GET'])
def get_sources():
    conn = get_db()
    sources = conn.execute("SELECT * FROM sources ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(s) for s in sources])


@app.route('/api/sources', methods=['POST'])
def add_source():
    data = request.json
    name = data.get('name', '').strip()
    url = data.get('url', '').strip()
    if not name or not url:
        return jsonify({'error': 'Nazwa i URL są wymagane'}), 400
    conn = get_db()
    try:
        conn.execute("INSERT INTO sources (name, url) VALUES (?, ?)", (name, url))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'To źródło już istnieje'}), 400
    conn.close()
    return jsonify({'success': True})


@app.route('/api/sources/<int:source_id>', methods=['DELETE'])
def delete_source(source_id):
    conn = get_db()
    conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/sources/<int:source_id>/toggle', methods=['POST'])
def toggle_source(source_id):
    conn = get_db()
    conn.execute("UPDATE sources SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END WHERE id = ?", (source_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/keywords', methods=['GET'])
def get_keywords():
    conn = get_db()
    keywords = conn.execute("SELECT * FROM keywords ORDER BY keyword").fetchall()
    conn.close()
    return jsonify([dict(k) for k in keywords])


@app.route('/api/keywords', methods=['POST'])
def add_keyword():
    data = request.json
    keyword = data.get('keyword', '').strip()
    if not keyword:
        return jsonify({'error': 'Słowo kluczowe jest wymagane'}), 400
    conn = get_db()
    try:
        conn.execute("INSERT INTO keywords (keyword) VALUES (?)", (keyword,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'To słowo kluczowe już istnieje'}), 400
    conn.close()
    return jsonify({'success': True})


@app.route('/api/keywords/<int:kw_id>', methods=['DELETE'])
def delete_keyword(kw_id):
    conn = get_db()
    conn.execute("DELETE FROM keywords WHERE id = ?", (kw_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/search', methods=['POST'])
def search_tenders():
    """Search active sources for tenders matching keywords."""
    data = request.json
    keywords = data.get('keywords', [])
    source_ids = data.get('source_ids', [])

    conn = get_db()

    if source_ids:
        placeholders = ','.join('?' * len(source_ids))
        sources = conn.execute(
            f"SELECT * FROM sources WHERE id IN ({placeholders}) AND active = 1",
            source_ids
        ).fetchall()
    else:
        sources = conn.execute("SELECT * FROM sources WHERE active = 1").fetchall()

    conn.close()

    all_results = []

    for source in sources:
        if keywords:
            for kw in keywords:
                results = scrape_page(source['url'], keyword=kw)
                all_results.extend(results)
        else:
            results = scrape_page(source['url'])
            all_results.extend(results)

    # Deduplicate by title
    seen = set()
    unique_results = []
    for r in all_results:
        key = r['title'].lower().strip()
        if key not in seen and not r.get('error'):
            seen.add(key)
            unique_results.append(r)

    # Save results to DB
    conn = get_db()
    for r in unique_results:
        try:
            conn.execute(
                "INSERT INTO search_results (title, url, source_name, source_url, snippet, keyword) VALUES (?, ?, ?, ?, ?, ?)",
                (r['title'], r['url'], r['source_name'], r['source_url'], r['snippet'], r['keyword'])
            )
        except Exception:
            pass
    conn.commit()

    # Also return errors
    errors = [r for r in all_results if r.get('error')]

    conn.close()
    return jsonify({
        'results': unique_results,
        'errors': errors,
        'total': len(unique_results),
    })


@app.route('/api/search/history', methods=['GET'])
def search_history():
    conn = get_db()
    results = conn.execute(
        "SELECT * FROM search_results ORDER BY found_date DESC LIMIT 500"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in results])


@app.route('/api/search/history', methods=['DELETE'])
def clear_history():
    conn = get_db()
    conn.execute("DELETE FROM search_results")
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# -- Client Research API --

@app.route('/api/research', methods=['POST'])
def research_client():
    """Generate meeting prep material for a client."""
    data = request.json
    company = data.get('company', '').strip()
    email = data.get('email', '').strip()

    if not company:
        return jsonify({'error': 'Nazwa firmy jest wymagana'}), 400

    # Extract domain from email for additional research
    domain = ''
    if email and '@' in email:
        domain = email.split('@')[1]

    research = {
        'company': company,
        'email': email,
        'domain': domain,
        'sections': [],
    }

    # 1. Try to scrape company website
    if domain:
        try:
            resp = requests.get(f"https://{domain}", headers=HEADERS, timeout=10, verify=False)
            soup = BeautifulSoup(resp.text, 'lxml')

            # Get meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            desc = meta_desc['content'] if meta_desc and meta_desc.get('content') else ''

            # Get page title
            page_title = soup.title.string if soup.title else ''

            # Get main text content
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            body_text = soup.get_text(separator=' ', strip=True)[:2000]

            research['sections'].append({
                'title': 'Strona firmowa',
                'content': f"**{page_title}**\n\n{desc}\n\n{body_text[:1000]}",
            })
        except Exception as e:
            research['sections'].append({
                'title': 'Strona firmowa',
                'content': f"Nie udało się pobrać strony {domain}: {str(e)[:200]}",
            })

    # 2. Search for company info on various sources
    search_queries = [
        (f"{company} firma", "Informacje ogólne"),
        (f"{company} opinie pracownicy", "Opinie i kultura pracy"),
        (f"{company} klienci portfolio", "Portfolio i klienci"),
    ]

    for query, section_title in search_queries:
        try:
            # Use Google search
            search_url = f"https://www.google.com/search?q={quote_plus(query)}&hl=pl&num=5"
            resp = requests.get(search_url, headers=HEADERS, timeout=10, verify=False)
            soup = BeautifulSoup(resp.text, 'lxml')

            results_text = []
            for g in soup.select('.g, .tF2Cxc')[:5]:
                title_el = g.select_one('h3')
                snippet_el = g.select_one('.VwiC3b, .st, .IsZvec')
                link_el = g.select_one('a')
                if title_el:
                    title = title_el.get_text(strip=True)
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ''
                    link = link_el.get('href', '') if link_el else ''
                    results_text.append(f"- **{title}**: {snippet}")

            if results_text:
                research['sections'].append({
                    'title': section_title,
                    'content': '\n'.join(results_text),
                })
        except Exception:
            pass

    # 3. Check KRS / REGON (Polish business registry)
    try:
        krs_url = f"https://rejestr.io/s?q={quote_plus(company)}"
        resp = requests.get(krs_url, headers=HEADERS, timeout=10, verify=False)
        soup = BeautifulSoup(resp.text, 'lxml')
        krs_results = []
        for item in soup.select('.company-item, .search-result, a[href*="/krs/"]')[:3]:
            text = item.get_text(strip=True)
            if text and len(text) > 10:
                krs_results.append(f"- {text[:200]}")
        if krs_results:
            research['sections'].append({
                'title': 'Dane rejestrowe (KRS)',
                'content': '\n'.join(krs_results),
            })
    except Exception:
        pass

    # 4. Build meeting prep template
    research['sections'].append({
        'title': 'Szablon przygotowania do spotkania',
        'content': f"""## Karta klienta: {company}

### Podstawowe informacje
- **Firma:** {company}
- **Email kontaktowy:** {email or 'brak'}
- **Domena:** {domain or 'brak'}

### Przed spotkaniem - sprawdź:
1. Aktualne kampanie marketingowe firmy
2. Obecność w social media (Facebook, Instagram, LinkedIn, TikTok)
3. Ostatnie publikacje prasowe
4. Konkurencja w branży
5. Ewentualne przetargi/zapytania ofertowe

### Pytania do zadania na spotkaniu:
1. Jakie są główne cele biznesowe na najbliższy rok?
2. Jakie kanały komunikacji wykorzystują obecnie?
3. Jaki jest budżet marketingowy?
4. Kto jest grupą docelową?
5. Jakie były dotychczasowe doświadczenia z agencjami?
6. Jakie KPI są najważniejsze?

### Notatki ze spotkania:
_(uzupełnij po spotkaniu)_
""",
    })

    # Save to DB
    conn = get_db()
    conn.execute(
        "INSERT INTO client_research (company_name, email, research_data) VALUES (?, ?, ?)",
        (company, email, json.dumps(research, ensure_ascii=False))
    )
    conn.commit()
    conn.close()

    return jsonify(research)


@app.route('/api/research/history', methods=['GET'])
def research_history():
    conn = get_db()
    results = conn.execute(
        "SELECT id, company_name, email, created_at FROM client_research ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in results])


@app.route('/api/research/<int:research_id>', methods=['GET'])
def get_research(research_id):
    conn = get_db()
    result = conn.execute("SELECT * FROM client_research WHERE id = ?", (research_id,)).fetchone()
    conn.close()
    if not result:
        return jsonify({'error': 'Nie znaleziono'}), 404
    data = dict(result)
    data['research_data'] = json.loads(data['research_data'])
    return jsonify(data)


# -- CRM API --

@app.route('/api/crm', methods=['GET'])
def get_crm_tenders():
    conn = get_db()
    status_filter = request.args.get('status', '')
    if status_filter:
        tenders = conn.execute(
            "SELECT * FROM crm_tenders WHERE status = ? ORDER BY created_at DESC", (status_filter,)
        ).fetchall()
    else:
        tenders = conn.execute("SELECT * FROM crm_tenders ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(t) for t in tenders])


@app.route('/api/crm', methods=['POST'])
def add_crm_tender():
    data = request.json
    conn = get_db()
    conn.execute(
        """INSERT INTO crm_tenders (title, url, source, client, deadline, status, notes, priority, value)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data.get('title', ''),
            data.get('url', ''),
            data.get('source', ''),
            data.get('client', ''),
            data.get('deadline', ''),
            data.get('status', 'nowy'),
            data.get('notes', ''),
            data.get('priority', 'normalny'),
            data.get('value', ''),
        )
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/crm/<int:tender_id>', methods=['PUT'])
def update_crm_tender(tender_id):
    data = request.json
    conn = get_db()
    fields = []
    values = []
    for key in ['title', 'url', 'source', 'client', 'deadline', 'status', 'notes', 'priority', 'value']:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    fields.append("updated_at = datetime('now')")
    values.append(tender_id)
    conn.execute(f"UPDATE crm_tenders SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/crm/<int:tender_id>', methods=['DELETE'])
def delete_crm_tender(tender_id):
    conn = get_db()
    conn.execute("DELETE FROM crm_tenders WHERE id = ?", (tender_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/crm/stats', methods=['GET'])
def crm_stats():
    conn = get_db()
    stats = {}
    for status in ['nowy', 'w_analizie', 'oferta_wyslana', 'wygrana', 'przegrana', 'anulowany']:
        count = conn.execute("SELECT COUNT(*) FROM crm_tenders WHERE status = ?", (status,)).fetchone()[0]
        stats[status] = count
    stats['total'] = conn.execute("SELECT COUNT(*) FROM crm_tenders").fetchone()[0]
    conn.close()
    return jsonify(stats)


@app.route('/api/crm/add-from-search', methods=['POST'])
def add_from_search():
    """Add a search result directly to CRM."""
    data = request.json
    conn = get_db()
    conn.execute(
        """INSERT INTO crm_tenders (title, url, source, status, notes)
           VALUES (?, ?, ?, 'nowy', ?)""",
        (data.get('title', ''), data.get('url', ''), data.get('source_name', ''), data.get('snippet', ''))
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


if __name__ == '__main__':
    init_db()
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    app.run(debug=True, host='0.0.0.0', port=5000)
