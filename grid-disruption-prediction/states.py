"""The 20 states with the most weather-driven OE-417 events, 2000-2014.

Three weather points per state -- the largest metro areas, because grid
disturbances get reported where the customers are, not at the geographic
centre of the state. Daily features take the worst reading across a state's
three points, which matches the target: "was a major disturbance reported
anywhere in this state today?"
"""

STATE_POINTS = {
    "Michigan":       [("Detroit", 42.33, -83.05), ("Grand Rapids", 42.96, -85.67), ("Traverse City", 44.76, -85.62)],
    "Virginia":       [("Richmond", 37.54, -77.44), ("Virginia Beach", 36.85, -75.98), ("Roanoke", 37.27, -79.94)],
    "California":     [("Los Angeles", 34.05, -118.24), ("San Francisco", 37.77, -122.42), ("Sacramento", 38.58, -121.49)],
    "Texas":          [("Houston", 29.76, -95.37), ("Dallas", 32.78, -96.80), ("San Antonio", 29.42, -98.49)],
    "Pennsylvania":   [("Philadelphia", 39.95, -75.17), ("Pittsburgh", 40.44, -79.99), ("Scranton", 41.41, -75.66)],
    "Illinois":       [("Chicago", 41.88, -87.63), ("Springfield", 39.80, -89.64), ("Peoria", 40.69, -89.59)],
    "Ohio":           [("Columbus", 39.96, -83.00), ("Cleveland", 41.50, -81.69), ("Cincinnati", 39.10, -84.51)],
    "Indiana":        [("Indianapolis", 39.77, -86.16), ("Fort Wayne", 41.08, -85.14), ("Evansville", 37.97, -87.57)],
    "Georgia":        [("Atlanta", 33.75, -84.39), ("Savannah", 32.08, -81.09), ("Augusta", 33.47, -81.97)],
    "North Carolina": [("Charlotte", 35.23, -80.84), ("Raleigh", 35.78, -78.64), ("Wilmington", 34.23, -77.94)],
    "Maryland":       [("Baltimore", 39.29, -76.61), ("Hagerstown", 39.64, -77.72), ("Salisbury", 38.36, -75.60)],
    "Alabama":        [("Birmingham", 33.52, -86.80), ("Mobile", 30.69, -88.04), ("Huntsville", 34.73, -86.59)],
    "Louisiana":      [("New Orleans", 29.95, -90.07), ("Baton Rouge", 30.45, -91.19), ("Shreveport", 32.53, -93.75)],
    "Florida":        [("Miami", 25.76, -80.19), ("Tampa", 27.95, -82.46), ("Jacksonville", 30.33, -81.66)],
    "Arkansas":       [("Little Rock", 34.75, -92.29), ("Fayetteville", 36.06, -94.16), ("Jonesboro", 35.84, -90.70)],
    "Mississippi":    [("Jackson", 32.30, -90.18), ("Gulfport", 30.37, -89.09), ("Tupelo", 34.26, -88.70)],
    "New York":       [("New York", 40.71, -74.01), ("Buffalo", 42.89, -78.88), ("Albany", 42.65, -73.76)],
    "South Carolina": [("Columbia", 34.00, -81.03), ("Charleston", 32.78, -79.93), ("Greenville", 34.85, -82.39)],
    "Washington":     [("Seattle", 47.61, -122.33), ("Spokane", 47.66, -117.43), ("Vancouver", 45.63, -122.67)],
    "Kentucky":       [("Louisville", 38.25, -85.76), ("Lexington", 38.04, -84.50), ("Bowling Green", 36.99, -86.44)],
}

# Flat list in request order; location_id N in the Open-Meteo response is
# POINTS[N], which is how downloaded weather is matched back to a state.
POINTS = [
    {"state": state, "place": place, "lat": lat, "lon": lon}
    for state, places in STATE_POINTS.items()
    for place, lat, lon in places
]

START_DATE = "2000-01-01"
END_DATE = "2014-12-31"
