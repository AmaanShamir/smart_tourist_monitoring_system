from app import init_db, get_db
from ai_module import detect_anomaly
from datetime import datetime, timedelta

print('Final Comprehensive Test - Smart Tourist Monitoring System')
print('=' * 70)

# Initialize database
init_db()

conn = get_db()
cursor = conn.cursor()

# ===== TEST 1: Hard Rule - Extreme Speed (>150 km/h) =====
print('\n[TEST 1] Hard Rule: Speed > 150 km/h')
print('-' * 70)

cursor.execute('DELETE FROM locations WHERE user_id = 1001')

# Setup: User at NYC  
cursor.execute('''
    INSERT INTO locations (user_id, latitude, longitude, timestamp, is_anomaly)
    VALUES (?, ?, ?, ?, 0)
''', (1001, 40.7128, -74.0060, (datetime.now() - timedelta(seconds=10)).isoformat()))

conn.commit()

# Try to jump 30 km in 5 seconds (5400 km/h)
far_lat = 40.7128 + (30 / 111)  
result = detect_anomaly(1001, far_lat, -74.0060, conn)
status = "✓ PASS" if result == True else "✗ FAIL"
print(f'Result: {result} | Expected: True {status}\n')

# ===== TEST 2: Normal Walking Speed =====
print('[TEST 2] Normal Walking: ~4 km/h (safe, expected False)')
print('-' * 70)

cursor.execute('DELETE FROM locations WHERE user_id = 1002')

# Create a realistic walking pattern - use recent past times
base_time = datetime.now() - timedelta(hours=1)  # 1 hour ago
center_lat, center_lng = 40.7128, -74.0060

# Add 8 walking steps with consistent 100m movements every 1.5 minutes
for i in range(8):
    lat = center_lat + (i * 0.0009)  # ~100m per step
    lng = center_lng + (i * 0.0009)
    timestamp = (base_time + timedelta(minutes=i*1.5)).isoformat()
    
    cursor.execute('''
        INSERT INTO locations (user_id, latitude, longitude, timestamp, is_anomaly)
        VALUES (?, ?, ?, ?, 0)
    ''', (1002, lat, lng, timestamp))

conn.commit()

# Add the final location very recently (90 seconds ago)
lat_check = center_lat + (8 * 0.0009)
lng_check = center_lng + (8 * 0.0009)
final_time = datetime.now() - timedelta(seconds=90)

cursor.execute('''
    INSERT INTO locations (user_id, latitude, longitude, timestamp, is_anomaly)
    VALUES (?, ?, ?, ?, 0)
''', (1002, lat_check, lng_check, final_time.isoformat()))

conn.commit()

# Now test the next step (should be normal)
result = detect_anomaly(1002, lat_check + 0.0009, lng_check + 0.0009, conn)
status = "✓ PASS" if result == False else "✗ FAIL"
print(f'Result: {result} | Expected: False {status}\n')

# ===== TEST 3: Impossible Jump (>50 km in <5 min) =====
print('[TEST 3] Hard Rule: > 50 km in < 5 minutes')
print('-' * 70)

cursor.execute('DELETE FROM locations WHERE user_id = 1003')

cursor.execute('''
    INSERT INTO locations (user_id, latitude, longitude, timestamp, is_anomaly)
    VALUES (?, ?, ?, ?, 0)
''', (1003, 40.7128, -74.0060, (datetime.now() - timedelta(seconds=60)).isoformat()))

conn.commit()

# Jump 80 km away
far_lat_3 = 40.7128 + (80 / 111)
result = detect_anomaly(1003, far_lat_3, -74.0060, conn)
status = "✓ PASS" if result == True else "✗ FAIL"
print(f'Result: {result} | Expected: True {status}\n')

conn.close()

print('=' * 70)
print('System Test Summary:')
print('  - Hard Rule 1 (Speed > 150 km/h): ENABLED')
print('  - Hard Rule 2 (>50km in <5min): ENABLED')
print('  - ML Detection (IsolationForest): ENABLED')
print('=' * 70)
