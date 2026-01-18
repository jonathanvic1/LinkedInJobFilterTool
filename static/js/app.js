// State
let isRunning = false;
let logInterval = null;
let historyOffset = 0;
let historyLimit = 50;

// Auth Fetch Helper
async function apiFetch(url, options = {}) {
    const token = await authClient.getSessionToken();
    if (!token && !url.includes('/api/auth/config')) {
        window.location.href = '/login';
        return;
    }

    const headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };

    const res = await fetch(url, { ...options, headers });

    if (res.status === 401) {
        window.location.href = '/login';
        return;
    }

    return res;
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    loadBlocklists();
    startStatusPolling();
});

// Tab Switching
// Tab Switching
function switchTab(tabId) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.add('hidden');
        el.classList.remove('flex');
    });

    // Show target tab
    const target = document.getElementById(tabId);
    if (target) {
        target.classList.remove('hidden');
        target.classList.add('flex');
    }

    // Update buttons
    document.querySelectorAll('.nav-btn').forEach(el => {
        el.classList.remove('bg-gray-700', 'text-white', 'shadow-md', 'shadow-gray-900/20');
        el.classList.add('text-gray-400', 'hover:bg-gray-700');
    });

    const btn = document.getElementById('btn-' + tabId);
    if (btn) {
        btn.classList.add('bg-gray-700', 'text-white', 'shadow-md', 'shadow-gray-900/20');
        btn.classList.remove('text-gray-400', 'hover:bg-gray-700'); // removed hover style to keep active state clean or keep it?
        // Actually keeping hover is fine, but usually active doesn't need hover bg change if it's already bg-gray-700
    }

    if (tabId === 'history') loadHistory();
    if (tabId === 'locations') loadGeoCache();
}

// API Interactions
async function loadConfig() {
    try {
        const res = await apiFetch('/api/config');
        const config = await res.json();

        document.getElementById('keywords').value = config.keywords || '';
        document.getElementById('location').value = config.location || 'Canada';
        document.getElementById('limit').value = config.limit || 25;

        // Map time_range string to select if needed
        const tr = document.getElementById('time_range');
        if (config.time_range) {
            // simplified mapping attempt
            if (config.time_range.includes('86400')) tr.value = '24h';
            else if (config.time_range.includes('604800')) tr.value = 'week';
            else if (config.time_range.includes('2592000')) tr.value = 'month';
            else tr.value = 'all';
        }

    } catch (e) {
        console.error("Failed to load config", e);
    }
}

async function startScraper() {
    const workplace_type = [];
    if (document.getElementById('wp_onsite').checked) workplace_type.push(1);
    if (document.getElementById('wp_remote').checked) workplace_type.push(2);
    if (document.getElementById('wp_hybrid').checked) workplace_type.push(3);

    const payload = {
        keywords: document.getElementById('keywords').value,
        location: document.getElementById('location').value,
        time_range: document.getElementById('time_range').value,
        limit: parseInt(document.getElementById('limit').value),
        easy_apply: document.getElementById('easy_apply').checked,
        relevant: document.getElementById('relevant').checked,
        workplace_type: workplace_type
    };

    try {
        const res = await apiFetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            alert('Error: ' + err.detail);
            return;
        }

        updateStatus(true);
        // Clear logs
        document.getElementById('logs').innerHTML = '';
    } catch (e) {
        alert("Failed to start scraper: " + e);
    }
}

async function stopScraper() {
    try {
        await apiFetch('/api/stop', { method: 'POST' });
        // Don't immediately set status false, let polling handle it
    } catch (e) {
        console.error("Stop failed", e);
    }
}

function startStatusPolling() {
    setInterval(async () => {
        try {
            const res = await apiFetch('/api/status');
            const data = await res.json();

            updateStatus(data.running);
            renderLogs(data.logs);

        } catch (e) {
            console.error("Polling error", e);
        }
    }, 1000);
}

function updateStatus(running) {
    isRunning = running;
    const indicator = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');

    if (running) {
        indicator.className = "w-2 h-2 rounded-full bg-green-500 animate-pulse";
        text.innerText = "Status: Running";
        text.className = "text-green-400";
        startBtn.classList.add('hidden');
        stopBtn.classList.remove('hidden');
    } else {
        indicator.className = "w-2 h-2 rounded-full bg-gray-500";
        text.innerText = "Status: Idle";
        text.className = "text-gray-400";
        startBtn.classList.remove('hidden');
        stopBtn.classList.add('hidden');
    }
}

function renderLogs(logs) {
    const container = document.getElementById('logs');
    // Simple diffing: just clear and append if length changed significantly or just strict replace?
    // For simplicity, just replace content.
    // Optimization: compare last log or timestamp.

    const html = logs.map(line => `<div class="break-words font-mono text-xs">${escapeHtml(line)}</div>`).join('');
    // Only update if changed
    if (container.innerHTML !== html) {
        container.innerHTML = html;
        container.scrollTop = container.scrollHeight;
    }
}

// Blocklists
async function loadBlocklists() {
    try {
        const [titles, companies] = await Promise.all([
            fetch('/api/blocklist?filename=blocklist.txt').then(r => r.json()),
            fetch('/api/blocklist?filename=blocklist_companies.txt').then(r => r.json())
        ]);

        document.getElementById('blocklist-titles').value = titles.content;
        document.getElementById('blocklist-companies').value = companies.content;
    } catch (e) { console.error(e); }
}

async function saveBlocklist(filename) {
    const id = filename === 'blocklist.txt' ? 'blocklist-titles' : 'blocklist-companies';
    const content = document.getElementById(id).value;

    try {
        await apiFetch('/api/blocklist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename, content })
        });
        alert('Blocked list saved!');
    } catch (e) { alert('Save failed'); }
}

// History
async function loadHistory(offset = 0) {
    historyOffset = offset;
    try {
        const res = await apiFetch(`/api/history?limit=${historyLimit}&offset=${historyOffset}`);
        const data = await res.json();
        const history = data.items;
        const total = data.total;

        const tbody = document.getElementById('history-table-body');
        tbody.innerHTML = history.map(row => `
            <tr class="hover:bg-gray-800 transition-colors">
                <td class="px-6 py-4 font-medium text-white">${escapeHtml(row.title)}</td>
                <td class="px-6 py-4 text-gray-400">${escapeHtml(row.company)}</td>
                <td class="px-6 py-4 text-xs">
                    <span class="px-2 py-1 rounded bg-red-900 text-red-200">${escapeHtml(formatReason(row.reason))}</span>
                </td>
                <td class="px-6 py-4 text-gray-500 text-xs">${new Date(row.date).toLocaleString()}</td>
                <td class="px-6 py-4">
                    <a href="${row.url}" target="_blank" class="text-blue-400 hover:text-blue-300 hover:underline text-xs">View Job</a>
                </td>
            </tr>
        `).join('');

        // Pagination Controls
        const paginationContainer = document.getElementById('history-pagination');
        if (paginationContainer) {
            const hasNext = (historyOffset + historyLimit) < total;
            const hasPrev = historyOffset > 0;

            paginationContainer.innerHTML = `
                <span class="text-sm text-gray-400 mr-4">
                    Showing ${historyOffset + 1}-${Math.min(historyOffset + historyLimit, total)} of ${total}
                </span>
                <div class="flex space-x-2">
                    <button onclick="loadHistory(${historyOffset - historyLimit})" ${!hasPrev ? 'disabled' : ''} 
                        class="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed text-white">
                        Previous
                    </button>
                    <button onclick="loadHistory(${historyOffset + historyLimit})" ${!hasNext ? 'disabled' : ''} 
                        class="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed text-white">
                        Next
                    </button>
                </div>
            `;
        }

    } catch (e) { console.error(e); }
}

// Locations (GeoID Cache)
async function loadGeoCache() {
    try {
        const res = await apiFetch('/api/config'); // Ensure config is synced
        const cacheRes = await apiFetch('/api/geo_cache');
        const cache = await cacheRes.json();

        // 1. Master GeoID Cache
        const masterTbody = document.getElementById('master-geo-table-body');
        masterTbody.innerHTML = cache.map(row => `
            <tr class="hover:bg-gray-800 transition-colors">
                <td class="px-6 py-4 font-mono text-xs text-blue-300 font-medium">${escapeHtml(row.query)}</td>
                <td class="px-6 py-4 text-xs font-mono text-gray-400">${escapeHtml(row.master_id)}</td>
                <td class="px-6 py-4">
                    <button onclick="deleteGeoCacheEntry('${row.query}')" class="text-red-400 hover:text-red-300 text-xs font-medium">Delete</button>
                </td>
            </tr>
        `).join('');

        // 2. Refined Place Cache (Only if pp_id exists)
        const ppTbody = document.getElementById('pp-cache-table-body');
        const refinedData = cache.filter(row => row.pp_id);

        if (refinedData.length === 0) {
            ppTbody.innerHTML = '<tr><td colspan="5" class="px-6 py-8 text-center text-gray-500 italic">No refined locations cached yet. Start a search to populate.</td></tr>';
        } else {
            ppTbody.innerHTML = refinedData.map(row => `
                <tr class="hover:bg-gray-800 transition-colors border-l-2 border-green-500/30">
                    <td class="px-6 py-4 font-mono text-xs text-blue-300 font-medium">${row.query}</td>
                    <td class="px-6 py-4 text-xs font-mono text-gray-500">${escapeHtml(row.master_id)}</td>
                    <td class="px-6 py-4 text-xs font-mono text-green-400">${escapeHtml(row.pp_id)}</td>
                    <td class="px-6 py-4 text-xs text-white font-medium">${escapeHtml(row.name)}</td>
                    <td class="px-6 py-4 flex space-x-3">
                        <button onclick="openCorrectionModal('${row.query}', '${row.master_id}')" class="text-blue-400 hover:text-blue-300 text-xs font-medium">Correct</button>
                        <button onclick="deleteGeoCacheEntry('${row.query}')" class="text-red-400 hover:text-red-300 text-xs font-medium">Clear</button>
                    </td>
                </tr>
            `).join('');
        }

    } catch (e) {
        console.error("Failed to load geo cache", e);
    }
}

async function deleteGeoCacheEntry(query) {
    if (!confirm('Are you sure you want to clear this cached location?')) return;
    try {
        await apiFetch(`/api/geo_cache/${encodeURIComponent(query)}`, {
            method: 'DELETE'
        });
        loadGeoCache();
    } catch (e) {
        alert('Failed to delete entry');
    }
}

// Geo Correction
async function openCorrectionModal(query, masterId) {
    const modal = document.getElementById('modal-geo-correction');
    const queryEl = document.getElementById('correction-query');
    const listEl = document.getElementById('geo-candidates-list');

    queryEl.innerText = query;
    listEl.innerHTML = '<p class="text-center py-4 text-gray-500 italic">Loading candidates...</p>';
    modal.classList.remove('hidden');

    try {
        const res = await apiFetch(`/api/geo_candidates/${masterId}`);
        const candidates = await res.json();

        if (candidates.length === 0) {
            listEl.innerHTML = '<p class="text-center py-4 text-red-400">No candidates found in cache. Run a fresh search first.</p>';
        } else {
            listEl.innerHTML = candidates.map(c => `
                <button onclick="applyGeoOverride('${query}', '${c.id}', '${c.name.replace(/'/g, "\\'")}')" 
                    class="w-full text-left p-4 rounded-xl border border-gray-700 hover:border-blue-500 hover:bg-blue-500/10 transition-all group">
                    <div class="flex justify-between items-center">
                        <span class="text-white font-medium group-hover:text-blue-300">${escapeHtml(c.name)}</span>
                        <span class="text-xs font-mono text-gray-500">${escapeHtml(c.id)}</span>
                    </div>
                </button>
            `).join('');
        }
    } catch (e) {
        listEl.innerHTML = '<p class="text-center py-4 text-red-500">Failed to load candidates.</p>';
    }
}

function closeGeoModal() {
    document.getElementById('modal-geo-correction').classList.add('hidden');
}

async function applyGeoOverride(query, ppId, ppName) {
    try {
        const res = await apiFetch('/api/geo_cache/override', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, pp_id: ppId, pp_name: ppName })
        });
        if (res.ok) {
            closeGeoModal();
            loadGeoCache();
        } else {
            throw new Error('Failed to apply override');
        }
    } catch (e) {
        alert(e.message);
    }
}

function formatReason(reason) {
    if (!reason) return 'Unknown';
    const map = {
        'job_title': 'Job Title',
        'company': 'Company',
        'applied': 'Applied',
        'title': 'Job Title' // unexpected case
    };
    return map[reason.toLowerCase()] || reason;
}

function escapeHtml(text) {
    if (!text) return '';
    return text.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
