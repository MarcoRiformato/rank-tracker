
from app import app
import json

app.config['TESTING'] = True

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['project_id'] = 4  # Matches existing data in point_history

    response = client.get('/api/dashboard/points')
    if response.status_code == 200:
        data = response.get_json()
        points = data.get('points', [])
        print(f"Total points returned: {len(points)}")
        if points:
            print(f"First point city: '{points[0].get('city')}'")
            print(f"Second point city: '{points[1].get('city')}'")
            
            # Count points with city
            with_city = sum(1 for p in points if p.get('city'))
            print(f"Points with city: {with_city}/{len(points)}")
    else:
        print(f"Error: {response.status_code}")
