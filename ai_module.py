import numpy as np
from sklearn.ensemble import IsolationForest
from haversine import haversine


def detect_anomaly(user_id, new_lat, new_lng, conn):
    """
    Detect anomalies in user movement using IsolationForest + hard speed rules.
    
    Parameters:
    -----------
    user_id : int
        User ID to check
    new_lat : float
        New latitude coordinate
    new_lng : float
        New longitude coordinate
    conn : sqlite3.Connection
        Database connection
    
    Returns:
    --------
    bool
        True if anomaly detected, False otherwise
    """
    try:
        from datetime import datetime
        
        cursor = conn.cursor()
        
        # Query last 20 locations for this user
        cursor.execute('''
            SELECT latitude, longitude, timestamp
            FROM locations
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 20
        ''', (user_id,))
        
        locations = cursor.fetchall()
        
        # If no previous locations, allow first location
        if len(locations) == 0:
            return False
        
        # Sort by timestamp ascending (oldest first)
        locations = list(reversed(locations))
        
        # Get the most recent previous location
        lat_prev, lng_prev, time_prev = locations[-1]
        
        # Calculate time delta
        t_prev = datetime.fromisoformat(time_prev)
        t_new = datetime.now()
        time_delta_sec = (t_new - t_prev).total_seconds()
        
        # Calculate distance and speed for new location
        distance_km = haversine(lat_prev, lng_prev, new_lat, new_lng)
        
        # Avoid division by zero
        if time_delta_sec <= 0:
            speed_kmh = 0
        else:
            speed_kmh = (distance_km / time_delta_sec) * 3600
        
        # DEBUG: Print movement metrics
        print(f"[ANOMALY_DEBUG] User {user_id}: distance={distance_km:.2f}km, time_delta={time_delta_sec:.0f}sec, speed={speed_kmh:.2f}km/h")
        
        # HARD RULE 1: Speed > 150 km/h is always anomalous (unrealistic for tourists)
        if speed_kmh > 150:
            print(f"[ANOMALY_DETECTED] User {user_id}: Speed {speed_kmh:.2f} km/h exceeds 150 km/h threshold")
            return True
        
        # HARD RULE 2: Jump > 50 km in < 5 minutes is always anomalous
        if distance_km > 50 and time_delta_sec < 300:
            print(f"[ANOMALY_DETECTED] User {user_id}: Jumped {distance_km:.2f}km in {time_delta_sec:.0f}sec")
            return True
        
        # If less than 15 historical records, use only hard rules (model needs more training data)
        if len(locations) < 15:
            print(f"[ANOMALY_ML] User {user_id}: Insufficient data ({len(locations)} records), using hard rules only")
            return False
        
        # Build feature matrix from consecutive pairs
        features = []
        for i in range(len(locations) - 1):
            lat1, lng1, time1 = locations[i]
            lat2, lng2, time2 = locations[i + 1]
            
            t1 = datetime.fromisoformat(time1)
            t2 = datetime.fromisoformat(time2)
            
            # Calculate time delta in seconds
            time_delta = (t2 - t1).total_seconds()
            
            # Skip if no time difference
            if time_delta == 0:
                continue
            
            # Calculate distance in km
            dist = haversine(lat1, lng1, lat2, lng2)
            
            # Calculate speed in km/h
            speed = (dist / time_delta) * 3600
            
            # Add feature vector: [distance, time_delta, speed]
            features.append([dist, time_delta, speed])
        
        # Need at least 5 feature vectors for meaningful ML training
        if len(features) < 5:
            print(f"[ANOMALY_ML] User {user_id}: Only {len(features)} feature vectors, using hard rules only")
            return False
        
        # Convert to numpy array
        X = np.array(features)
        
        # Train IsolationForest with moderate sensitivity (contamination=0.1)
        iso_forest = IsolationForest(contamination=0.1, random_state=42)
        iso_forest.fit(X)
        
        # Create feature vector for new location
        new_feature = np.array([[distance_km, time_delta_sec, speed_kmh]])
        
        # Predict: -1 = anomaly, 1 = normal
        prediction = iso_forest.predict(new_feature)[0]
        
        is_anomaly = bool(prediction == -1)  # Convert numpy.bool_ to Python bool
        
        if is_anomaly:
            print(f"[ANOMALY_ML_DETECTED] User {user_id}: IsolationForest flagged movement as anomalous")
        else:
            print(f"[ANOMALY_ML_NORMAL] User {user_id}: IsolationForest detected normal movement")
        
        return is_anomaly
    
    except Exception as e:
        # Log error but don't break location tracking
        print(f"[ANOMALY_ERROR] Error in anomaly detection for user {user_id}: {e}")
        return False
