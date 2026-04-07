import sqlite3
import os
import bcrypt
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from datetime import datetime
from haversine import haversine
from ai_module import detect_anomaly

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

DATABASE = 'database.db'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with tables and seed data"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')
    
    # Create locations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timestamp TEXT NOT NULL,
            is_anomaly BOOLEAN DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    # Create zones table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            radius REAL NOT NULL,
            type TEXT NOT NULL
        )
    ''')
    
    # Create settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    
    # Seed initial data if users table is empty
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        # Hash passwords with bcrypt
        admin_hash = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode('utf-8')
        tourist_hash = bcrypt.hashpw(b'test123', bcrypt.gensalt()).decode('utf-8')
        
        # Insert admin user
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', ('Admin User', 'admin@tour.com', admin_hash, 'admin'))
        
        # Insert tourist user
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', ('Tourist User', 'tourist@tour.com', tourist_hash, 'user'))
        
        conn.commit()
    
    # Initialize AI settings if not already set
    cursor.execute('SELECT COUNT(*) FROM settings WHERE key = ?', ('ai_enabled',))
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO settings (key, value)
            VALUES (?, ?)
        ''', ('ai_enabled', 'true'))
        conn.commit()
    
    conn.close()

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Redirect to login"""
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login route"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, password_hash, role FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            flash(f'Welcome, {user["name"]}!', 'success')
            # Redirect to admin dashboard if admin, otherwise to regular dashboard
            if user['role'] == 'admin':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register route"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not name or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            flash('Email already exists.', 'danger')
            return render_template('register.html')
        
        # Hash password and insert user
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', (name, email, password_hash, 'user'))
        
        conn.commit()
        conn.close()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """Logout route"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard route"""
    username = session.get('name', 'User')
    return render_template('dashboard.html', username=username)

@app.route('/api/location', methods=['POST'])
@login_required
def api_location():
    """Handle location updates and check for geofencing alerts"""
    try:
        data = request.get_json()
        
        # Validate input parameters
        if not data:
            return jsonify({'error': 'Request body is empty'}), 400
        
        lat = data.get('lat')
        lng = data.get('lng')
        
        if lat is None or lng is None:
            return jsonify({'error': 'Missing latitude or longitude'}), 400
        
        user_id = session.get('user_id')
        conn = get_db()
        cursor = conn.cursor()
        
        # Check for anomalies using AI model BEFORE inserting location
        is_anomaly = False
        try:
            # Check if AI is enabled in settings
            cursor.execute('SELECT value FROM settings WHERE key = ?', ('ai_enabled',))
            ai_setting = cursor.fetchone()
            if ai_setting and ai_setting[0] == 'true':
                # Call AI anomaly detection with existing historical locations
                is_anomaly = detect_anomaly(user_id, lat, lng, conn)
                print(f"AI CALLED: {is_anomaly}")
            else:
                print("AI CALLED: False (AI not enabled)")
        except Exception as e:
            print(f"Error checking AI setting or detecting anomaly: {e}")
            is_anomaly = False
        
        # Now insert location record into database with detected anomaly flag
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO locations (user_id, latitude, longitude, timestamp, is_anomaly)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, lat, lng, timestamp, 1 if is_anomaly else 0))
        conn.commit()
        
        # Fetch all zones for geofencing check
        cursor.execute('SELECT id, name, type, lat, lng, radius FROM zones')
        zones = cursor.fetchall()
        
        # Check if user is within any zone using haversine distance
        # Priority: red > yellow > green if overlapping
        zone_alert = None
        priority_map = {'red': 3, 'yellow': 2, 'green': 1}
        highest_priority = 0
        
        for zone in zones:
            # Get zone center and radius
            zone_lat = zone['lat']
            zone_lng = zone['lng']
            zone_radius_m = zone['radius']
            zone_type = zone['type']
            
            # Convert radius from meters to kilometers for haversine comparison
            zone_radius_km = zone_radius_m / 1000.0
            
            # Calculate distance using haversine formula
            distance_km = haversine(lat, lng, zone_lat, zone_lng)
            
            # Check if user is within zone and has higher priority
            if distance_km <= zone_radius_km:
                zone_priority = priority_map.get(zone_type, 0)
                if zone_priority > highest_priority:
                    highest_priority = zone_priority
                    zone_alert = {
                        'name': zone['name'],
                        'type': zone_type
                    }
        
        conn.close()
        
        return jsonify({
            'success': True,
            'zone_alert': zone_alert,
            'is_anomaly': is_anomaly
        }), 200
    
    except Exception as error:
        # Return 500 error for server-side exceptions
        return jsonify({'error': f'Server error: {str(error)}'}), 500

@app.route('/api/admin/users/add', methods=['POST'])
@admin_required
def api_admin_add_user():
    """Add a new user (admin only)"""
    try:
        data = request.get_json()
        
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'user')  # Default to 'user' if not provided
        
        # Validate role
        if role not in ['admin', 'user']:
            role = 'user'
        
        # Validate required fields
        if not name or not email or not password:
            return jsonify({'error': 'Name, email, and password are required'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Email already exists'}), 400
        
        # Hash password and insert user
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', (name, email, password_hash, role))
        conn.commit()
        
        # Get the new user's ID
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        user_id = cursor.fetchone()['id']
        conn.close()
        
        return jsonify({
            'success': True,
            'user': {
                'id': user_id,
                'name': name,
                'email': email,
                'role': role
            }
        }), 201
    
    except Exception as error:
        return jsonify({'error': f'Server error: {str(error)}'}), 500

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_user(user_id):
    """Delete a user (admin only)"""
    try:
        current_user_id = session.get('user_id')
        
        # Cannot delete yourself
        if user_id == current_user_id:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user exists and get their role
        cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Cannot delete the last admin
        if user['role'] == 'admin':
            cursor.execute('SELECT COUNT(*) as count FROM users WHERE role = ?', ('admin',))
            admin_count = cursor.fetchone()['count']
            if admin_count == 1:
                conn.close()
                return jsonify({'error': 'Cannot delete the last admin'}), 400
        
        # Delete user's locations first (foreign key cleanup)
        cursor.execute('DELETE FROM locations WHERE user_id = ?', (user_id,))
        
        # Delete the user
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True}), 200
    
    except Exception as error:
        return jsonify({'error': f'Server error: {str(error)}'}), 500

@app.route('/api/admin/users/all', methods=['GET'])
@admin_required
def api_admin_get_all_users():
    """Get all users ordered by role and name (admin only)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, email, role FROM users
            ORDER BY role DESC, name ASC
        ''')
        users_data = cursor.fetchall()
        conn.close()
        
        users_list = [
            {
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'role': user['role']
            }
            for user in users_data
        ]
        
        return jsonify(users_list), 200
    
    except Exception as error:
        return jsonify({'error': f'Server error: {str(error)}'}), 500

@app.route('/api/zones')
@login_required
def api_zones():
    """Get all zones"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, lat, lng, radius, type FROM zones')
    zones_data = cursor.fetchall()
    conn.close()
    
    zones_list = [
        {
            'id': zone['id'],
            'name': zone['name'],
            'lat': zone['lat'],
            'lng': zone['lng'],
            'radius': zone['radius'],
            'type': zone['type']
        }
        for zone in zones_data
    ]
    
    return jsonify(zones_list)

@app.route('/admin')
@admin_required
def admin():
    """Admin control panel route"""
    username = session.get('name', 'Admin')
    user_id = session.get('user_id')
    return render_template('admin.html', username=username, user_id=user_id)

@app.route('/api/admin/users')
@admin_required
def api_admin_users():
    """Get all users for admin"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, email, role FROM users')
        users_data = cursor.fetchall()
        conn.close()
        
        users_list = [
            {
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'role': user['role']
            }
            for user in users_data
        ]
        
        return jsonify(users_list), 200
    
    except Exception as error:
        return jsonify({'error': f'Server error: {str(error)}'}), 500

@app.route('/api/admin/locations')
@admin_required
def api_admin_locations():
    """Get latest location per user for admin"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get latest location for each user with user details
        cursor.execute('''
            SELECT 
                u.id as user_id,
                u.name,
                l.latitude as lat,
                l.longitude as lng,
                l.timestamp,
                l.is_anomaly
            FROM users u
            LEFT JOIN (
                SELECT user_id, latitude, longitude, timestamp, is_anomaly
                FROM locations
                WHERE (user_id, timestamp) IN (
                    SELECT user_id, MAX(timestamp)
                    FROM locations
                    GROUP BY user_id
                )
            ) l ON u.id = l.user_id
            ORDER BY u.name ASC
        ''')
        locations_data = cursor.fetchall()
        conn.close()
        
        locations_list = [
            {
                'user_id': loc['user_id'],
                'name': loc['name'],
                'lat': loc['lat'] if loc['lat'] is not None else 40.7128,
                'lng': loc['lng'] if loc['lng'] is not None else -74.0060,
                'timestamp': loc['timestamp'] if loc['timestamp'] is not None else '',
                'is_anomaly': bool(loc['is_anomaly']) if loc['is_anomaly'] is not None else False
            }
            for loc in locations_data
        ]
        
        return jsonify(locations_list), 200
    
    except Exception as error:
        return jsonify({'error': f'Server error: {str(error)}'}), 500

@app.route('/api/admin/zones', methods=['POST'])
@admin_required
def api_admin_zones_create():
    """Create a new zone"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is empty'}), 400
        
        name = data.get('name', '').strip()
        lat = data.get('lat')
        lng = data.get('lng')
        radius = data.get('radius')
        zone_type = data.get('type', '').strip()
        
        if not name or lat is None or lng is None or radius is None or not zone_type:
            return jsonify({'error': 'Missing required fields'}), 400
        
        if zone_type not in ['red', 'yellow', 'green']:
            return jsonify({'error': 'Invalid zone type'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO zones (name, lat, lng, radius, type)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, lat, lng, radius, zone_type))
        conn.commit()
        
        zone_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'id': zone_id,
            'name': name,
            'lat': lat,
            'lng': lng,
            'radius': radius,
            'type': zone_type
        }), 201
    
    except Exception as error:
        return jsonify({'error': f'Server error: {str(error)}'}), 500

@app.route('/api/admin/zones/<int:zone_id>', methods=['PUT'])
@admin_required
def api_admin_zones_update(zone_id):
    """Update an existing zone"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is empty'}), 400
        
        name = data.get('name', '').strip()
        lat = data.get('lat')
        lng = data.get('lng')
        radius = data.get('radius')
        zone_type = data.get('type', '').strip()
        
        if not name or lat is None or lng is None or radius is None or not zone_type:
            return jsonify({'error': 'Missing required fields'}), 400
        
        if zone_type not in ['red', 'yellow', 'green']:
            return jsonify({'error': 'Invalid zone type'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE zones
            SET name = ?, lat = ?, lng = ?, radius = ?, type = ?
            WHERE id = ?
        ''', (name, lat, lng, radius, zone_type, zone_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'id': zone_id,
            'name': name,
            'lat': lat,
            'lng': lng,
            'radius': radius,
            'type': zone_type
        }), 200
    
    except Exception as error:
        return jsonify({'error': f'Server error: {str(error)}'}), 500

@app.route('/api/admin/zones/<int:zone_id>', methods=['DELETE'])
@admin_required
def api_admin_zones_delete(zone_id):
    """Delete a zone"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM zones WHERE id = ?', (zone_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True}), 200
    
    except Exception as error:
        return jsonify({'error': f'Server error: {str(error)}'}), 500

@app.route('/api/admin/ai/enable', methods=['POST'])
@admin_required
def api_admin_ai_enable():
    """Enable AI anomaly detection"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Upsert settings: ai_enabled = "true"
        cursor.execute('''
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?
        ''', ('ai_enabled', 'true', 'true'))
        
        conn.commit()
        conn.close()
        
        return jsonify({'ai_enabled': True}), 200
    
    except Exception as error:
        return jsonify({'error': f'Server error: {str(error)}'}), 500

@app.route('/api/admin/ai/disable', methods=['POST'])
@admin_required
def api_admin_ai_disable():
    """Disable AI anomaly detection"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Upsert settings: ai_enabled = "false"
        cursor.execute('''
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?
        ''', ('ai_enabled', 'false', 'false'))
        
        conn.commit()
        conn.close()
        
        return jsonify({'ai_enabled': False}), 200
    
    except Exception as error:
        return jsonify({'error': f'Server error: {str(error)}'}), 500

@app.route('/api/admin/ai/status', methods=['GET'])
@admin_required
def api_admin_ai_status():
    """Get AI anomaly detection status"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Read ai_enabled from settings
        cursor.execute('SELECT value FROM settings WHERE key = ?', ('ai_enabled',))
        result = cursor.fetchone()
        conn.close()
        
        ai_enabled = result[0] == 'true' if result else False
        
        return jsonify({'ai_enabled': ai_enabled}), 200
    
    except Exception as error:
        return jsonify({'error': f'Server error: {str(error)}'}), 500

if __name__ == '__main__':
    # Initialize database on startup
    init_db()
    app.run(debug=True)
