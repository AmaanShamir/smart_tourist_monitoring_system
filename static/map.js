let map;
let userMarker;
let watchId;
let lastUpdate = 0;
const UPDATE_INTERVAL = 5000; // 5 seconds

// Initialize map on page load
document.addEventListener('DOMContentLoaded', function() {
    try {
        initMap();
        startTracking();
        fetchAndDrawZones();
    } catch (error) {
        console.error('Error initializing dashboard:', error);
    }
});

function initMap() {
    try {
        // Create map centered on a default location
        if (!document.getElementById('map')) {
            console.error('Map container not found');
            return;
        }
        map = L.map('map').setView([40.7128, -74.0060], 13);
    
    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);
    
    // Create user marker with pulsing animation
    const pulseIcon = L.divIcon({
        className: 'user-marker-pulse',
        html: '<div class="user-marker-inner"></div>',
        iconSize: [30, 30],
        iconAnchor: [15, 15]
    });
    
    userMarker = L.marker([40.7128, -74.0060], { icon: pulseIcon })
        .bindPopup('📍 You are here')
        .addTo(map);
    } catch (error) {
        console.error('Error initializing map:', error);
    }
}

function startTracking() {
    // Request geolocation permission
    if (navigator.geolocation) {
        watchId = navigator.geolocation.watchPosition(
            handlePositionSuccess,
            handlePositionError,
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    } else {
        console.error('Geolocation not supported');
    }
}

function handlePositionSuccess(position) {
    const lat = position.coords.latitude;
    const lng = position.coords.longitude;
    
    // Update user marker position
    userMarker.setLatLng([lat, lng]);
    map.setView([lat, lng], 13);
    
    // Update info card
    updateInfoCard(lat, lng);
    
    // Send location to server every 5 seconds
    const now = Date.now();
    if (now - lastUpdate >= UPDATE_INTERVAL) {
        sendLocation(lat, lng);
        lastUpdate = now;
    }
}

function handlePositionError(error) {
    console.error('Geolocation error:', error.message);
}

function sendLocation(lat, lng) {
    try {
        fetch('/api/location', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ lat: lat, lng: lng })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('API response error: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            if (!data) {
                console.warn('Empty response from API');
                return;
            }
            
            // Handle zone alert
            if (data.zone_alert) {
                showZoneAlert(data.zone_alert.name, data.zone_alert.type);
            }
            
            // Handle anomaly alert
            if (data.is_anomaly) {
                showAnomalyAlert();
            }
        })
        .catch(error => console.error('Error sending location:', error));
    } catch (error) {
        console.error('Error in sendLocation:', error);
    }
}

function fetchAndDrawZones() {
    try {
        fetch('/api/zones')
        .then(response => {
            if (!response.ok) {
                throw new Error('API response error: ' + response.status);
            }
            return response.json();
        })
        .then(zones => {
            if (!zones || !Array.isArray(zones)) {
                console.warn('Invalid zones data received');
                return;
            }
            zones.forEach(zone => {
                try {
                    drawZoneCircle(zone);
                } catch (error) {
                    console.error('Error drawing zone:', zone, error);
                }
            });
        })
        .catch(error => console.error('Error fetching zones:', error));
    } catch (error) {
        console.error('Error in fetchAndDrawZones:', error);
    }
}

function drawZoneCircle(zone) {
    const colorMap = {
        'red': '#ff4757',
        'yellow': '#ffa502',
        'green': '#2ed573'
    };
    
    const fillColor = colorMap[zone.type] || '#cccccc';
    
    L.circle([zone.lat, zone.lng], {
        radius: zone.radius * 1000, // Convert to meters
        color: fillColor,
        fillColor: fillColor,
        fillOpacity: 0.25,
        weight: 2
    })
    .bindPopup(`<strong>${zone.name}</strong><br/>Type: ${zone.type}`)
    .addTo(map);
}

function showZoneAlert(zoneName, zoneType) {
    const alertEl = document.getElementById('zone-alert');
    const alertText = alertEl.querySelector('.alert-text');
    
    // Map zone type to color emoji and background
    const zoneEmoji = {
        'red': '🔴',
        'yellow': '🟡',
        'green': '🟢'
    };
    
    alertText.textContent = `${zoneEmoji[zoneType] || ''} ${zoneType.toUpperCase()} zone: ${zoneName}`;
    alertEl.className = `alert-banner zone-alert zone-${zoneType}`;
    
    // Show alert
    alertEl.classList.remove('hidden');
    
    // Auto-dismiss after 6 seconds
    setTimeout(() => {
        alertEl.classList.add('fade-out');
        setTimeout(() => {
            alertEl.classList.add('hidden');
            alertEl.classList.remove('fade-out');
        }, 500);
    }, 6000);
}

function showAnomalyAlert() {
    const alertEl = document.getElementById('anomaly-alert');
    
    // Show alert
    alertEl.classList.remove('hidden');
    
    // Auto-dismiss after 6 seconds
    setTimeout(() => {
        alertEl.classList.add('fade-out');
        setTimeout(() => {
            alertEl.classList.add('hidden');
            alertEl.classList.remove('fade-out');
        }, 500);
    }, 6000);
}

function updateInfoCard(lat, lng) {
    try {
        const coordsEl = document.getElementById('info-coords');
        const timeEl = document.getElementById('info-time');
        
        if (coordsEl) {
            coordsEl.textContent = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
        }
        
        if (timeEl) {
            const now = new Date();
            const timeString = now.toLocaleTimeString();
            timeEl.textContent = timeString;
        }
    } catch (error) {
        console.error('Error updating info card:', error);
    }
}

// Stop tracking when page unloads
window.addEventListener('beforeunload', function() {
    try {
        if (watchId) {
            navigator.geolocation.clearWatch(watchId);
        }
    } catch (error) {
        console.error('Error clearing watch:', error);
    }
});
