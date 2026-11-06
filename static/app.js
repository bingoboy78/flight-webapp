// ──── State ────
let airports = [];
let cities = [];

// ──── Helpers ────
function formatDate(year, month, day) {
    return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

function sanitizeDate(dateStr) {
    const match = dateStr.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (match) return `${match[1]}-${match[2]}-${match[3]}`;
    const parts = dateStr.split(/[\/\-.]/);
    if (parts.length === 3) {
        if (parts[0].length === 4) return `${parts[0]}-${parts[1].padStart(2,'0')}-${parts[2].padStart(2,'0')}`;
        return `${parts[2]}-${parts[1].padStart(2,'0')}-${parts[0].padStart(2,'0')}`;
    }
    return dateStr;
}

// ──── Init ────
document.addEventListener('DOMContentLoaded', async () => {
    if (localStorage.getItem('flighthub_auth') === 'ok') {
        document.getElementById('auth-screen').classList.remove('active');
        document.getElementById('app-screen').classList.add('active');
        await loadAirports();
        addCity();
    }

    document.getElementById('password-input').addEventListener('keydown', e => {
        if (e.key === 'Enter') login();
    });
});

// ──── Auth ────
async function login() {
    const pw = document.getElementById('password-input').value;
    try {
        const res = await fetch('/api/auth', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({password: pw})
        });
        if (res.ok) {
            localStorage.setItem('flighthub_auth', 'ok');
            document.getElementById('auth-screen').classList.remove('active');
            document.getElementById('app-screen').classList.add('active');
            await loadAirports();
            addCity();
        } else {
            document.getElementById('auth-error').textContent = 'Wrong password';
        }
    } catch (e) {
        document.getElementById('auth-error').textContent = 'Connection error';
    }
}

// ──── Airports ────
async function loadAirports() {
    try {
        const res = await fetch('/api/airports');
        airports = await res.json();
        populateHeatmapSelects();
    } catch (e) {
        console.error('Failed to load airports', e);
    }
}

function makeAirportSelect(selectedCode) {
    const sel = document.createElement('select');
    sel.className = 'city-select';
    airports.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.code;
        opt.textContent = `${a.code} — ${a.name}`;
        if (a.code === selectedCode) opt.selected = true;
        sel.appendChild(opt);
    });
    sel.addEventListener('change', updateLegs);
    return sel;
}

function populateHeatmapSelects() {
    ['hm-origin', 'hm-dest'].forEach(id => {
        const sel = document.getElementById(id);
        sel.innerHTML = '';
        airports.forEach(a => {
            const opt = document.createElement('option');
            opt.value = a.code;
            opt.textContent = `${a.code} — ${a.name}`;
            sel.appendChild(opt);
        });
    });
    document.getElementById('hm-dest').value = 'HKG';
}

// ──── Cities ────
function addCity() {
    const defaultCodes = ['HKG', 'SIN', 'BKK', 'NRT', 'ICN'];
    const code = defaultCodes[cities.length] || airports[1]?.code || 'HKG';
    cities.push(code);
    renderCities();
    updateLegs();
}

function removeCity(idx) {
    cities.splice(idx, 1);
    renderCities();
    updateLegs();
}

function renderCities() {
    const container = document.getElementById('cities-list');
    container.innerHTML = '';
    cities.forEach((code, i) => {
        const row = document.createElement('div');
        row.className = 'city-row';

        const num = document.createElement('span');
        num.className = 'city-num';
        num.textContent = i + 1;

        const sel = makeAirportSelect(code);
        sel.addEventListener('change', () => {
            cities[i] = sel.value;
            updateLegs();
        });

        const removeBtn = document.createElement('button');
        removeBtn.className = 'btn-remove';
        removeBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>';
        removeBtn.onclick = () => removeCity(i);

        row.appendChild(num);
        row.appendChild(sel);
        if (cities.length > 1) row.appendChild(removeBtn);
        container.appendChild(row);
    });
}

function updateLegs() {
    const route = ['TLV', ...cities, 'TLV'];
    const container = document.getElementById('legs-dates');
    container.innerHTML = '';

    for (let i = 0; i < route.length - 1; i++) {
        const row = document.createElement('div');
        row.className = 'leg-date-row';

        const label = document.createElement('span');
        label.className = 'leg-label';
        label.textContent = `${route[i]} → ${route[i + 1]}`;

        const input = document.createElement('input');
        input.type = 'date';
        input.className = 'leg-date-input';
        input.dataset.from = route[i];
        input.dataset.to = route[i + 1];

        const baseDay = 16 + i * 5;
        input.value = formatDate(2027, 1, baseDay);

        row.appendChild(label);
        row.appendChild(input);
        container.appendChild(row);
    }
}

// ──── Mode Toggle ────
function setMode(mode) {
    document.querySelectorAll('.mode-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.mode === mode);
    });
    document.getElementById('specific-fields').style.display = mode === 'specific' ? 'block' : 'none';
    document.getElementById('flexible-fields').style.display = mode === 'flexible' ? 'block' : 'none';
}

// ──── Tabs ────
function showTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');
    document.querySelector(`.nav-item[data-tab="${tab}"]`).classList.add('active');

    if (tab === 'history') loadHistory();
    if (tab === 'monitors') loadMonitors();
}

// ──── Search ────
async function startSearch() {
    const modeEl = document.querySelector('.mode-btn.active');
    const mode = modeEl ? modeEl.dataset.mode : 'specific';
    const directOnly = document.getElementById('direct-only').checked;

    let body = { mode, direct_only: directOnly, cities };

    if (mode === 'specific') {
        const legInputs = document.querySelectorAll('.leg-date-input');
        body.legs = Array.from(legInputs).map(inp => ({
            from: inp.dataset.from,
            to: inp.dataset.to,
            date: sanitizeDate(inp.value)
        }));
    } else {
        body.month = document.getElementById('flex-month').value;
        body.year = document.getElementById('flex-year').value;
        body.min_trip = document.getElementById('min-trip').value;
        body.max_trip = document.getElementById('max-trip').value;
        body.min_stay = document.getElementById('min-stay').value;
    }

    document.getElementById('search-btn').disabled = true;
    document.getElementById('progress-section').style.display = 'block';
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('results-section').innerHTML = '';

    try {
        const res = await fetch('/api/search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });
        const {task_id} = await res.json();
        streamProgress(task_id);
    } catch (e) {
        document.getElementById('search-btn').disabled = false;
        alert('Search failed: ' + e.message);
    }
}

function streamProgress(taskId) {
    const evtSource = new EventSource(`/api/search/stream/${taskId}`);
    evtSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        const pct = data.progress || 0;

        document.getElementById('progress-fill').style.width = pct + '%';
        document.getElementById('progress-pct').textContent = pct + '%';
        document.getElementById('progress-text').textContent =
            data.status === 'done' ? 'Complete!' :
            `Scanning leg ${data.current_step || '?'} of ${data.total_steps || '?'}...`;

        if (data.status === 'done') {
            evtSource.close();
            document.getElementById('search-btn').disabled = false;
            setTimeout(() => {
                document.getElementById('progress-section').style.display = 'none';
            }, 800);
            renderResults(data.results);
        }
    };
    evtSource.onerror = () => {
        evtSource.close();
        document.getElementById('search-btn').disabled = false;
    };
}

function renderResults(results) {
    const container = document.getElementById('results-section');
    container.style.display = 'block';

    if (!results || results.length === 0) {
        container.innerHTML = '<div class="empty-state">No flights found. Try different dates or disable "Direct flights only".</div>';
        return;
    }

    container.innerHTML = '<h2 class="results-header">Top results</h2>';

    results.forEach((combo, idx) => {
        const card = document.createElement('div');
        card.className = 'result-card';

        let legsHtml = '';
        (combo.legs || []).forEach(leg => {
            if (leg.error) {
                legsHtml += `<div class="leg-info"><span class="leg-route">${leg.from} → ${leg.to}</span><span class="leg-error">${leg.error}</span></div>`;
            } else {
                const stops = leg.stops === 0 ? 'Direct' : `${leg.stops} stop`;
                const airline = (leg.legs && leg.legs[0]) ? leg.legs[0].airline.replace('Airline.','') : '';
                const dur = `${Math.floor((leg.duration_min||0)/60)}h${(leg.duration_min||0)%60}m`;
                const legUrl = leg.booking_url || `https://www.google.com/travel/flights?q=Flights%20from%20${leg.from}%20to%20${leg.to}%20on%20${leg.date}`;
                legsHtml += `
                    <div class="leg-info">
                        <div>
                            <div class="leg-route">
                                ${leg.from} → ${leg.to} <span class="leg-date-tag">${leg.date}</span>
                                <a href="${legUrl}" target="_blank" rel="noopener noreferrer" class="leg-link" title="Open in Google Flights">Google Flights ↗</a>
                            </div>
                            <div class="leg-details">${airline} · ${stops} · ${dur}</div>
                        </div>
                        <span class="leg-price">$${(leg.price_usd||0).toLocaleString()}</span>
                    </div>`;
            }
        });

        const mainUrl = combo.booking_url || (combo.legs && combo.legs[0] ? combo.legs[0].booking_url : 'https://www.google.com/travel/flights');
        card.innerHTML = `
            <div class="result-top">
                <span class="result-rank">${idx + 1}</span>
                <span class="result-total">$${(combo.total_usd||0).toLocaleString()}</span>
                ${combo.days ? `<span class="result-days">${combo.days} days</span>` : ''}
            </div>
            <div class="result-breakdown">
                International $${(combo.international_usd||0).toLocaleString()} · Internal $${(combo.internal_usd||0).toLocaleString()}
            </div>
            <div class="result-legs">${legsHtml}</div>
            <div class="result-actions">
                <a href="${mainUrl}" target="_blank" rel="noopener noreferrer" class="btn-source">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/></svg>
                    Google Flights
                </a>
                <button class="btn-alert" onclick='setMonitor(${JSON.stringify(combo.legs).replace(/'/g, "&#39;")})'>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0"/></svg>
                    Track price
                </button>
            </div>`;

        container.appendChild(card);
    });
}

// ──── Monitor ────
async function setMonitor(legs) {
    try {
        const res = await fetch('/api/monitor', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({legs})
        });
        if (res.ok) {
            alert('Price alert set! You will receive Telegram notifications.');
        }
    } catch (e) {
        alert('Failed to set alert');
    }
}

async function loadMonitors() {
    try {
        const res = await fetch('/api/monitors');
        const monitors = await res.json();
        const list = document.getElementById('monitors-list');

        if (monitors.length === 0) {
            list.innerHTML = '<p class="empty-state">No active alerts. Search for flights and tap "Track price".</p>';
            return;
        }

        list.innerHTML = monitors.map(m => {
            const legs = m.route?.legs || [];
            const route = legs.map(l => l.from).concat(legs.length ? [legs[legs.length-1].to] : []).join(' → ');
            const dates = legs.length ? `${legs[0].date} — ${legs[legs.length-1].date}` : '';
            return `
                <div class="monitor-item">
                    <div>
                        <div class="monitor-route">${route}</div>
                        <div class="monitor-date">${dates}</div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 12px;">
                        ${m.last_price ? `<span class="monitor-price">$${m.last_price.toLocaleString()}</span>` : ''}
                        <button class="btn-danger" onclick="deleteMonitor('${m.id}')">Remove</button>
                    </div>
                </div>`;
        }).join('');
    } catch (e) {
        document.getElementById('monitors-list').innerHTML = '<p class="empty-state">Failed to load alerts.</p>';
    }
}

async function deleteMonitor(id) {
    await fetch(`/api/monitor/${id}`, {method: 'DELETE'});
    loadMonitors();
}

// ──── History ────
async function loadHistory() {
    try {
        const res = await fetch('/api/history');
        const items = await res.json();
        const list = document.getElementById('history-list');

        if (items.length === 0) {
            list.innerHTML = '<p class="empty-state">No searches yet</p>';
            return;
        }

        list.innerHTML = items.map(item => {
            const p = item.params;
            const citiesStr = p.cities ? ['TLV', ...p.cities, 'TLV'].join(' → ') : 'N/A';
            const bestPrice = item.results?.length ? `$${item.results[0].total_usd?.toLocaleString() || '?'}` : 'N/A';
            const date = new Date(item.created_at).toLocaleString();
            return `
                <div class="history-item" onclick="showHistoryDetail('${item.id}')">
                    <div class="history-route">${citiesStr}</div>
                    <div class="history-meta">${date} · ${p.mode || 'specific'} · <span class="history-price">${bestPrice}</span></div>
                </div>`;
        }).join('');
    } catch (e) {
        document.getElementById('history-list').innerHTML = '<p class="empty-state">Failed to load history.</p>';
    }
}

function showHistoryDetail(id) {
    fetch('/api/history').then(r => r.json()).then(items => {
        const item = items.find(i => i.id === id);
        if (item) {
            showTab('search');
            document.getElementById('results-section').style.display = 'block';
            renderResults(item.results);
        }
    });
}

// ──── Heatmap ────
async function startHeatmap() {
    const origin = document.getElementById('hm-origin').value;
    const dest = document.getElementById('hm-dest').value;
    const month = document.getElementById('hm-month').value;
    const year = document.getElementById('hm-year').value;

    document.getElementById('hm-progress').style.display = 'block';
    document.getElementById('heatmap-grid').style.display = 'none';

    try {
        const res = await fetch('/api/heatmap', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({origin, destination: dest, month, year})
        });
        const {task_id} = await res.json();

        const evtSource = new EventSource(`/api/search/stream/${task_id}`);
        evtSource.onmessage = (e) => {
            const data = JSON.parse(e.data);
            document.getElementById('hm-fill').style.width = (data.progress || 0) + '%';
            document.getElementById('hm-pct').textContent = (data.progress || 0) + '%';

            if (data.status === 'done') {
                evtSource.close();
                document.getElementById('hm-progress').style.display = 'none';
                renderHeatmap(data.results);
            }
        };
    } catch (e) {
        alert('Heatmap failed: ' + e.message);
    }
}

function renderHeatmap(data) {
    const grid = document.getElementById('heatmap-grid');
    grid.style.display = 'block';
    grid.innerHTML = `<div class="heatmap-title">${data.origin} → ${data.destination} · ${getMonthName(data.month)} ${data.year}</div>`;

    const prices = data.prices || {};
    const allPrices = Object.values(prices).map(p => p.price_usd);
    const minPrice = Math.min(...allPrices);
    const maxPrice = Math.max(...allPrices);

    const calendar = document.createElement('div');
    calendar.className = 'heatmap-calendar';

    ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].forEach(d => {
        const lbl = document.createElement('div');
        lbl.className = 'heatmap-day-label';
        lbl.textContent = d;
        calendar.appendChild(lbl);
    });

    const firstDay = new Date(data.year, data.month - 1, 1);
    let startDow = firstDay.getDay();
    startDow = startDow === 0 ? 6 : startDow - 1;

    for (let i = 0; i < startDow; i++) {
        const cell = document.createElement('div');
        cell.className = 'heatmap-cell empty';
        calendar.appendChild(cell);
    }

    const daysInMonth = new Date(data.year, data.month, 0).getDate();
    for (let d = 1; d <= daysInMonth; d++) {
        const dateStr = `${data.year}-${String(data.month).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        const cell = document.createElement('div');
        cell.className = 'heatmap-cell';

        if (prices[dateStr]) {
            const price = prices[dateStr].price_usd;
            const ratio = maxPrice > minPrice ? (price - minPrice) / (maxPrice - minPrice) : 0.5;
            cell.style.background = priceColor(ratio);
            cell.style.color = ratio > 0.6 ? '#fff' : '#0f172a';
            cell.innerHTML = `<span class="day-num">${d}</span><span class="day-price">$${price.toLocaleString()}</span>`;
        } else {
            cell.style.background = 'var(--bg-card)';
            cell.style.color = 'var(--text-muted)';
            cell.innerHTML = `<span class="day-num">${d}</span><span class="day-price">—</span>`;
        }

        calendar.appendChild(cell);
    }

    grid.appendChild(calendar);

    const legend = document.createElement('div');
    legend.className = 'heatmap-legend';
    legend.innerHTML = `<span>$${minPrice?.toLocaleString() || '?'}</span><div class="legend-bar"></div><span>$${maxPrice?.toLocaleString() || '?'}</span>`;
    grid.appendChild(legend);
}

function priceColor(ratio) {
    if (ratio < 0.5) {
        const r = Math.round(52 + (251 - 52) * (ratio * 2));
        const g = Math.round(211 + (191 - 211) * (ratio * 2));
        const b = Math.round(153 + (36 - 153) * (ratio * 2));
        return `rgb(${r}, ${g}, ${b})`;
    } else {
        const t = (ratio - 0.5) * 2;
        const r = Math.round(251 + (248 - 251) * t);
        const g = Math.round(191 + (113 - 191) * t);
        const b = Math.round(36 + (113 - 36) * t);
        return `rgb(${r}, ${g}, ${b})`;
    }
}

function getMonthName(m) {
    return ['', 'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'][m];
}
