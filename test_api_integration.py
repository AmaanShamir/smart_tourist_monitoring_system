"""Test API integration with anomaly detection"""
import json
from app import app, init_db, get_db
from datetime import datetime, timedelta

# Initialize database
init_db()

print('\n' + '='*70)
print('Testing API Integration with Anomaly Detection')
print('='*70 + '\n')

# Create test client
client = app.test_client()

# Test 1: Login as tourist
print('[TEST 1] Login as tourist user')
print('-' * 70)

response = client.post('/login', data={
    'email': 'tourist@tour.com',
    'password': 'test123'
}, follow_redirects=True)

if response.status_code == 200:
    print('✓ Login successful')
else:
    print(f'✗ Login failed: {response.status_code}')

# Test 2: Send normal location (walking pace)
print('\n[TEST 2] Send normal location (safe movement)')
print('-' * 70)

# Set up location history for the user
conn = get_db()
cursor = conn.cursor()

# Clear previous locations for user 2
cursor.execute('DELETE FROM locations WHERE user_id = 2')

# Add a location from 1 hour ago
base_time = datetime.now() - timedelta(hours=1)
cursor.execute('''
    INSERT INTO locations (user_id, latitude, longitude, timestamp, is_anomaly)
    VALUES (?, ?, ?, ?, 0)
''', (2, 40.7128, -74.0060, base_time.isoformat()))

# Add locations with realistic walking pattern every 10 minutes
for i in range(6):
    lat = 40.7128 + (i * 0.0009)  # ~100m per step
    lng = -74.0060 + (i * 0.0009)
    timestamp = (base_time + timedelta(minutes=i*10)).isoformat()
    cursor.execute('''
        INSERT INTO locations (user_id, latitude, longitude, timestamp, is_anomaly)
        VALUES (?, ?, ?, ?, 0)
    ''', (2, lat, lng, timestamp))

conn.commit()
conn.close()

# Now send API request with next position
response = client.post('/api/location', 
    json={
        'lat': 40.7128 + (6 * 0.0009),
        'lng': -74.0060 + (6 * 0.0009)
    },
    headers={'Content-Type': 'application/json'}
)

if response.status_code == 200:
    data = response.get_json()
    print(f'✓ API request successful')
    print(f'  Response: {json.dumps(data, indent=2)}')
    print(f'  is_anomaly: {data.get("is_anomaly")} (expected False)')
else:
    print(f'✗ API request failed: {response.status_code}')
    print(f'  Response: {response.data}')

# Test 3: Check that location was recorded with is_anomaly flag
print('\n[TEST 3] Verify location was saved in database')
print('-' * 70)

conn = get_db()
cursor = conn.cursor()

# Get last location for user 2
cursor.execute('''
    SELECT latitude, longitude, timestamp, is_anomaly 
    FROM locations 
    WHERE user_id = 2 
    ORDER BY timestamp DESC 
    LIMIT 1
''')

last_location = cursor.fetchone()
if last_location:
    print(f'✓ Location found in database')
    print(f'  Latitude: {last_location[0]:.6f}')
    print(f'  Longitude: {last_location[1]:.6f}')
    print(f'  is_anomaly: {last_location[3]} (should be set based on AI detection)')
else:
    print('✗ Location not found in database')

conn.close()

# Test 4: Send anomalous location (extreme speed)
print('\n[TEST 4] Send anomalous location (extreme speed > 150 km/h)')
print('-' * 70)

# Need to insert a fresh location just before testing
# This ensures time_delta is reasonable (not 0)
conn = get_db()
cursor = conn.cursor()

# Delete all locations for user 2
cursor.execute('DELETE FROM locations WHERE user_id = 2')

# Add a single location from 30 seconds ago
base_location_time = datetime.now() - timedelta(seconds=30)
cursor.execute('''
    INSERT INTO locations (user_id, latitude, longitude, timestamp, is_anomaly)
    VALUES (?, ?, ?, ?, 0)
''', (2, 40.7128, -74.0060, base_location_time.isoformat()))

conn.commit()

# DEBUG: Check what was inserted
cursor.execute('SELECT * FROM locations WHERE user_id = 2')
rows = cursor.fetchall()
print(f'[DEBUG] Inserted rows: {len(rows)}')
for row in rows:
    print(f'  - lat={row[2]}, lng={row[3]}, timestamp={row[4]}')

conn.close()

# Give a little time for database to settle
import time
time.sleep(1)

# Now send a location 30 km away (will cause extreme speed)
response = client.post('/api/location', 
    json={
        'lat': 40.7128 + (30 / 111),  # Jump 30 km away ≈ 40.9826°
        'lng': -74.0060
    },
    headers={'Content-Type': 'application/json'}
)

if response.status_code == 200:
    data = response.get_json()
    print(f'✓ API request successful')
    print(f'  Response: {json.dumps(data, indent=2)}')
    is_anom = data.get("is_anomaly")
    expected = "True (hard rule triggers)"
    status = "✓ CORRECT" if is_anom else "✗ FAILED"
    print(f'  is_anomaly: {is_anom} (expected {expected}) {status}')
else:
    print(f'✗ API request failed: {response.status_code}')

print('\n' + '='*70)
print('✓ API Integration Tests Complete!')
print('='*70 + '\n')
