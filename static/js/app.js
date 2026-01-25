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
    // Use pointer-events-none and transition only opacity for maximum speed
    toast.className = `fixed bottom-6 right-6 px-5 py-3 rounded-lg shadow-xl text-sm font-medium z-50 pointer-events-none transition-opacity duration-200 opacity-100 ${isError ? 'bg-red-600 text-white' : 'bg-green-600 text-white'}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Fast disappear: 800ms display + 200ms fade
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => { if (toast.parentNode) toast.remove(); }, 200);
    }, 800);
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
    loadSettings();
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
    const btn = document.getElementById(`btn-${tabId}`);
    document.querySelectorAll('.nav-btn').forEach(el => {
        el.classList.remove('bg-gray-700', 'text-white', 'shadow-md', 'shadow-gray-900/20');
        el.classList.add('text-gray-400', 'hover:bg-gray-700');
    });

    if (btn) {
        btn.classList.add('bg-gray-700', 'text-white', 'shadow-md', 'shadow-gray-900/20');
        btn.classList.remove('text-gray-400', 'hover:bg-gray-700');
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
        // Smart Scroll: Only scroll to bottom if user is already near the bottom
        const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 50;

        container.innerHTML = html;

        if (isAtBottom) {
            container.scrollTop = container.scrollHeight;
        }
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
function formatDateTime(dateStr) {
    if (!dateStr) return 'NULL';
    try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return 'NULL';
        const date = d.toLocaleDateString([], { month: '2-digit', day: '2-digit', year: 'numeric' });
        const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
        return `${date}<br>${time}`;
    } catch (e) {
        return 'NULL';
    }
}

async function loadHistory(offset = 0, manual = false) {
    historyOffset = offset;
    try {
        const res = await apiFetch(`/api/history?limit=${historyLimit}&offset=${historyOffset}`);
        const data = await res.json();
        const history = data.items;
        const total = data.total;

        const tbody = document.getElementById('history-table-body');
        tbody.innerHTML = history.map(row => `
            <tr class="hover:bg-gray-800 transition-colors border-b border-gray-700/50 last:border-0">
                <td class="px-6 py-4 font-medium text-white">${escapeHtml(row.title)}</td>
                <td class="px-6 py-4 text-gray-400">${escapeHtml(row.company)}</td>
                <td class="px-6 py-4">
                    <span class="inline-block px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wider whitespace-nowrap bg-red-900/40 text-red-300 border border-red-800/50">${escapeHtml(formatReason(row.reason))}</span>
                </td>
                <td class="px-6 py-4 text-gray-400 text-xs">${formatDateTime(row.listed_at)}</td>
                <td class="px-6 py-4 text-gray-400 text-xs">${formatDateTime(row.dismissed_at)}</td>
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
async function clearAllGeoCandidates() {
    if (!confirm('Are you sure you want to clear ALL discovered populated places? This cannot be undone.')) return;
    try {
        const res = await apiFetch('/api/geo_candidates', { method: 'DELETE' });
        if (res.ok) {
            showToast("All candidates cleared");
            loadGeoCache();
        } else {
            showToast("Failed to clear candidates", true);
        }
    } catch (e) {
        showToast("Error clearing candidates", true);
    }
}

async function clearGeoCandidate(ppId) {
    if (!confirm('Are you sure you want to clear this populated place?')) return;
    try {
        const res = await apiFetch(`/api/geo_candidate/${ppId}`, { method: 'DELETE' });
        if (res.ok) {
            showToast("Candidate cleared");
            loadGeoCache();
        } else {
            showToast("Failed to clear candidate", true);
        }
    } catch (e) {
        showToast("Error clearing candidate", true);
    }
}

async function loadGeoCache(manual = false) {
    try {
        const [cacheRes, candidatesRes] = await Promise.all([
            apiFetch('/api/geo_cache'),
            apiFetch('/api/geo_candidates')
        ]);
        const cache = await cacheRes.json();
        const candidates = await candidatesRes.json();

        // 1. GEO IDS Table
        const masterTbody = document.getElementById('master-geo-table-body');
        masterTbody.innerHTML = cache.map(row => {
            // Count candidates that have this master_id in their master_geo_id array
            const count = candidates.filter(cand =>
                Array.isArray(cand.master_geo_id) && cand.master_geo_id.includes(parseInt(row.master_id))
            ).length;

            return `
                <tr class="hover:bg-gray-800 transition-colors">
                    <td class="px-6 py-4 font-mono text-xs text-blue-300 font-medium">${escapeHtml(row.query)}</td>
                    <td class="px-6 py-4 text-xs font-mono text-gray-400">${escapeHtml(row.master_id)}</td>
                    <td class="px-6 py-4 text-xs font-mono text-gray-500">${count}</td>
                    <td class="px-6 py-4 space-x-3">
                        <button onclick="openCorrectionModal('${escapeHtml(row.query)}', '${row.master_id}')" class="text-blue-400 hover:text-blue-300 text-xs font-medium">Correct</button>
                        <button onclick="deleteGeoCacheEntry('${row.query}')" class="text-red-400 hover:text-red-300 text-xs font-medium">Delete</button>
                    </td>
                </tr>
            `;
        }).join('');

        // 2. POPULATED PLACES Table (Full Candidates List)
        const ppTbody = document.getElementById('pp-cache-table-body');

        if (candidates.length === 0) {
            ppTbody.innerHTML = '<tr><td colspan="6" class="px-6 py-8 text-center text-gray-500 italic">No candidates found. Run a search to discover places.</td></tr>';
        } else {
            // Group by pp_id to show unique places
            const groupedMap = new Map();
            candidates.forEach(cand => {
                if (!groupedMap.has(cand.pp_id)) {
                    groupedMap.set(cand.pp_id, {
                        ...cand,
                        master_ids: new Set([cand.master_geo_id])
                    });
                } else {
                    groupedMap.get(cand.pp_id).master_ids.add(cand.master_geo_id);
                }
            });

            const uniqueCandidates = Array.from(groupedMap.values());

            ppTbody.innerHTML = uniqueCandidates.map(cand => {
                const activeFor = cache.filter(c => c.pp_id === cand.pp_id).map(c => c.query).join(', ');
                const isActive = activeFor.length > 0;

                return `
                    <tr class="hover:bg-gray-800 transition-colors ${isActive ? 'border-l-2 border-green-500/50 bg-green-500/5' : ''}">
                        <td class="px-6 py-4 text-xs font-mono text-blue-400">${cand.pp_id}</td>
                        <td class="px-6 py-4 text-xs text-gray-300">
                            ${escapeHtml(cand.pp_name || 'N/A')}
                        </td>
                        <td class="px-6 py-4 text-xs text-white font-medium">${escapeHtml(cand.pp_corrected_name || 'N/A')}</td>
                        <td class="px-6 py-4 flex space-x-3">
                            <button onclick="openCandidateModal('${cand.pp_id}', '${escapeHtml(cand.pp_name)}', '${escapeHtml(cand.pp_corrected_name || '')}')" 
                                    class="text-blue-400 hover:text-blue-300 text-xs font-medium">Correct</button>
                            <button onclick="clearGeoCandidate(${cand.pp_id})" class="text-red-400 hover:text-red-300 text-xs font-medium">Clear</button>
                        </td>
                    </tr>
                `;
            }).join('');
        }
        if (manual) showToast("Location cache refreshed");
    } catch (e) {
        console.error("Failed to load geo cache", e);
        if (manual) showToast("Failed to refresh locations", true);
    }
}

// Candidate Correction Modal
let currentCandidatePpId = null;

function openCandidateModal(ppId, originalName, correctedName) {
    currentCandidatePpId = ppId;
    document.getElementById('candidate-id-display').textContent = ppId;
    document.getElementById('candidate-original-name').textContent = originalName;
    document.getElementById('candidate-corrected-name-input').value = correctedName || originalName;
    document.getElementById('modal-candidate-name-correction').classList.remove('hidden');
}

function closeCandidateModal() {
    document.getElementById('modal-candidate-name-correction').classList.add('hidden');
    currentCandidatePpId = null;
}

async function saveCandidateNameUpdate() {
    const correctedName = document.getElementById('candidate-corrected-name-input').value.trim();
    if (!correctedName) return showToast("Name cannot be empty", true);

    try {
        const res = await apiFetch('/api/geo_candidate/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pp_id: currentCandidatePpId, corrected_name: correctedName })
        });
        if (res.ok) {
            showToast("Candidate name updated");
            closeCandidateModal();
            loadGeoCache();
        }
    } catch (e) {
        showToast("Update failed", true);
    }
}

async function clearGeoOverride(ppId) {
    if (!confirm('Clear this override from all queries?')) return;
    try {
        const res = await apiFetch('/api/geo_cache');
        const cache = await res.json();
        const entries = cache.filter(c => c.pp_id === ppId);

        for (const entry of entries) {
            await apiFetch(`/api/geo_cache/${encodeURIComponent(entry.query)}`, { method: 'DELETE' });
        }
        showToast("Override cleared");
        loadGeoCache();
    } catch (e) {
        showToast("Clear failed", true);
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

        let listHtml = `
            <button onclick="applyGeoOverride('${query}', null)" 
                class="w-full text-left p-4 rounded-xl border border-dashed border-gray-700 hover:border-red-500 hover:bg-red-500/5 transition-all group mb-4">
                <div class="flex justify-between items-center">
                    <div>
                        <p class="text-gray-400 font-medium group-hover:text-red-400 transition-colors italic">Clear Choice (Use Regional Level)</p>
                    </div>
                    <svg class="w-5 h-5 text-gray-600 group-hover:text-red-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                    </svg>
                </div>
            </button>
        `;

        if (candidates.length === 0) {
            listEl.innerHTML = listHtml + '<p class="text-center py-4 text-red-400">No candidates found in cache. Run a fresh search first.</p>';
        } else {
            listEl.innerHTML = listHtml + candidates.map(c => `
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

// Settings
async function loadSettings() {
    try {
        const res = await apiFetch('/api/settings');
        const data = await res.json();

        const cookieInput = document.getElementById('linkedin-cookie');
        cookieInput.value = data.linkedin_cookie || '';

        // Delays
        if (data.page_delay !== undefined) document.getElementById('page-delay').value = data.page_delay;
        if (data.job_delay !== undefined) document.getElementById('job_delay').value = data.job_delay;

        if (data.updated_at) {
            document.getElementById('last-updated-row').classList.remove('hidden');
            document.getElementById('cookie-updated-at').textContent = new Date(data.updated_at).toLocaleString();
        }

        updateCookiePreview(data.has_cookie, data.cookie_preview);
    } catch (e) {
        console.error("Failed to load settings", e);
    }
}

function updateCookiePreview(hasCookie, preview) {
    const overlay = document.getElementById('cookie-overlay');
    const previewText = document.getElementById('cookie-preview-text');
    if (hasCookie) {
        previewText.textContent = `Cookie Set (${preview})`;
        previewText.classList.add('text-green-400');
        previewText.classList.remove('text-gray-400');
    } else {
        previewText.textContent = 'No Cookie Saved';
        previewText.classList.remove('text-green-400');
        previewText.classList.add('text-gray-400');
    }
}

async function saveSettings() {
    const pageDelay = parseFloat(document.getElementById('page-delay').value) || 2.0;
    const jobDelay = parseFloat(document.getElementById('job_delay').value) || 1.0;

    try {
        const res = await apiFetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                linkedin_cookie: cookie,
                page_delay: pageDelay,
                job_delay: jobDelay
            })
        });

        if (res.ok) {
            showToast("Settings saved successfully!");
            loadSettings();
        } else {
            showToast("Failed to save settings", true);
        }
    } catch (e) {
        showToast("Error saving settings", true);
    }
}

let cookieVisible = false;
function toggleCookieVisibility() {
    cookieVisible = !cookieVisible;
    const input = document.getElementById('linkedin-cookie');
    const overlay = document.getElementById('cookie-overlay');
    const btn = document.getElementById('toggle-cookie-btn');

    if (cookieVisible) {
        input.classList.remove('blur-sm');
        overlay.classList.add('opacity-0');
        btn.textContent = "Hide Cookie";
    } else {
        input.classList.add('blur-sm');
        overlay.classList.remove('opacity-0');
        btn.textContent = "Show Cookie";
    }
}

// Blocklist Validation
async function validateBlocklist(type) {
    const items = blocklistState[type];

    if (!items || items.length === 0) {
        showToast("Blocklist is empty", true);
        return;
    }

    try {
        const res = await apiFetch('/api/blocklist/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items })
        });
        const result = await res.json();
        showValidationResults(result);
    } catch (e) {
        showToast("Validation failed", true);
    }
}

function showValidationResults(result) {
    const container = document.getElementById('validation-results-content');
    let html = '';

    if (result.valid) {
        html = `
            <div class="bg-green-900/30 border border-green-800 p-6 rounded-xl text-center">
                <div class="inline-flex items-center justify-center w-12 h-12 bg-green-500/20 text-green-400 rounded-full mb-3">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                </div>
                <h4 class="text-green-400 font-bold text-lg">No Issues Found</h4>
                <p class="text-green-500/70 text-sm mt-1">Found ${result.total_items} items. No duplicates or whitespace issues detected.</p>
            </div>
        `;
    } else {
        if (result.duplicates.length > 0) {
            html += `
                <div class="space-y-3">
                    <h4 class="text-yellow-400 font-bold flex items-center text-sm uppercase tracking-wider">
                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.268 17c-.77 1.333.192 3 1.732 3z"></path>
                        </svg>
                        Duplicates (${result.duplicates.length})
                    </h4>
                    <div class="bg-gray-900 rounded-lg p-3 space-y-1.5 border border-yellow-900/30">
                        ${result.duplicates.slice(0, 10).map(d => `
                            <div class="flex justify-between text-xs">
                                <span class="text-gray-400 font-mono">Line ${d.index}:</span>
                                <span class="text-yellow-500 font-medium">${escapeHtml(d.value)}</span>
                            </div>
                        `).join('')}
                        ${result.duplicates.length > 10 ? `<div class="text-[10px] text-gray-500 italic pt-1">... and ${result.duplicates.length - 10} more</div>` : ''}
                    </div>
                </div>
            `;
        }

        if (result.whitespace_issues.length > 0) {
            html += `
                <div class="space-y-3">
                    <h4 class="text-blue-400 font-bold flex items-center text-sm uppercase tracking-wider">
                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 11c0 3.517-1.009 6.799-2.753 9.571m-3.44-2.04l.054-.09a10.116 10.116 0 001.202-2.31c.216-.605.516-1.185.894-1.725"/>
                        </svg>
                        Whitespace Issues (${result.whitespace_issues.length})
                    </h4>
                    <div class="bg-gray-900 rounded-lg p-3 space-y-1.5 border border-blue-900/30">
                        ${result.whitespace_issues.slice(0, 10).map(w => `
                            <div class="flex justify-between text-xs">
                                <span class="text-gray-400 font-mono">Line ${w.index}:</span>
                                <span class="text-blue-500 font-medium bg-blue-900/20 rounded-sm px-1">"${escapeHtml(w.value)}"</span>
                            </div>
                        `).join('')}
                        ${result.whitespace_issues.length > 10 ? `<div class="text-[10px] text-gray-500 italic pt-1">... and ${result.whitespace_issues.length - 10} more</div>` : ''}
                    </div>
                    <p class="text-[10px] text-gray-500 italic mt-1">Note: These entries have leading or trailing spaces that should be removed for exact matching.</p>
                </div>
            `;
        }
    }

    container.innerHTML = html;
    document.getElementById('validation-modal').classList.remove('hidden');
}

function closeValidationModal() {
    document.getElementById('validation-modal').classList.add('hidden');
}

// Export History
async function exportHistory() {
    try {
        const token = await authClient.getSessionToken();
        const url = `/api/history/export`;

        // Use a hidden anchor tag to trigger download with Auth header 
        // Or since it's a GET, we can just open in new tab if we put token in query?
        // Better: use fetch blob
        const res = await apiFetch(url);
        if (!res.ok) throw new Error("Export failed");

        const blob = await res.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `linkedin_history_export_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(downloadUrl);
        document.body.removeChild(a);

        showToast("History exported successfully!");
    } catch (e) {
        console.error(e);
        showToast("Export failed", true);
    }
}

function formatReason(reason) {
    if (!reason) return 'NULL';
    const map = {
        'job_title': 'Job Title',
        'company': 'Company',
        'applied': 'Applied',
        'title': 'Job Title' // unexpected case
    };
    return map[reason.toLowerCase()] || reason;
}

// Optimization Modal handlers
function closeOptimizationModal() {
    document.getElementById('optimization-modal').classList.add('hidden');
}

async function optimizeBlocklist(type) {
    const list = blocklistState[type];
    if (!list || list.length === 0) {
        showToast("Blocklist is empty", true);
        return;
    }

    let redundant = [];
    const sourceMap = {};

    const normalizeUrl = (url) => {
        if (!url) return "";
        return url.toLowerCase().trim()
            .replace(/^https?:\/\//, '') // remove protocol
            .replace(/\/$/, ''); // remove trailing slash
    };

    if (type === 'job_title') {
        // Redundant item: if A is a substring of B, B is redundant.
        const sorted = [...list].sort((a, b) => a.length - b.length);
        for (let i = 0; i < sorted.length; i++) {
            const broad = sorted[i].toLowerCase();
            for (let j = i + 1; j < sorted.length; j++) {
                const specific = sorted[j].toLowerCase();
                if (specific.includes(broad)) {
                    if (!redundant.includes(sorted[j])) {
                        redundant.push(sorted[j]);
                        sourceMap[sorted[j]] = `Covered by "${sorted[i]}"`;
                    }
                }
            }
        }
    } else if (type === 'company_linkedin') {
        // Unused item: if the company link is not in dismissal history, suggest removal
        try {
            const res = await apiFetch('/api/history/unique_companies');
            if (!res.ok) throw new Error("Failed to fetch unique company links");
            const historyLinks = await res.json();
            const historySet = new Set(historyLinks.map(l => normalizeUrl(l)));

            redundant = list.filter(link => {
                const norm = normalizeUrl(link);
                return norm !== "" && !historySet.has(norm);
            });
            redundant.forEach(link => {
                sourceMap[link] = "Not found in your history";
            });
        } catch (e) {
            console.error(e);
            showToast("Failed to check history", true);
            return;
        }
    }

    showOptimizationResults(type, redundant, sourceMap);
}

function showOptimizationResults(type, redundant, sourceMap) {
    const container = document.getElementById('optimization-results-content');
    const modal = document.getElementById('optimization-modal');
    const applyBtn = document.getElementById('apply-optimization-btn');

    const label = type === 'job_title' ? 'redundant' : 'unused';
    const description = type === 'job_title'
        ? 'redundant items that are already covered by broader keywords:'
        : 'items that have never been seen in your dismissal history:';

    if (redundant.length === 0) {
        container.innerHTML = `
            <div class="bg-green-900/30 border border-green-800 p-6 rounded-xl text-center">
                <div class="inline-flex items-center justify-center w-12 h-12 bg-green-500/20 text-green-400 rounded-full mb-3">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                </div>
                <h4 class="text-green-400 font-bold text-lg">Already Optimal</h4>
                <p class="text-green-500/70 text-sm mt-1">No ${label} keywords found in this list.</p>
            </div>
        `;
        applyBtn.classList.add('hidden');
    } else {
        container.innerHTML = `
            <div class="space-y-4">
                <div class="flex justify-between items-center">
                    <p class="text-sm text-gray-400">Found <span class="text-white font-bold">${redundant.length}</span> ${description}</p>
                    <label class="flex items-center space-x-2 cursor-pointer group">
                        <input type="checkbox" id="opt-select-all" class="custom-checkbox" onchange="toggleAllRedundant(this.checked)">
                        <span class="text-[10px] text-gray-500 uppercase font-bold tracking-widest group-hover:text-gray-300">Select All</span>
                    </label>
                </div>
                <div class="bg-gray-900 rounded-xl overflow-hidden border border-gray-700/50">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-gray-800 text-gray-400 uppercase font-bold tracking-wider">
                            <tr>
                                <th class="px-4 py-2 w-10"></th>
                                <th class="px-4 py-2">Item (To Remove)</th>
                                <th class="px-4 py-2">Reason</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-800 text-gray-300">
                            ${redundant.map((item, i) => `
                                <tr class="hover:bg-gray-800/40 transition-colors">
                                    <td class="px-4 py-2">
                                        <input type="checkbox" name="redundant-item" value="${escapeHtml(item)}" class="custom-checkbox opt-item-checkbox">
                                    </td>
                                    <td class="px-4 py-2 text-red-400 font-medium">${escapeHtml(item)}</td>
                                    <td class="px-4 py-2 text-green-400 font-medium text-xs">${escapeHtml(sourceMap[item])}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
                <p class="text-[10px] text-gray-500 italic mt-2">Note: Only checked items will be removed from your list.</p>
            </div>
        `;
        applyBtn.classList.remove('hidden');
        applyBtn.textContent = `Remove Selected Items`;
        applyBtn.onclick = () => {
            const checked = Array.from(document.querySelectorAll('input[name="redundant-item"]:checked')).map(cb => cb.value);
            if (checked.length === 0) return showToast("No items selected", true);

            blocklistState[type] = blocklistState[type].filter(item => !checked.includes(item));
            renderBlocklist(type);
            closeOptimizationModal();
            showToast(`Removed ${checked.length} items`);
        };
    }

    modal.classList.remove('hidden');
}

function toggleAllRedundant(checked) {
    document.querySelectorAll('.opt-item-checkbox').forEach(cb => cb.checked = checked);
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
