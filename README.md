# Rank Tracker - Local SEO Heatmap Tool

A browser-based application for tracking Google Rankings across geographic locations. Draw a rectangle on a map, and the app automatically generates a grid of tracking points to check Google Rankings for a specific business.

## Features

- **Interactive Map**: Draw rectangles on a map to define scan areas
- **Grid Generation**: Automatically generates GPS coordinates grid based on spacing
- **Map-pack scanning**: one DataForSEO Google Maps request per grid point, ranked at that coordinate
- **Color-Coded Visualization**: 
  - Gold (#FFD700): Rank 1-3
  - Green (#22c55e): Rank 4-10
  - Yellow (#eab308): Rank 11-20
  - Orange (#f97316): Rank 21-30
  - Red (#ef4444): Rank 31+ or Not Found
  - Grey (#6b7280): API Error
- **Data Persistence**: Saves all scans to SQLite database

## Tech Stack

- **Backend**: Python (Flask), requests, sqlite3
- **Frontend**: HTML5, TailwindCSS (CDN), Leaflet.js, Leaflet-Draw
- **API**: DataForSEO Google Maps Live Advanced

## Setup

1. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

2. **Configure DataForSEO**:
   - Copy `.env.example` to `.env`
   - Add the login and password from the DataForSEO API access page:
   ```
   DATAFORSEO_LOGIN=your_login
   DATAFORSEO_PASSWORD=your_password
   ```

3. **Run the Application**:
```bash
python app.py
```

4. **Open in Browser**:
   - Navigate to `http://localhost:5000`

## Usage

1. **Enter Details**:
   - Business Name (e.g., "Edil Italia")
   - Keyword (e.g., "Ristrutturazione")
   - Grid Spacing (0.5km to 5km)

2. **Draw Rectangle**:
   - Use the rectangle drawing tool on the map
   - Draw over the area you want to scan

3. **Start Scan**:
   - Click "Start Scan"
   - Wait for the scan to complete (may take time with many points)

4. **View Results**:
   - Color-coded markers show rankings
   - Click markers for detailed rank information

## Database

Scans are saved to `scans.db` with two tables:
- `scans`: Scan metadata (date, business name, keyword, grid spacing, bounding box)
- `scan_points`: Individual grid point results (coordinates, ranks, status)

## API Credits

- Maximum 100 grid points per scan
- Each point is one DataForSEO Google Maps Live request
- Depth defaults to 20 and is capped at 100, because depth above 100 is billed as another SERP
- Use `USE_DUMMY_MODE=true` in `.env` for testing without API calls

## Environment Variables

- `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD`: required for real scans
- `DATAFORSEO_LANGUAGE_CODE`: default `it`
- `DATAFORSEO_SE_DOMAIN`: default `google.it`
- `DATAFORSEO_DEVICE`: `mobile` (default) or `desktop`
- `DATAFORSEO_DEPTH`: listings to request, 1 to 100, default 20
- `USE_DUMMY_MODE`: set to `true` for fake listings. A missing password does not turn this on.
