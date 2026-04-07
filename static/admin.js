let map;
let userMarkers = {};

// Color palette for deterministic avatar colors
const AVATAR_COLORS = ['#667eea', '#f093fb', '#4facfe', '#43e97b', '#fa709a', '#fee140', '#a18cd1', '#fda085'];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    try {
        // Initialize map centered at [20, 0], zoom 2
        map = L.map('map').setView([20, 0], 2);

        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(map);

        // Load locations and zones immediately
        loadLocations();
        loadZonesTable();
        redrawZoneCircles();
        loadAIStatus();
        loadAllUsers();

        // Auto-refresh locations every 10 seconds
        setInterval(loadLocations, 10000);
    } catch (error) {
        console.error('Error initializing admin panel:', error);
    }
});

function loadLocations() {
    try {
        fetch('/api/admin/locations')
            .then(response => {
                if (!response.ok) throw new Error('API error: ' + response.status);
                return response.json();
            })
            .then(locations => {
                if (!locations || !Array.isArray(locations)) {
                    console.warn('Invalid locations data');
                    return;
                }

                // Update markers on map
                const seenUserIds = new Set();
                locations.forEach(location => {
                    seenUserIds.add(location.user_id);
                    const lat = location.lat || 40.7128;
                    const lng = location.lng || -74.0060;
                    const isAnomaly = location.is_anomaly || false;

                    if (!userMarkers[location.user_id]) {
                        // Create new marker
                        const icon = isAnomaly
                            ? L.divIcon({
                                className: 'anomaly-marker',
                                html: '<div></div>',
                                iconSize: [16, 16],
                                iconAnchor: [8, 8]
                            })
                            : L.icon({ iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png', iconSize: [25, 41] });

                        const popupHTML = `<b>👤 ${location.name}</b><br/>
                            📍 ${lat.toFixed(4)}, ${lng.toFixed(4)}<br/>
                            🕐 ${location.timestamp ? new Date(location.timestamp).toLocaleString() : 'No data'}<br/>
                            <span class="${isAnomaly ? 'anomaly-badge' : 'normal-badge'}">${isAnomaly ? '🔴 Anomaly' : '🟢 Normal'}</span>`;

                        const marker = L.marker([lat, lng], { icon })
                            .bindPopup(popupHTML)
                            .addTo(map);

                        userMarkers[location.user_id] = { marker, isAnomaly };
                    } else {
                        // Update existing marker
                        userMarkers[location.user_id].marker.setLatLng([lat, lng]);
                        userMarkers[location.user_id].isAnomaly = isAnomaly;
                    }
                });

                // Remove markers for users not in current list
                Object.keys(userMarkers).forEach(userId => {
                    if (!seenUserIds.has(parseInt(userId))) {
                        map.removeLayer(userMarkers[userId].marker);
                        delete userMarkers[userId];
                    }
                });

                // Update sidebar
                updateUsersSidebar(locations);

                // Update stats
                updateStatsBar(locations);
                
                // Update anomaly count
                updateAnomalyCount(locations);

                // Flash refresh badge
                flashRefreshBadge();
            })
            .catch(error => console.error('Error loading locations:', error));
    } catch (error) {
        console.error('Error in loadLocations:', error);
    }
}

function loadZones() {
    try {
        fetch('/api/zones')
            .then(response => {
                if (!response.ok) throw new Error('API error: ' + response.status);
                return response.json();
            })
            .then(zones => {
                if (!zones || !Array.isArray(zones)) {
                    console.warn('Invalid zones data');
                    return;
                }

                zones.forEach(zone => {
                    const colorMap = {
                        red: { color: '#ff4757', fill: '#ff4757' },
                        yellow: { color: '#ffa502', fill: '#ffa502' },
                        green: { color: '#2ed573', fill: '#2ed573' }
                    };

                    const colors = colorMap[zone.type] || { color: '#cccccc', fill: '#cccccc' };

                    L.circle([zone.lat, zone.lng], {
                        radius: zone.radius * 1000,
                        color: colors.color,
                        fillColor: colors.fill,
                        fillOpacity: 0.2,
                        weight: 2
                    })
                        .bindTooltip(`${zone.name} (${zone.type})`)
                        .addTo(map);
                });
            })
            .catch(error => console.error('Error loading zones:', error));
    } catch (error) {
        console.error('Error in loadZones:', error);
    }
}

function updateUsersSidebar(locations) {
    try {
        const userList = document.getElementById('user-list');
        if (!userList) return;

        if (locations.length === 0) {
            userList.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🗺️</div><div class="empty-state-text">No active users</div></div>';
            return;
        }

        userList.innerHTML = locations.map(location => {
            const initials = getInitials(location.name);
            const avatarColor = getAvatarColor(location.name);
            const isAnomaly = location.is_anomaly || false;
            const timeAgoStr = timeAgo(new Date(location.timestamp));

            return `
                <div class="user-card">
                    <div class="avatar" style="background: ${avatarColor};">${initials}</div>
                    <div class="user-info">
                        <div class="user-name">${location.name}</div>
                        <div class="user-email">${location.name}</div>
                        <div class="user-time">${timeAgoStr}</div>
                    </div>
                    <div class="status-badge ${isAnomaly ? 'anomaly' : 'normal'}">
                        ${isAnomaly ? '🔴 Anomaly' : '🟢 Normal'}
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error updating sidebar:', error);
    }
}

function updateStatsBar(locations) {
    try {
        const totalEl = document.getElementById('stat-total');
        const activeEl = document.getElementById('stat-active');
        const anomaliesEl = document.getElementById('stat-anomalies');

        const total = locations.length;
        const active = locations.filter(l => l.timestamp && (Date.now() - new Date(l.timestamp).getTime()) < 5 * 60 * 1000).length;
        const anomalies = locations.filter(l => l.is_anomaly).length;

        if (totalEl) totalEl.textContent = total;
        if (activeEl) activeEl.textContent = active;
        if (anomaliesEl) anomaliesEl.textContent = anomalies;
    } catch (error) {
        console.error('Error updating stats:', error);
    }
}

function getInitials(name) {
    return name.split(' ').map(word => word[0]).join('').toUpperCase().substring(0, 2);
}

function getAvatarColor(name) {
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = ((hash << 5) - hash) + name.charCodeAt(i);
        hash = hash & hash;
    }
    const index = Math.abs(hash) % AVATAR_COLORS.length;
    return AVATAR_COLORS[index];
}

function timeAgo(date) {
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return Math.floor(seconds / 60) + ' mins ago';
    if (seconds < 86400) return Math.floor(seconds / 3600) + ' hour' + (Math.floor(seconds / 3600) > 1 ? 's' : '') + ' ago';
    return Math.floor(seconds / 86400) + ' day' + (Math.floor(seconds / 86400) > 1 ? 's' : '') + ' ago';
}

function flashRefreshBadge() {
    try {
        const badge = document.getElementById('refresh-badge');
        if (badge) {
            badge.classList.add('flash');
            setTimeout(() => badge.classList.remove('flash'), 1000);
        }
    } catch (error) {
        console.error('Error flashing badge:', error);
    }
}

// Add styles for anomaly marker
const style = document.createElement('style');
style.textContent = `
    .anomaly-marker {
        width: 16px;
        height: 16px;
        background: #ff4757;
        border-radius: 50%;
        box-shadow: 0 0 0 0 rgba(255, 71, 87, 0.7);
        animation: anomalyPulse 1.5s infinite;
    }

    @keyframes anomalyPulse {
        0% { box-shadow: 0 0 0 0 rgba(255, 71, 87, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(255, 71, 87, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 71, 87, 0); }
    }

    .normal-badge {
        background: #1a3a2a;
        color: #2ed573;
        border: 1px solid #2ed573;
        border-radius: 50px;
        padding: 3px 10px;
        font-size: 11px;
        display: inline-block;
        font-weight: 600;
    }

    .anomaly-badge {
        background: #3a1a1a;
        color: #ff4757;
        border: 1px solid #ff4757;
        border-radius: 50px;
        padding: 3px 10px;
        font-size: 11px;
        display: inline-block;
        font-weight: 600;
    }
`;
document.head.appendChild(style);

// ============ ZONE MANAGEMENT ============
let zoneMapLayers = [];
let editingZoneId = null;
let selectedZoneType = null;

function toggleZoneForm() {
    const form = document.getElementById('zone-form');
    const toggle = document.querySelector('.zone-toggle');
    const table = document.getElementById('zone-table');
    
    form.classList.toggle('visible');
    toggle.classList.toggle('collapsed');
    
    if (form.classList.contains('visible')) {
        renderZonesTable();
    }
}

function selectZoneType(type) {
    selectedZoneType = type;
    document.querySelectorAll('.zone-type-btn').forEach(btn => {
        btn.classList.remove('selected');
    });
    document.querySelector(`[data-type="${type}"]`).classList.add('selected');
}

function resetZoneForm() {
    document.getElementById('zone-name').value = '';
    document.getElementById('zone-lat').value = '';
    document.getElementById('zone-lng').value = '';
    document.getElementById('zone-radius').value = '';
    selectedZoneType = null;
    editingZoneId = null;
    document.getElementById('zone-mode-label').textContent = '➕ New Zone';
    document.getElementById('zone-btn-cancel').classList.remove('visible');
    document.querySelectorAll('.zone-type-btn').forEach(btn => btn.classList.remove('selected'));
}

function editZone(zone) {
    editingZoneId = zone.id;
    document.getElementById('zone-name').value = zone.name;
    document.getElementById('zone-lat').value = zone.lat;
    document.getElementById('zone-lng').value = zone.lng;
    document.getElementById('zone-radius').value = zone.radius;
    selectedZoneType = zone.type;
    
    document.querySelectorAll('.zone-type-btn').forEach(btn => {
        btn.classList.remove('selected');
    });
    document.querySelector(`[data-type="${zone.type}"]`).classList.add('selected');
    
    document.getElementById('zone-mode-label').textContent = `✏️ Editing: ${zone.name}`;
    document.getElementById('zone-btn-cancel').classList.add('visible');
    
    // Ensure form is visible
    const form = document.getElementById('zone-form');
    if (!form.classList.contains('visible')) {
        toggleZoneForm();
    }
    
    // Scroll to form
    form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function cancelZoneEdit() {
    resetZoneForm();
}

function saveZone() {
    const name = document.getElementById('zone-name').value.trim();
    const lat = parseFloat(document.getElementById('zone-lat').value);
    const lng = parseFloat(document.getElementById('zone-lng').value);
    const radius = parseFloat(document.getElementById('zone-radius').value);
    const type = selectedZoneType;
    
    if (!name || isNaN(lat) || isNaN(lng) || isNaN(radius) || !type) {
        alert('Please fill in all fields');
        return;
    }
    
    if (radius <= 0) {
        alert('Radius must be greater than 0');
        return;
    }
    
    const data = { name, lat, lng, radius, type };
    
    if (editingZoneId) {
        // Update existing zone
        fetch(`/api/admin/zones/${editingZoneId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
            .then(response => {
                if (!response.ok) throw new Error('API error: ' + response.status);
                return response.json();
            })
            .then(zone => {
                loadZonesTable();
                redrawZoneCircles();
                resetZoneForm();
                alert('Zone updated successfully');
            })
            .catch(error => {
                console.error('Error updating zone:', error);
                alert('Failed to update zone');
            });
    } else {
        // Create new zone
        fetch('/api/admin/zones', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
            .then(response => {
                if (!response.ok) throw new Error('API error: ' + response.status);
                return response.json();
            })
            .then(zone => {
                loadZonesTable();
                redrawZoneCircles();
                resetZoneForm();
                alert('Zone created successfully');
            })
            .catch(error => {
                console.error('Error creating zone:', error);
                alert('Failed to create zone');
            });
    }
}

function deleteZone(zone) {
    if (!confirm(`Delete zone "${zone.name}"?`)) return;
    
    fetch(`/api/admin/zones/${zone.id}`, {
        method: 'DELETE'
    })
        .then(response => {
            if (!response.ok) throw new Error('API error: ' + response.status);
            return response.json();
        })
        .then(result => {
            loadZonesTable();
            redrawZoneCircles();
            alert('Zone deleted successfully');
        })
        .catch(error => {
            console.error('Error deleting zone:', error);
            alert('Failed to delete zone');
        });
}

function loadZonesTable() {
    try {
        fetch('/api/zones')
            .then(response => {
                if (!response.ok) throw new Error('API error: ' + response.status);
                return response.json();
            })
            .then(zones => {
                renderZonesTable(zones);
            })
            .catch(error => console.error('Error loading zones:', error));
    } catch (error) {
        console.error('Error in loadZonesTable:', error);
    }
}

function renderZonesTable(zones = []) {
    const tableBody = document.getElementById('zone-table-body');
    const table = document.getElementById('zone-table');
    const emptyState = document.getElementById('zone-empty-state');
    
    if (!zones || zones.length === 0) {
        tableBody.innerHTML = '';
        table.classList.remove('visible');
        emptyState.style.display = 'block';
        return;
    }
    
    table.classList.add('visible');
    emptyState.style.display = 'none';
    
    tableBody.innerHTML = zones.map(zone => `
        <div class="zone-table-row">
            <div class="zone-name">${zone.name}</div>
            <div class="zone-type-badge ${zone.type}">${zone.type.charAt(0).toUpperCase() + zone.type.slice(1)}</div>
            <div class="zone-radius">${zone.radius}m</div>
            <div class="zone-actions">
                <button class="zone-btn-icon zone-btn-edit" onclick='editZone(${JSON.stringify(zone).replace(/'/g, "&apos;")})' title="Edit">✏️</button>
                <button class="zone-btn-icon zone-btn-delete" onclick='deleteZone(${JSON.stringify(zone).replace(/'/g, "&apos;")})' title="Delete">🗑️</button>
            </div>
        </div>
    `).join('');
}

function redrawZoneCircles() {
    try {
        // Remove existing zone circles
        zoneMapLayers.forEach(layer => {
            if (map.hasLayer(layer)) {
                map.removeLayer(layer);
            }
        });
        zoneMapLayers = [];
        
        // Fetch and redraw zones
        fetch('/api/zones')
            .then(response => {
                if (!response.ok) throw new Error('API error');
                return response.json();
            })
            .then(zones => {
                zones.forEach(zone => {
                    const colorMap = {
                        red: { color: '#ff4757', fill: '#ff4757' },
                        yellow: { color: '#ffa502', fill: '#ffa502' },
                        green: { color: '#2ed573', fill: '#2ed573' }
                    };
                    
                    const colors = colorMap[zone.type] || { color: '#cccccc', fill: '#cccccc' };
                    
                    const circle = L.circle([zone.lat, zone.lng], {
                        radius: zone.radius,
                        color: colors.color,
                        fillColor: colors.fill,
                        fillOpacity: 0.2,
                        weight: 2
                    })
                        .bindTooltip(`${zone.name} (${zone.type})`)
                        .addTo(map);
                    
                    zoneMapLayers.push(circle);
                });
            })
            .catch(error => console.error('Error redrawing zones:', error));
    } catch (error) {
        console.error('Error in redrawZoneCircles:', error);
    }
}

// ============ AI CONTROL ============
function loadAIStatus() {
    try {
        fetch('/api/admin/ai/status')
            .then(response => {
                if (!response.ok) throw new Error('API error: ' + response.status);
                return response.json();
            })
            .then(data => {
                const enabled = data.ai_enabled;
                const indicator = document.getElementById('ai-status-indicator');
                const enableBtn = document.getElementById('ai-btn-enable');
                const disableBtn = document.getElementById('ai-btn-disable');
                
                if (enabled) {
                    indicator.classList.remove('disabled');
                    indicator.classList.add('enabled');
                    enableBtn.disabled = true;
                    disableBtn.disabled = false;
                } else {
                    indicator.classList.remove('enabled');
                    indicator.classList.add('disabled');
                    enableBtn.disabled = false;
                    disableBtn.disabled = true;
                }
            })
            .catch(error => console.error('Error loading AI status:', error));
    } catch (error) {
        console.error('Error in loadAIStatus:', error);
    }
}

function toggleAI(enable) {
    try {
        const endpoint = enable ? '/api/admin/ai/enable' : '/api/admin/ai/disable';
        
        fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
            .then(response => {
                if (!response.ok) throw new Error('API error: ' + response.status);
                return response.json();
            })
            .then(data => {
                loadAIStatus();
                alert(`AI detection ${enable ? 'enabled' : 'disabled'}`);
            })
            .catch(error => {
                console.error('Error toggling AI:', error);
                alert('Failed to toggle AI detection');
            });
    } catch (error) {
        console.error('Error in toggleAI:', error);
    }
}

function toggleAIPanel() {
    // Toggle AI section expansion (placeholder for future collapse feature)
    console.log('AI panel toggled');
}

function updateAnomalyCount(locations) {
    try {
        const anomalyCount = locations.filter(loc => loc.is_anomaly).length;
        const anomalyStat = document.getElementById('stat-anomalies');
        const anomalyStatsDiv = document.getElementById('anomaly-stats');
        const anomalyCountDiv = document.getElementById('anomaly-count');
        
        if (anomalyStat) {
            anomalyStat.textContent = anomalyCount;
        }
        
        if (anomalyCount > 0) {
            if (anomalyStatsDiv) {
                anomalyStatsDiv.style.display = 'block';
            }
            if (anomalyCountDiv) {
                anomalyCountDiv.textContent = anomalyCount;
            }
        } else {
            if (anomalyStatsDiv) {
                anomalyStatsDiv.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error updating anomaly count:', error);
    }
}

// ========== USER MANAGEMENT FUNCTIONS ==========

function toggleUserForm() {
    const userForm = document.getElementById('user-form');
    const userToggle = document.querySelector('.user-toggle');
    
    if (userForm.classList.contains('visible')) {
        userForm.classList.remove('visible');
        userToggle.classList.remove('collapsed');
    } else {
        userForm.classList.add('visible');
        userToggle.classList.add('collapsed');
    }
}

function selectUserRole(role) {
    document.getElementById('selected-role').value = role;
    
    // Update button styling
    const userBtn = document.querySelector('.user-role-btn.user');
    const adminBtn = document.querySelector('.user-role-btn.admin');
    
    if (role === 'user') {
        userBtn.classList.add('selected');
        adminBtn.classList.remove('selected');
    } else {
        adminBtn.classList.add('selected');
        userBtn.classList.remove('selected');
    }
}

function loadAllUsers() {
    try {
        fetch('/api/admin/users/all')
            .then(response => {
                if (!response.ok) throw new Error('API error: ' + response.status);
                return response.json();
            })
            .then(users => {
                renderUsersTable(users);
            })
            .catch(error => console.error('Error loading users:', error));
    } catch (error) {
        console.error('Error in loadAllUsers:', error);
    }
}

function renderUsersTable(users = []) {
    const tableBody = document.getElementById('user-table-body');
    const table = document.getElementById('user-table');
    const emptyState = document.getElementById('user-empty-state');
    
    if (!users || users.length === 0) {
        tableBody.innerHTML = '';
        table.classList.remove('visible');
        emptyState.classList.remove('hidden');
        return;
    }
    
    table.classList.add('visible');
    emptyState.classList.add('hidden');
    
    // Get current user ID from session (will need to add this to the page)
    const currentUserId = parseInt(document.body.dataset.userId || '0');
    
    tableBody.innerHTML = users.map(user => {
        const initials = getInitials(user.name);
        const avatarColor = getAvatarColor(user.name);
        const roleBadgeClass = user.role === 'admin' ? 'admin' : 'user';
        const roleText = user.role === 'admin' ? '👑 Admin' : '👤 User';
        
        const actionCell = currentUserId === user.id
            ? '<span class="you-text">— (You)</span>'
            : `<button class="user-delete-btn" onclick='deleteUser(${user.id}, "${user.name.replace(/"/g, '\\"')}")' title="Delete">🗑️</button>`;
        
        return `
            <div class="user-table-row">
                <div class="user-avatar" style="background-color: ${avatarColor};">${initials}</div>
                <div class="user-name-cell">${user.name}</div>
                <div class="user-email-cell">${user.email}</div>
                <div><span class="user-role-badge ${roleBadgeClass}">${roleText}</span></div>
                <div class="user-action">${actionCell}</div>
            </div>
        `;
    }).join('');
}

function addUser() {
    try {
        const name = document.getElementById('user-name').value.trim();
        const email = document.getElementById('user-email').value.trim();
        const password = document.getElementById('user-password').value;
        const role = document.getElementById('selected-role').value;
        
        // Validate inputs
        if (!name || !email || !password) {
            showUserMessage('All fields are required', 'error');
            return;
        }
        
        // Basic email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            showUserMessage('Please enter a valid email address', 'error');
            return;
        }
        
        // Send request
        fetch('/api/admin/users/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email, password, role })
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.error || 'Failed to add user');
                    });
                }
                return response.json();
            })
            .then(data => {
                showUserMessage(`✅ ${name} added successfully`, 'success');
                // Clear form
                document.getElementById('user-name').value = '';
                document.getElementById('user-email').value = '';
                document.getElementById('user-password').value = '';
                selectUserRole('user');
                // Refresh tables
                loadAllUsers();
                loadLocations();
            })
            .catch(error => {
                showUserMessage(error.message || 'Error adding user', 'error');
            });
    } catch (error) {
        console.error('Error in addUser:', error);
        showUserMessage('An unexpected error occurred', 'error');
    }
}

function deleteUser(userId, userName) {
    const confirmDelete = confirm(`Remove ${userName} from the system? This cannot be undone.`);
    if (!confirmDelete) return;
    
    try {
        fetch(`/api/admin/users/${userId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.error || 'Failed to delete user');
                    });
                }
                return response.json();
            })
            .then(data => {
                showUserMessage(`✅ ${userName} removed`, 'success');
                // Refresh tables
                loadAllUsers();
                loadLocations();
            })
            .catch(error => {
                showUserMessage(error.message || 'Error deleting user', 'error');
            });
    } catch (error) {
        console.error('Error in deleteUser:', error);
        showUserMessage('An unexpected error occurred', 'error');
    }
}

function showUserMessage(message, type) {
    const messageDiv = document.getElementById('user-message');
    messageDiv.textContent = message;
    messageDiv.className = 'user-message ' + type;
    
    // Auto-hide after 3 seconds
    setTimeout(() => {
        messageDiv.className = 'user-message';
    }, 3000);
}
