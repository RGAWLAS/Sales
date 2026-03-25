// ==================== BID FINDER APP (Netlify/Static version) ====================
// All data stored in localStorage. Scraping via Netlify Functions.

// ==================== LOCAL STORAGE HELPERS ====================

function store(key, data) {
    localStorage.setItem('bf_' + key, JSON.stringify(data));
}

function load(key, fallback) {
    try {
        const data = localStorage.getItem('bf_' + key);
        return data ? JSON.parse(data) : fallback;
    } catch { return fallback; }
}

// ==================== DEFAULT DATA ====================

const DEFAULT_SOURCES = [
    { id: 1,  name: "Nowy Marketing", url: "https://nowymarketing.pl/?s=przetarg", active: true },
    { id: 2,  name: "MMP Online", url: "https://mmponline.pl/przetargi/", active: true },
    { id: 3,  name: "Wirtualne Media", url: "https://www.wirtualnemedia.pl/wyniki?zapytanie=przetarg", active: true },
    { id: 4,  name: "OnePlace MarketPlanet", url: "https://oneplace.marketplanet.pl/zapytania-ofertowe-przetargi/", active: true },
    { id: 5,  name: "Press.pl", url: "https://www.press.pl/tag/przetarg-publiczny", active: true },
    { id: 6,  name: "Marketing przy Kawie", url: "https://marketingprzykawie.pl/?s=przetarg", active: true },
    { id: 7,  name: "eZamowienia BZP", url: "https://ezamowienia.gov.pl/mo-client-board/bzp/list", active: true },
    { id: 8,  name: "eZamowienia MP", url: "https://ezamowienia.gov.pl/mp-client/search/list", active: true },
    { id: 9,  name: "Brief4U", url: "https://brief4u.com/home", active: true },
    { id: 10, name: "Platforma Zakupowa", url: "https://platformazakupowa.pl/", active: true },
    { id: 11, name: "OnePlace Marketing/Reklama", url: "https://oneplace.marketplanet.pl/zapytania-ofertowe-przetargi/-/rfp/cat/11075/marketing-reklama-i-pr", active: true },
    { id: 12, name: "OWG Przetargi", url: "https://www.owg.pl/przetarg/zaawansowana/wynik?pageSize=100&typ_oglosz_410=checked&typ_oglosz_454=checked&zakup_sprzedaz_441=checked", active: true },
    { id: 13, name: "PZP24", url: "https://platformazakupowa.pzp24.pl/?filter%5Bbusiness_sector%5D=58", active: true },
    { id: 14, name: "Przetargi.info", url: "https://www.przetargi.info/", active: true },
];

const DEFAULT_KEYWORDS = [
    { id: 1, keyword: "kampania marketingowa", active: true },
    { id: 2, keyword: "marketing", active: true },
    { id: 3, keyword: "uslugi marketingowe", active: true },
    { id: 4, keyword: "social media", active: true },
    { id: 5, keyword: "reklama", active: true },
    { id: 6, keyword: "strategia komunikacji", active: true },
    { id: 7, keyword: "media planning", active: true },
    { id: 8, keyword: "kreacja", active: true },
    { id: 9, keyword: "branding", active: true },
    { id: 10, keyword: "PR", active: true },
];

// ==================== STATE ====================

let sources = load('sources', null);
if (!sources) { sources = DEFAULT_SOURCES; store('sources', sources); }

let keywords = load('keywords', null);
if (!keywords) { keywords = DEFAULT_KEYWORDS; store('keywords', keywords); }

let searchHistory = load('searchHistory', []);
let crmTenders = load('crmTenders', []);
let researchHistory = load('researchHistory', []);

let nextSourceId = Math.max(0, ...sources.map(s => s.id)) + 1;
let nextKeywordId = Math.max(0, ...keywords.map(k => k.id)) + 1;
let nextTenderId = crmTenders.length > 0 ? Math.max(...crmTenders.map(t => t.id)) + 1 : 1;
let nextResearchId = researchHistory.length > 0 ? Math.max(...researchHistory.map(r => r.id)) + 1 : 1;

// ==================== SOURCES ====================

function renderSources() {
    const list = document.getElementById('sourcesList');
    if (sources.length === 0) {
        list.innerHTML = '<div class="text-center p-3 text-muted">Brak zrodel</div>';
        return;
    }
    list.innerHTML = sources.map(s => `
        <div class="source-item">
            <input class="form-check-input" type="checkbox" ${s.active ? 'checked' : ''}
                   onchange="toggleSource(${s.id})" title="Aktywne/Nieaktywne">
            <span class="source-name ms-2" title="${escapeHtml(s.url)}">${escapeHtml(s.name)}</span>
            <button class="btn btn-sm btn-delete text-danger" onclick="deleteSource(${s.id})" title="Usun">
                <i class="bi bi-x"></i>
            </button>
        </div>
    `).join('');
}

function addSource() {
    const name = document.getElementById('newSourceName').value.trim();
    const url = document.getElementById('newSourceUrl').value.trim();
    if (!name || !url) return alert('Wypelnij oba pola');
    if (sources.some(s => s.url === url)) return alert('To zrodlo juz istnieje');
    sources.push({ id: nextSourceId++, name, url, active: true });
    store('sources', sources);
    bootstrap.Modal.getInstance(document.getElementById('addSourceModal')).hide();
    document.getElementById('newSourceName').value = '';
    document.getElementById('newSourceUrl').value = '';
    renderSources();
}

function deleteSource(id) {
    if (!confirm('Usunac to zrodlo?')) return;
    sources = sources.filter(s => s.id !== id);
    store('sources', sources);
    renderSources();
}

function toggleSource(id) {
    const source = sources.find(s => s.id === id);
    if (source) source.active = !source.active;
    store('sources', sources);
    renderSources();
}

// ==================== KEYWORDS ====================

function renderKeywords() {
    const list = document.getElementById('keywordsList');
    if (keywords.length === 0) {
        list.innerHTML = '<div class="text-center p-3 text-muted">Brak slow kluczowych</div>';
        return;
    }
    list.innerHTML = keywords.map(k => `
        <div class="keyword-item">
            <span class="badge bg-secondary me-2">${escapeHtml(k.keyword)}</span>
            <button class="btn btn-sm btn-delete text-danger" onclick="deleteKeyword(${k.id})" title="Usun">
                <i class="bi bi-x"></i>
            </button>
        </div>
    `).join('');
}

function addKeyword() {
    const keyword = document.getElementById('newKeyword').value.trim();
    if (!keyword) return alert('Wpisz slowo kluczowe');
    if (keywords.some(k => k.keyword.toLowerCase() === keyword.toLowerCase())) return alert('To slowo kluczowe juz istnieje');
    keywords.push({ id: nextKeywordId++, keyword, active: true });
    store('keywords', keywords);
    bootstrap.Modal.getInstance(document.getElementById('addKeywordModal')).hide();
    document.getElementById('newKeyword').value = '';
    renderKeywords();
}

function deleteKeyword(id) {
    if (!confirm('Usunac to slowo kluczowe?')) return;
    keywords = keywords.filter(k => k.id !== id);
    store('keywords', keywords);
    renderKeywords();
}

// ==================== SEARCH ====================

async function runSearch() {
    const activeKeywords = keywords.filter(k => k.active).map(k => k.keyword);
    if (activeKeywords.length === 0) {
        alert('Dodaj przynajmniej jedno slowo kluczowe');
        return;
    }
    await executeSearch(activeKeywords);
}

async function runQuickSearch() {
    const input = document.getElementById('quickSearchInput').value.trim();
    if (!input) return;
    const kws = input.split(',').map(s => s.trim()).filter(s => s);
    await executeSearch(kws);
}

async function executeSearch(keywordList) {
    const btn = document.getElementById('searchBtn');
    const status = document.getElementById('searchStatus');
    const statusText = document.getElementById('searchStatusText');
    const activeSources = sources.filter(s => s.active);

    btn.disabled = true;
    status.classList.remove('d-none');

    const allResults = [];
    const errors = [];
    let completed = 0;
    const total = activeSources.length * keywordList.length;

    statusText.textContent = `Przeszukuje ${activeSources.length} zrodel dla ${keywordList.length} fraz... (0/${total})`;

    const tasks = [];
    for (const source of activeSources) {
        for (const kw of keywordList) {
            tasks.push({ source, kw });
        }
    }

    const concurrency = 3;
    let taskIndex = 0;

    async function processNext() {
        while (taskIndex < tasks.length) {
            const idx = taskIndex++;
            const { source, kw } = tasks[idx];
            try {
                const resp = await fetch('/.netlify/functions/scrape', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: source.url, keyword: kw }),
                });
                const data = await resp.json();
                if (data.results) allResults.push(...data.results);
                if (data.error) errors.push({ source: source.name, error: data.error });
            } catch (err) {
                errors.push({ source: source.name, error: err.message });
            }
            completed++;
            statusText.textContent = `Przeszukuje zrodla... (${completed}/${total})`;
        }
    }

    const workers = [];
    for (let i = 0; i < concurrency; i++) {
        workers.push(processNext());
    }
    await Promise.all(workers);

    const seen = new Set();
    const uniqueResults = [];
    for (const r of allResults) {
        const key = r.title.toLowerCase().trim();
        if (!seen.has(key)) {
            seen.add(key);
            r.found_date = new Date().toISOString();
            uniqueResults.push(r);
        }
    }

    searchHistory = [...uniqueResults, ...searchHistory].slice(0, 500);
    store('searchHistory', searchHistory);

    displaySearchResults({ results: uniqueResults, errors });

    btn.disabled = false;
    status.classList.add('d-none');
}

function displaySearchResults(data) {
    const container = document.getElementById('searchResults');

    if (data.results.length === 0) {
        container.innerHTML = `
            <div class="card">
                <div class="card-body text-center text-muted py-4">
                    <i class="bi bi-emoji-frown" style="font-size: 2rem;"></i>
                    <p class="mt-2">Nie znaleziono wynikow. Sprobuj innych fraz lub dodaj wiecej zrodel.</p>
                    ${data.errors.length > 0 ? `<p class="text-warning"><small>${data.errors.length} zrodel zwrocilo bledy</small></p>` : ''}
                </div>
            </div>
        `;
        return;
    }

    let html = `
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h6 class="mb-0">Znaleziono: <strong>${data.results.length}</strong> wynikow</h6>
            ${data.errors.length > 0 ? `<span class="badge bg-warning">${data.errors.length} bledow</span>` : ''}
        </div>
    `;

    for (const r of data.results) {
        const rJson = JSON.stringify(r).replace(/&/g, '&amp;').replace(/'/g, '&#39;').replace(/"/g, '&quot;');
        html += `
            <div class="result-card fade-in">
                <div class="result-title">
                    <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">${escapeHtml(r.title)}</a>
                </div>
                <div class="result-meta">
                    <i class="bi bi-globe"></i> ${escapeHtml(r.source_name)}
                    ${r.keyword ? `&nbsp;|&nbsp;<i class="bi bi-tag"></i> ${escapeHtml(r.keyword)}` : ''}
                </div>
                ${r.snippet ? `<div class="result-snippet">${escapeHtml(r.snippet)}</div>` : ''}
                <div class="result-actions">
                    <button class="btn btn-sm btn-outline-primary" onclick="addToCRM(${rJson})">
                        <i class="bi bi-plus-lg"></i> Dodaj do CRM
                    </button>
                    <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener" class="btn btn-sm btn-outline-secondary">
                        <i class="bi bi-box-arrow-up-right"></i> Otworz
                    </a>
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
}

function addToCRM(result) {
    crmTenders.push({
        id: nextTenderId++,
        title: result.title,
        url: result.url,
        source: result.source_name,
        client: '',
        deadline: '',
        status: 'nowy',
        notes: result.snippet || '',
        priority: 'normalny',
        value: '',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
    });
    store('crmTenders', crmTenders);
    alert('Dodano do CRM!');
}

function loadSearchHistory() {
    displaySearchResults({ results: searchHistory, errors: [] });
}

function clearSearchHistory() {
    if (!confirm('Wyczysc cala historie wyszukiwan?')) return;
    searchHistory = [];
    store('searchHistory', searchHistory);
    document.getElementById('searchResults').innerHTML = `
        <div class="card"><div class="card-body text-center text-muted py-5">
            <i class="bi bi-binoculars" style="font-size: 3rem;"></i>
            <p class="mt-3">Historia wyczyszczona</p>
        </div></div>
    `;
}

// ==================== CLIENT RESEARCH ====================

async function runResearch() {
    const company = document.getElementById('researchCompany').value.trim();
    const email = document.getElementById('researchEmail').value.trim();

    if (!company) return alert('Wpisz nazwe firmy');

    const btn = document.getElementById('researchBtn');
    const statusEl = document.getElementById('researchStatus');

    btn.disabled = true;
    statusEl.classList.remove('d-none');

    const domain = email && email.includes('@') ? email.split('@')[1] : '';

    const research = {
        id: nextResearchId++,
        company,
        email,
        domain,
        sections: [],
        created_at: new Date().toISOString(),
    };

    if (domain) {
        try {
            const resp = await fetch('/.netlify/functions/research', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ domain }),
            });
            const data = await resp.json();

            if (data.title || data.description || data.text) {
                let content = '';
                if (data.title) content += `**${data.title}**\n\n`;
                if (data.description) content += `${data.description}\n\n`;
                if (data.text) content += data.text.substring(0, 1000);
                research.sections.push({ title: 'Strona firmowa', content });
            }

            if (data.socialMedia && data.socialMedia.length > 0) {
                const smContent = data.socialMedia.map(sm => `- **${sm.name}**: ${sm.url}`).join('\n');
                research.sections.push({ title: 'Social Media', content: smContent });
            }

            if (data.error) {
                research.sections.push({
                    title: 'Strona firmowa',
                    content: `Nie udalo sie pobrac strony ${domain}: ${data.error}`,
                });
            }
        } catch (err) {
            research.sections.push({
                title: 'Strona firmowa',
                content: `Blad pobierania strony: ${err.message}`,
            });
        }
    }

    research.sections.push({
        title: 'Szablon przygotowania do spotkania',
        content: `## Karta klienta: ${company}\n\n### Podstawowe informacje\n- **Firma:** ${company}\n- **Email kontaktowy:** ${email || 'brak'}\n- **Domena:** ${domain || 'brak'}\n\n### Przed spotkaniem - sprawdz:\n1. Aktualne kampanie marketingowe firmy\n2. Obecnosc w social media (Facebook, Instagram, LinkedIn, TikTok)\n3. Ostatnie publikacje prasowe\n4. Konkurencja w branzy\n5. Ewentualne przetargi/zapytania ofertowe\n\n### Pytania do zadania na spotkaniu:\n1. Jakie sa glowne cele biznesowe na najblizszy rok?\n2. Jakie kanaly komunikacji wykorzystuja obecnie?\n3. Jaki jest budzet marketingowy?\n4. Kto jest grupa docelowa?\n5. Jakie byly dotychczasowe doswiadczenia z agencjami?\n6. Jakie KPI sa najwazniejsze?\n\n### Przydatne linki do sprawdzenia:\n- Google: https://www.google.com/search?q=${encodeURIComponent(company)}\n- LinkedIn: https://www.linkedin.com/search/results/companies/?keywords=${encodeURIComponent(company)}\n- KRS: https://rejestr.io/s?q=${encodeURIComponent(company)}\n- Panorama Firm: https://panoramafirm.pl/szukaj?k=${encodeURIComponent(company)}\n\n### Notatki ze spotkania:\n_(uzupelnij po spotkaniu)_`,
    });

    researchHistory = [research, ...researchHistory].slice(0, 50);
    store('researchHistory', researchHistory);

    displayResearch(research);
    renderResearchHistory();

    btn.disabled = false;
    statusEl.classList.add('d-none');
}

function displayResearch(data) {
    const container = document.getElementById('researchResults');

    let html = `
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h5 class="mb-0"><i class="bi bi-building"></i> ${escapeHtml(data.company)}</h5>
            ${data.email ? `<span class="badge bg-secondary">${escapeHtml(data.email)}</span>` : ''}
        </div>
    `;

    for (const section of data.sections) {
        html += `
            <div class="research-section fade-in">
                <h5><i class="bi bi-info-circle"></i> ${escapeHtml(section.title)}</h5>
                <div class="research-content">${formatMarkdown(section.content)}</div>
            </div>
        `;
    }

    container.innerHTML = html;
}

function renderResearchHistory() {
    const list = document.getElementById('researchHistory');

    if (researchHistory.length === 0) {
        list.innerHTML = '<div class="text-center p-3 text-muted">Brak historii</div>';
        return;
    }

    list.innerHTML = researchHistory.map(r => `
        <a href="#" class="list-group-item list-group-item-action" onclick="loadResearchDetail(${r.id}); return false;">
            <strong>${escapeHtml(r.company)}</strong>
            <br><small class="text-muted">${r.email || ''} | ${formatDate(r.created_at)}</small>
        </a>
    `).join('');
}

function loadResearchDetail(id) {
    const research = researchHistory.find(r => r.id === id);
    if (research) displayResearch(research);
}

// ==================== CRM ====================

function renderCRM() {
    const statusFilter = document.getElementById('crmStatusFilter').value;

    const statuses = ['nowy', 'w_analizie', 'oferta_wyslana', 'wygrana', 'przegrana', 'anulowany'];
    for (const s of statuses) {
        const el = document.getElementById(`stat-${s}`);
        if (el) el.textContent = crmTenders.filter(t => t.status === s).length;
    }
    const totalEl = document.getElementById('stat-total');
    if (totalEl) totalEl.textContent = crmTenders.length;

    let filtered = crmTenders;
    if (statusFilter) filtered = crmTenders.filter(t => t.status === statusFilter);
    filtered.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));

    const container = document.getElementById('crmList');

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="bi bi-inbox" style="font-size: 2rem;"></i>
                <p class="mt-2">Brak przetargow w CRM</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map(t => {
        const tJson = JSON.stringify(t).replace(/&/g, '&amp;').replace(/'/g, '&#39;').replace(/"/g, '&quot;');
        return `
        <div class="tender-row priority-${t.priority}" onclick="editTenderFromCRM(${tJson})">
            <div class="row align-items-center">
                <div class="col-md-5">
                    <strong>${escapeHtml(t.title)}</strong>
                    ${t.client ? `<br><small class="text-muted"><i class="bi bi-building"></i> ${escapeHtml(t.client)}</small>` : ''}
                </div>
                <div class="col-md-2">
                    <span class="status-badge status-${t.status}">${statusLabel(t.status)}</span>
                </div>
                <div class="col-md-2">
                    ${t.deadline ? `<small><i class="bi bi-calendar"></i> ${t.deadline}</small>` : '<small class="text-muted">brak terminu</small>'}
                </div>
                <div class="col-md-2">
                    ${t.value ? `<small><i class="bi bi-cash"></i> ${escapeHtml(t.value)}</small>` : ''}
                </div>
                <div class="col-md-1 text-end">
                    <small class="text-muted">${escapeHtml(t.source || '')}</small>
                </div>
            </div>
        </div>
    `;
    }).join('');
}

function addTender() {
    const data = {
        id: nextTenderId++,
        title: document.getElementById('tenderTitle').value,
        url: document.getElementById('tenderUrl').value,
        source: document.getElementById('tenderSource').value,
        client: document.getElementById('tenderClient').value,
        deadline: document.getElementById('tenderDeadline').value,
        status: document.getElementById('tenderStatus').value,
        priority: document.getElementById('tenderPriority').value,
        value: document.getElementById('tenderValue').value,
        notes: document.getElementById('tenderNotes').value,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
    };

    if (!data.title) return alert('Tytul jest wymagany');

    crmTenders.push(data);
    store('crmTenders', crmTenders);
    bootstrap.Modal.getInstance(document.getElementById('addTenderModal')).hide();

    ['tenderTitle','tenderUrl','tenderSource','tenderClient','tenderDeadline','tenderValue','tenderNotes'].forEach(id => {
        document.getElementById(id).value = '';
    });

    renderCRM();
}

function editTenderFromCRM(tender) {
    document.getElementById('editTenderId').value = tender.id;
    document.getElementById('editTenderTitle').value = tender.title || '';
    document.getElementById('editTenderUrl').value = tender.url || '';
    document.getElementById('editTenderSource').value = tender.source || '';
    document.getElementById('editTenderClient').value = tender.client || '';
    document.getElementById('editTenderDeadline').value = tender.deadline || '';
    document.getElementById('editTenderStatus').value = tender.status || 'nowy';
    document.getElementById('editTenderPriority').value = tender.priority || 'normalny';
    document.getElementById('editTenderValue').value = tender.value || '';
    document.getElementById('editTenderNotes').value = tender.notes || '';

    new bootstrap.Modal(document.getElementById('editTenderModal')).show();
}

function updateTender() {
    const id = parseInt(document.getElementById('editTenderId').value);
    const tender = crmTenders.find(t => t.id === id);
    if (!tender) return;

    tender.title = document.getElementById('editTenderTitle').value;
    tender.url = document.getElementById('editTenderUrl').value;
    tender.source = document.getElementById('editTenderSource').value;
    tender.client = document.getElementById('editTenderClient').value;
    tender.deadline = document.getElementById('editTenderDeadline').value;
    tender.status = document.getElementById('editTenderStatus').value;
    tender.priority = document.getElementById('editTenderPriority').value;
    tender.value = document.getElementById('editTenderValue').value;
    tender.notes = document.getElementById('editTenderNotes').value;
    tender.updated_at = new Date().toISOString();

    store('crmTenders', crmTenders);
    bootstrap.Modal.getInstance(document.getElementById('editTenderModal')).hide();
    renderCRM();
}

function deleteTender() {
    const id = parseInt(document.getElementById('editTenderId').value);
    if (!confirm('Na pewno usunac ten przetarg?')) return;
    crmTenders = crmTenders.filter(t => t.id !== id);
    store('crmTenders', crmTenders);
    bootstrap.Modal.getInstance(document.getElementById('editTenderModal')).hide();
    renderCRM();
}

function exportCRM() {
    if (crmTenders.length === 0) return alert('Brak danych do eksportu');

    const headers = ['Tytul', 'URL', 'Zrodlo', 'Klient', 'Termin', 'Status', 'Priorytet', 'Wartosc', 'Notatki', 'Data dodania'];
    const rows = crmTenders.map(t => [
        t.title, t.url, t.source, t.client, t.deadline,
        statusLabel(t.status), t.priority, t.value, t.notes, t.created_at
    ]);

    let csv = headers.join(';') + '\n';
    for (const row of rows) {
        csv += row.map(v => `"${(v || '').replace(/"/g, '""')}"`).join(';') + '\n';
    }

    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `crm_przetargi_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
}

// ==================== HELPERS ====================

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function statusLabel(status) {
    const labels = {
        'nowy': 'Nowy',
        'w_analizie': 'W analizie',
        'oferta_wyslana': 'Oferta wyslana',
        'wygrana': 'Wygrana',
        'przegrana': 'Przegrana',
        'anulowany': 'Anulowany',
    };
    return labels[status] || status;
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString('pl-PL') + ' ' + d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
    } catch { return dateStr; }
}

function formatMarkdown(text) {
    if (!text) return '';
    return text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/^## (.*$)/gm, '<h6 class="mt-3">$1</h6>')
        .replace(/^### (.*$)/gm, '<h6 class="mt-2"><em>$1</em></h6>')
        .replace(/^- (.*$)/gm, '<li>$1</li>')
        .replace(/^(\d+)\. (.*$)/gm, '<li>$2</li>')
        .replace(/\n/g, '<br>')
        .replace(/_(.*?)_/g, '<em>$1</em>')
        .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
}

// ==================== INIT ====================

document.addEventListener('DOMContentLoaded', () => {
    renderSources();
    renderKeywords();
    renderResearchHistory();
    renderCRM();

    document.getElementById('crm-tab').addEventListener('shown.bs.tab', renderCRM);
    document.getElementById('research-tab').addEventListener('shown.bs.tab', renderResearchHistory);
});
