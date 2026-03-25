// ==================== BID FINDER APP ====================

const API = {
    get: (url) => fetch(url).then(r => r.json()),
    post: (url, data) => fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(r => r.json()),
    put: (url, data) => fetch(url, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(r => r.json()),
    delete: (url) => fetch(url, {method: 'DELETE'}).then(r => r.json()),
};

// ==================== SOURCES ====================

let sources = [];
let keywords = [];

async function loadSources() {
    sources = await API.get('/api/sources');
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

async function addSource() {
    const name = document.getElementById('newSourceName').value.trim();
    const url = document.getElementById('newSourceUrl').value.trim();
    if (!name || !url) return alert('Wypelnij oba pola');
    const res = await API.post('/api/sources', {name, url});
    if (res.error) return alert(res.error);
    bootstrap.Modal.getInstance(document.getElementById('addSourceModal')).hide();
    document.getElementById('newSourceName').value = '';
    document.getElementById('newSourceUrl').value = '';
    loadSources();
}

async function deleteSource(id) {
    if (!confirm('Usunac to zrodlo?')) return;
    await API.delete(`/api/sources/${id}`);
    loadSources();
}

async function toggleSource(id) {
    await API.post(`/api/sources/${id}/toggle`);
    loadSources();
}

// ==================== KEYWORDS ====================

async function loadKeywords() {
    keywords = await API.get('/api/keywords');
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

async function addKeyword() {
    const keyword = document.getElementById('newKeyword').value.trim();
    if (!keyword) return alert('Wpisz slowo kluczowe');
    const res = await API.post('/api/keywords', {keyword});
    if (res.error) return alert(res.error);
    bootstrap.Modal.getInstance(document.getElementById('addKeywordModal')).hide();
    document.getElementById('newKeyword').value = '';
    loadKeywords();
}

async function deleteKeyword(id) {
    if (!confirm('Usunac to slowo kluczowe?')) return;
    await API.delete(`/api/keywords/${id}`);
    loadKeywords();
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

    btn.disabled = true;
    status.classList.remove('d-none');
    statusText.textContent = `Przeszukuje ${sources.filter(s => s.active).length} zrodel dla ${keywordList.length} fraz...`;

    try {
        const res = await API.post('/api/search', {keywords: keywordList});
        displaySearchResults(res);
    } catch (e) {
        document.getElementById('searchResults').innerHTML = `
            <div class="alert alert-danger">Blad wyszukiwania: ${e.message}</div>
        `;
    } finally {
        btn.disabled = false;
        status.classList.add('d-none');
    }
}

function displaySearchResults(data) {
    const container = document.getElementById('searchResults');

    if (data.results.length === 0) {
        container.innerHTML = `
            <div class="card">
                <div class="card-body text-center text-muted py-4">
                    <i class="bi bi-emoji-frown" style="font-size: 2rem;"></i>
                    <p class="mt-2">Nie znaleziono wynikow. Sprobuj innych fraz lub dodaj wiecej zrodel.</p>
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
        html += `
            <div class="result-card fade-in">
                <div class="result-title">
                    <a href="${escapeHtml(r.url)}" target="_blank">${escapeHtml(r.title)}</a>
                </div>
                <div class="result-meta">
                    <i class="bi bi-globe"></i> ${escapeHtml(r.source_name)}
                    ${r.keyword ? `&nbsp;|&nbsp;<i class="bi bi-tag"></i> ${escapeHtml(r.keyword)}` : ''}
                </div>
                ${r.snippet ? `<div class="result-snippet">${escapeHtml(r.snippet)}</div>` : ''}
                <div class="result-actions">
                    <button class="btn btn-sm btn-outline-primary" onclick='addToCRM(${JSON.stringify(r).replace(/'/g, "\\'")})'>
                        <i class="bi bi-plus-lg"></i> Dodaj do CRM
                    </button>
                    <a href="${escapeHtml(r.url)}" target="_blank" class="btn btn-sm btn-outline-secondary">
                        <i class="bi bi-box-arrow-up-right"></i> Otworz
                    </a>
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
}

async function addToCRM(result) {
    try {
        await API.post('/api/crm/add-from-search', result);
        alert('Dodano do CRM!');
    } catch (e) {
        alert('Blad: ' + e.message);
    }
}

async function loadSearchHistory() {
    const res = await API.get('/api/search/history');
    displaySearchResults({results: res, errors: []});
}

// ==================== CLIENT RESEARCH ====================

async function runResearch() {
    const company = document.getElementById('researchCompany').value.trim();
    const email = document.getElementById('researchEmail').value.trim();

    if (!company) return alert('Wpisz nazwe firmy');

    const btn = document.getElementById('researchBtn');
    const status = document.getElementById('researchStatus');

    btn.disabled = true;
    status.classList.remove('d-none');

    try {
        const res = await API.post('/api/research', {company, email});
        displayResearch(res);
        loadResearchHistory();
    } catch (e) {
        document.getElementById('researchResults').innerHTML = `
            <div class="alert alert-danger">Blad: ${e.message}</div>
        `;
    } finally {
        btn.disabled = false;
        status.classList.add('d-none');
    }
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

async function loadResearchHistory() {
    const res = await API.get('/api/research/history');
    const list = document.getElementById('researchHistory');

    if (res.length === 0) {
        list.innerHTML = '<div class="text-center p-3 text-muted">Brak historii</div>';
        return;
    }

    list.innerHTML = res.map(r => `
        <a href="#" class="list-group-item list-group-item-action" onclick="loadResearchDetail(${r.id})">
            <strong>${escapeHtml(r.company_name)}</strong>
            <br><small class="text-muted">${r.email || ''} | ${formatDate(r.created_at)}</small>
        </a>
    `).join('');
}

async function loadResearchDetail(id) {
    const res = await API.get(`/api/research/${id}`);
    displayResearch(res.research_data);
}

// ==================== CRM ====================

async function loadCRM() {
    const status = document.getElementById('crmStatusFilter').value;
    const url = status ? `/api/crm?status=${status}` : '/api/crm';
    const tenders = await API.get(url);
    const stats = await API.get('/api/crm/stats');

    // Update stats
    for (const [key, val] of Object.entries(stats)) {
        const el = document.getElementById(`stat-${key}`);
        if (el) el.textContent = val;
    }

    const container = document.getElementById('crmList');

    if (tenders.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="bi bi-inbox" style="font-size: 2rem;"></i>
                <p class="mt-2">Brak przetargow w CRM</p>
            </div>
        `;
        return;
    }

    container.innerHTML = tenders.map(t => `
        <div class="tender-row priority-${t.priority}" onclick="editTender(${t.id}, ${escapeAttr(JSON.stringify(t))})">
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
    `).join('');
}

async function addTender() {
    const data = {
        title: document.getElementById('tenderTitle').value,
        url: document.getElementById('tenderUrl').value,
        source: document.getElementById('tenderSource').value,
        client: document.getElementById('tenderClient').value,
        deadline: document.getElementById('tenderDeadline').value,
        status: document.getElementById('tenderStatus').value,
        priority: document.getElementById('tenderPriority').value,
        value: document.getElementById('tenderValue').value,
        notes: document.getElementById('tenderNotes').value,
    };

    if (!data.title) return alert('Tytul jest wymagany');

    await API.post('/api/crm', data);
    bootstrap.Modal.getInstance(document.getElementById('addTenderModal')).hide();

    // Clear form
    ['tenderTitle','tenderUrl','tenderSource','tenderClient','tenderDeadline','tenderValue','tenderNotes'].forEach(id => {
        document.getElementById(id).value = '';
    });

    loadCRM();
}

function editTender(id, tender) {
    document.getElementById('editTenderId').value = id;
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

async function updateTender() {
    const id = document.getElementById('editTenderId').value;
    const data = {
        title: document.getElementById('editTenderTitle').value,
        url: document.getElementById('editTenderUrl').value,
        source: document.getElementById('editTenderSource').value,
        client: document.getElementById('editTenderClient').value,
        deadline: document.getElementById('editTenderDeadline').value,
        status: document.getElementById('editTenderStatus').value,
        priority: document.getElementById('editTenderPriority').value,
        value: document.getElementById('editTenderValue').value,
        notes: document.getElementById('editTenderNotes').value,
    };

    await API.put(`/api/crm/${id}`, data);
    bootstrap.Modal.getInstance(document.getElementById('editTenderModal')).hide();
    loadCRM();
}

async function deleteTender() {
    const id = document.getElementById('editTenderId').value;
    if (!confirm('Na pewno usunac ten przetarg?')) return;
    await API.delete(`/api/crm/${id}`);
    bootstrap.Modal.getInstance(document.getElementById('editTenderModal')).hide();
    loadCRM();
}

// ==================== HELPERS ====================

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/'/g, '&#39;').replace(/"/g, '&quot;');
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
        return d.toLocaleDateString('pl-PL') + ' ' + d.toLocaleTimeString('pl-PL', {hour: '2-digit', minute: '2-digit'});
    } catch {
        return dateStr;
    }
}

function formatMarkdown(text) {
    if (!text) return '';
    // Simple markdown: bold, lists, headers, line breaks
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/^## (.*$)/gm, '<h6 class="mt-3">$1</h6>')
        .replace(/^### (.*$)/gm, '<h6 class="mt-2"><em>$1</em></h6>')
        .replace(/^- (.*$)/gm, '<li>$1</li>')
        .replace(/^(\d+)\. (.*$)/gm, '<li>$2</li>')
        .replace(/\n/g, '<br>')
        .replace(/_(.*?)_/g, '<em>$1</em>');
}

// ==================== INIT ====================

document.addEventListener('DOMContentLoaded', () => {
    loadSources();
    loadKeywords();
    loadResearchHistory();
    loadCRM();

    // Tab change handlers
    document.getElementById('crm-tab').addEventListener('shown.bs.tab', loadCRM);
    document.getElementById('research-tab').addEventListener('shown.bs.tab', loadResearchHistory);
});
