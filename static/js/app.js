// State
let isRunning = false;
let logInterval = null;
let historyOffset = 0;
let historyLimit = 50;

// Toast Notification
function showToast(message, isError = false) {
    const existing = document.getElementById('toast-notification');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'toast-notification';
    toast.className = `fixed bottom-6 right-6 px-5 py-3 rounded-lg shadow-xl text-sm font-medium z-50 transition-all duration-300 transform translate-y-0 opacity-100 ${isError ? 'bg-red-600 text-white' : 'bg-green-600 text-white'}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.replace('translate-y-0', 'translate-y-4');
        toast.classList.replace('opacity-100', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, 1500);
}

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
    loadHistory();
    loadGeoCache();
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

    if (btn) {
        btn.classList.add('bg-gray-700', 'text-white', 'shadow-md', 'shadow-gray-900/20');
        btn.classList.remove('text-gray-400', 'hover:bg-gray-700'); // removed hover style to keep active state clean or keep it?
        // Actually keeping hover is fine, but usually active doesn't need hover bg change if it's already bg-gray-700
    }
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
            if (config.time_range.includes('1800')) tr.value = '30m';
            else if (config.time_range.includes('3600')) tr.value = '1h';
            else if (config.time_range.includes('28800')) tr.value = '8h';
            else if (config.time_range.includes('86400')) tr.value = '24h';
            else if (config.time_range.includes('172800')) tr.value = '2d';
            else if (config.time_range.includes('259200')) tr.value = '3d';
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

// Blocklists State
let blocklistState = {
    job_title: [],
    company_linkedin: []
};

async function loadBlocklists(manual = false) {
    try {
        const [titles, companies] = await Promise.all([
            apiFetch('/api/blocklist?filename=blocklist.txt').then(r => r.json()),
            apiFetch('/api/blocklist?filename=blocklist_companies.txt').then(r => r.json())
        ]);

        blocklistState.job_title = titles.content.split('\n').filter(l => l.trim());
        blocklistState.company_linkedin = companies.content.split('\n').filter(l => l.trim());

        renderBlocklist('job_title');
        renderBlocklist('company_linkedin');
        if (manual) showToast("Blocklists refreshed");
    } catch (e) {
        console.error("Failed to load blocklists", e);
        if (manual) showToast("Failed to refresh blocklists", true);
    }
}

function renderBlocklist(type) {
    const list = blocklistState[type];
    const containerId = type === 'job_title' ? 'titles-list-container' : 'companies-list-container';
    const searchId = type === 'job_title' ? 'search-title-input' : 'search-company-input';
    const countId = type === 'job_title' ? 'title-count' : 'company-count';
    const container = document.getElementById(containerId);
    if (!container) return;

    // Update count badge
    const countEl = document.getElementById(countId);
    if (countEl) countEl.textContent = list.length;

    const searchTerm = document.getElementById(searchId).value.toLowerCase();
    const filtered = list.filter(item => item.toLowerCase().includes(searchTerm));

    if (filtered.length === 0) {
        container.innerHTML = `<div class="text-center py-10 text-gray-700 italic text-xs">No items found${searchTerm ? ' matching search' : ''}</div>`;
        return;
    }


    container.innerHTML = filtered.map((item, index) => {
        // Find original index in state for deletion/edit
        const originalIndex = list.indexOf(item);
        return `
            <div class="group flex items-center justify-between px-3 py-1.5 hover:bg-gray-800/50 rounded-lg transition-all border border-transparent hover:border-gray-700/50">
                <input type="text" value="${escapeHtml(item)}" 
                    onchange="editBlocklistItem('${type}', ${originalIndex}, this.value)"
                    class="bg-transparent border-none text-gray-300 text-sm focus:outline-none focus:ring-0 w-full mr-2 py-0">
                <button onclick="removeBlocklistItem('${type}', ${originalIndex})" 
                    class="opacity-0 group-hover:opacity-100 p-1 text-gray-500 hover:text-red-400 transition-all">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                </button>
            </div>
        `;
    }).join('');
}

function addBlocklistItem(type) {
    const inputId = type === 'job_title' ? 'add-title-input' : 'add-company-input';
    const input = document.getElementById(inputId);
    const value = input.value.trim();

    if (value && !blocklistState[type].includes(value)) {
        blocklistState[type].unshift(value); // Add to top
        input.value = '';
        renderBlocklist(type);
    }
}

function removeBlocklistItem(type, index) {
    blocklistState[type].splice(index, 1);
    renderBlocklist(type);
}

function editBlocklistItem(type, index, newValue) {
    if (newValue.trim()) {
        blocklistState[type][index] = newValue.trim();
    } else {
        removeBlocklistItem(type, index);
    }
}

async function saveBlocklist(type) {
    const content = blocklistState[type].join('\n');
    const filename = type === 'job_title' ? 'blocklist.txt' : 'blocklist_companies.txt';

    try {
        const res = await apiFetch('/api/blocklist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename, content })
        });
        if (res.ok) {
            showToast(`${type === 'job_title' ? 'Job titles' : 'Companies'} saved successfully!`);
        } else {
            throw new Error('Save failed');
        }
    } catch (e) {
        showToast('Failed to save changes', true);
    }
}

// History
async function loadHistory(offset = 0, manual = false) {
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
                    <a href="https://www.linkedin.com/jobs/view/${row.job_id}" target="_blank" class="text-blue-400 hover:text-blue-300 hover:underline text-xs">View Job</a>
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
        if (manual && offset === 0) showToast("History refreshed");
    } catch (e) {
        console.error(e);
        if (manual) showToast("Failed to refresh history", true);
    }
}

// Locations (GeoID Cache)
async function loadGeoCache(manual = false) {
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
                <td class="px-6 py-4 text-xs font-mono text-gray-500">${row.place_count || 0}</td>
                <td class="px-6 py-4">
                    <button onclick="deleteGeoCacheEntry('${row.query}')" class="text-red-400 hover:text-red-300 text-xs font-medium">Delete</button>
                </td>
            </tr>
        `).join('');

        // 2. Refined Place Cache (Only if pp_id exists)
        const ppTbody = document.getElementById('pp-cache-table-body');
        const refinedData = cache.filter(row => row.pp_id);

        if (refinedData.length === 0) {
            ppTbody.innerHTML = '<tr><td colspan="6" class="px-6 py-8 text-center text-gray-500 italic">No refined locations cached yet. Start a search to populate.</td></tr>';
        } else {
            ppTbody.innerHTML = refinedData.map(row => `
                <tr class="hover:bg-gray-800 transition-colors border-l-2 border-green-500/30">
                    <td class="px-6 py-4 font-mono text-xs text-blue-300 font-medium">${row.query}</td>
                    <td class="px-6 py-4 text-xs font-mono text-gray-500">${escapeHtml(row.master_id)}</td>
                    <td class="px-6 py-4 text-xs font-mono text-green-400 font-semibold">${escapeHtml(row.pp_id)}</td>
                    <td class="px-6 py-4 text-xs text-gray-300">${escapeHtml(row.pp_name || 'N/A')}</td>
                    <td class="px-6 py-4 text-xs text-white font-medium">${escapeHtml(row.pp_corrected_name || 'N/A')}</td>
                    <td class="px-6 py-4 flex space-x-3">
                        <button onclick="openCorrectionModal('${row.query}', '${row.master_id}')" class="text-blue-400 hover:text-blue-300 text-xs font-medium">Correct</button>
                        <button onclick="deleteGeoCacheEntry('${row.query}')" class="text-red-400 hover:text-red-300 text-xs font-medium">Clear</button>
                    </td>
                </tr>
            `).join('');
        }
        if (manual) showToast("Location cache refreshed");
    } catch (e) {
        console.error("Failed to load geo cache", e);
        if (manual) showToast("Failed to refresh locations", true);
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
                <button onclick="applyGeoOverride('${query}', '${c.id}')" 
                    class="w-full text-left p-4 rounded-xl border border-gray-700 hover:border-blue-500 hover:bg-blue-500/10 transition-all group">
                    <div class="flex justify-between items-center">
                        <span class="text-white font-medium group-hover:text-blue-300">${escapeHtml(c.corrected_name || c.name)}</span>
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

async function applyGeoOverride(query, ppId) {
    try {
        const res = await apiFetch('/api/geo_cache/override', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, pp_id: ppId })
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
