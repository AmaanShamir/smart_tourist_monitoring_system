import math


def haversine(lat1, lng1, lat2, lng2):
    """
    Calculate the great-circle distance between two points on Earth
    using the Haversine formula.
    
    Parameters:
    -----------
    lat1 : float
        Latitude of the first point in decimal degrees
    lng1 : float
        Longitude of the first point in decimal degrees
    lat2 : float
        Latitude of the second point in decimal degrees
    lng2 : float
        Longitude of the second point in decimal degrees
    
    Returns:
    --------
    float
        Distance between the two points in kilometers
    
    Example:
    --------
    >>> distance = haversine(40.7128, -74.0060, 34.0522, -118.2437)
    >>> print(f"Distance: {distance:.2f} km")
    """
    # Earth radius in kilometers
    EARTH_RADIUS_KM = 6371.0
    
    # Convert decimal degrees to radians
    lat1_rad = math.radians(lat1)
    lng1_rad = math.radians(lng1)
    lat2_rad = math.radians(lat2)
    lng2_rad = math.radians(lng2)
    
    # Differences
    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad
    
    # Haversine formula
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    # Distance in kilometers
    distance = EARTH_RADIUS_KM * c
    
    return distance
