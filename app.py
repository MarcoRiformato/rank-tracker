import os
import sqlite3
import time
import json
import uuid
import threading
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
import requests

load_dotenv()

from rank_tracker.grid import calculate_grid
from rank_tracker.serp import credentials_configured, fetch_local_rank, normalize_competitor_name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rank_tracker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'rank-tracker-secret-key-change-in-production')

if os.getenv('USE_DUMMY_MODE', 'false').lower() == 'true':
    logger.warning("USE_DUMMY_MODE is on. Scans will not call DataForSEO.")
elif credentials_configured():
    logger.info("DataForSEO credentials loaded")
else:
    logger.error("DATAFORSEO_LOGIN or DATAFORSEO_PASSWORD is missing")

def is_dummy_mode():
    """Session toggle wins. A missing API password does not turn on fake data."""
    if 'use_dummy_mode' in session:
        return session.get('use_dummy_mode') is True
    return os.getenv('USE_DUMMY_MODE', 'false').lower() == 'true'

# Database setup
DB_NAME = 'scans.db'

# Job tracker for async scan progress
# Format: {job_id: {status, progress, completed, total, total_api_calls, completed_api_calls,
#                   results, start_time, eta_seconds, error}}
scan_jobs = {}
scan_jobs_lock = threading.Lock()

def init_db():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Create projects table
    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            business_names TEXT,
            keywords TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    # Add new columns to projects table if they don't exist
    try:
        c.execute('ALTER TABLE projects ADD COLUMN business_names TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        c.execute('ALTER TABLE projects ADD COLUMN keywords TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create scans table
    c.execute('''
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            business_name TEXT NOT NULL,
            keyword TEXT NOT NULL,
            grid_spacing REAL NOT NULL,
            bbox_north REAL NOT NULL,
            bbox_east REAL NOT NULL,
            bbox_south REAL NOT NULL,
            bbox_west REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    # Create scan_points table
    c.execute('''
        CREATE TABLE IF NOT EXISTS scan_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            local_pack_rank INTEGER,
            organic_rank INTEGER,
            display_rank INTEGER,
            status TEXT,
            matched_business_name TEXT,
            keyword TEXT,
            search_query TEXT,
            FOREIGN KEY (scan_id) REFERENCES scans(id)
        )
    ''')
    
    # Add new columns if they don't exist (for existing databases)
    try:
        c.execute('ALTER TABLE scans ADD COLUMN project_id INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        c.execute('ALTER TABLE scan_points ADD COLUMN matched_business_name TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        c.execute('ALTER TABLE scan_points ADD COLUMN keyword TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        c.execute('ALTER TABLE scan_points ADD COLUMN search_query TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        c.execute('ALTER TABLE point_history ADD COLUMN project_id INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        c.execute('ALTER TABLE point_history ADD COLUMN city TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create point_history table for tracking historical rankings
    c.execute('''
        CREATE TABLE IF NOT EXISTS point_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            keyword TEXT NOT NULL,
            business_name TEXT NOT NULL,
            scan_date TEXT NOT NULL,
            local_pack_rank INTEGER,
            organic_rank INTEGER,
            display_rank INTEGER,
            matched_business_name TEXT,
            search_query TEXT,
            city TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    # Add new detail columns to point_history (optional but good for debugging)
    # Actually, the user asked for COMPETITOR table details.
    
    # ... (existing ALTERs)
    
    # Add detailed columns to competitor_history
    try:
        c.execute('ALTER TABLE competitor_history ADD COLUMN address TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE competitor_history ADD COLUMN phone_number TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE competitor_history ADD COLUMN website TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE competitor_history ADD COLUMN category TEXT')
    except sqlite3.OperationalError:
        pass
        
    try:
        c.execute('ALTER TABLE competitor_snapshots ADD COLUMN address TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE competitor_snapshots ADD COLUMN phone_number TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE competitor_snapshots ADD COLUMN website TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE competitor_snapshots ADD COLUMN category TEXT')
    except sqlite3.OperationalError:
        pass
    
    # Create index for faster queries
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_point_history_location 
        ON point_history(lat, lon, keyword)
    ''')
    
    # Create scheduled_scans table for periodic scans
    c.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            frequency TEXT NOT NULL,
            start_date TEXT NOT NULL,
            next_run_date TEXT NOT NULL,
            business_names TEXT NOT NULL,
            keywords TEXT NOT NULL,
            grid_spacing REAL NOT NULL,
            polygon_coords TEXT,
            bbox_north REAL,
            bbox_east REAL,
            bbox_south REAL,
            bbox_west REAL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    # Create competitor_snapshots table for storing all competitors in Top 30
    c.execute('''
        CREATE TABLE IF NOT EXISTS competitor_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_point_id INTEGER NOT NULL,
            rank INTEGER NOT NULL,
            competitor_name TEXT NOT NULL,
            review_count INTEGER,
            rating_stars REAL,
            FOREIGN KEY (scan_point_id) REFERENCES scan_points(id)
        )
    ''')
    
    # Create index for faster competitor lookups
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_competitor_snapshots_scan_point 
        ON competitor_snapshots(scan_point_id)
    ''')
    
    # Create competitor_history table for tracking historical competitor rankings
    c.execute('''
        CREATE TABLE IF NOT EXISTS competitor_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            scan_point_id INTEGER NOT NULL,
            competitor_name TEXT NOT NULL,
            rank INTEGER NOT NULL,
            review_count INTEGER,
            rating_stars REAL,
            scan_date TEXT NOT NULL,
            keyword TEXT NOT NULL,
            city TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (scan_point_id) REFERENCES scan_points(id)
        )
    ''')
    
    # Create indexes for faster queries
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_competitor_history_project_name_date
        ON competitor_history(project_id, competitor_name, scan_date)
    ''')

    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_competitor_history_project_name_keyword
        ON competitor_history(project_id, competitor_name, keyword)
    ''')

    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_competitor_history_project_date
        ON competitor_history(project_id, scan_date)
    ''')

    # Create saved_polygons table for storing user-drawn polygons
    c.execute('''
        CREATE TABLE IF NOT EXISTS saved_polygons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            coordinates TEXT NOT NULL,  -- JSON array of [lat, lon] pairs
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')

    # Create index for faster polygon queries
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_saved_polygons_project
        ON saved_polygons(project_id)
    ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Serve main page - redirect to project select if no project selected"""
    if 'project_id' not in session:
        return render_template('project_select.html')
    return render_template('index.html')

@app.route('/projects')
def project_select():
    """Serve project selection page"""
    return render_template('project_select.html')

@app.route('/api/projects', methods=['GET'])
def get_projects():
    """Get all projects"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, name, created_at, updated_at FROM projects ORDER BY updated_at DESC')
    projects = [{'id': r[0], 'name': r[1], 'created_at': r[2], 'updated_at': r[3]} for r in c.fetchall()]
    conn.close()
    return jsonify(projects)

@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project"""
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Project name is required'}), 400
    
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO projects (name, created_at, updated_at) VALUES (?, ?, ?)', (name, now, now))
        project_id = c.lastrowid
        conn.commit()
        conn.close()
        return jsonify({'id': project_id, 'name': name, 'created_at': now, 'updated_at': now})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Project name already exists'}), 400

@app.route('/api/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    """Update a project"""
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Project name is required'}), 400
    
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE projects SET name = ?, updated_at = ? WHERE id = ?', (name, now, project_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project and all associated data"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Delete associated scans, scan_points, and point_history
    c.execute('DELETE FROM scan_points WHERE scan_id IN (SELECT id FROM scans WHERE project_id = ?)', (project_id,))
    c.execute('DELETE FROM scans WHERE project_id = ?', (project_id,))
    c.execute('DELETE FROM point_history WHERE project_id = ?', (project_id,))
    c.execute('DELETE FROM projects WHERE id = ?', (project_id,))
    conn.commit()
    conn.close()
    
    # Clear session if deleted project was selected
    if session.get('project_id') == project_id:
        session.pop('project_id', None)
    
    return jsonify({'success': True})

@app.route('/api/logout', methods=['POST'])
def logout():
    """Log out (clear session)"""
    session.pop('project_id', None)
    return jsonify({'success': True})

@app.route('/api/dummy-data', methods=['POST'])
def add_dummy_data_endpoint():
    """Add dummy data for current project"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    add_dummy_data(project_id)
    return jsonify({'success': True})

@app.route('/api/cleanup-dummy-data', methods=['POST'])
def cleanup_dummy_data():
    """Remove all dummy/test data from the database"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Known dummy data patterns
    dummy_keywords = ['pizza delivery', 'italian restaurant', 'food near me']
    dummy_business_patterns = ['My Business', 'My Business Inc', 'My Business LLC']
    
    deleted_counts = {
        'scans': 0,
        'scan_points': 0,
        'point_history': 0,
        'competitor_snapshots': 0,
        'competitor_history': 0
    }
    
    try:
        # Find scan IDs with dummy keywords or business names
        dummy_scan_ids = []
        
        # Find scans with dummy keywords
        for keyword in dummy_keywords:
            c.execute('SELECT id FROM scans WHERE project_id = ? AND keyword = ?', (project_id, keyword))
            dummy_scan_ids.extend([row[0] for row in c.fetchall()])
        
        # Find scans with dummy business names
        for pattern in dummy_business_patterns:
            c.execute('SELECT id FROM scans WHERE project_id = ? AND business_name LIKE ?', (project_id, f'%{pattern}%'))
            dummy_scan_ids.extend([row[0] for row in c.fetchall()])
        
        # Remove duplicates
        dummy_scan_ids = list(set(dummy_scan_ids))
        
        if dummy_scan_ids:
            # Delete competitor_snapshots for these scan points
            c.execute('''
                DELETE FROM competitor_snapshots 
                WHERE scan_point_id IN (
                    SELECT id FROM scan_points WHERE scan_id IN ({})
                )
            '''.format(','.join(['?' for _ in dummy_scan_ids])), dummy_scan_ids)
            deleted_counts['competitor_snapshots'] = c.rowcount
            
            # Delete competitor_history for these scan points
            c.execute('''
                DELETE FROM competitor_history 
                WHERE project_id = ? AND scan_point_id IN (
                    SELECT id FROM scan_points WHERE scan_id IN ({})
                )
            '''.format(','.join(['?' for _ in dummy_scan_ids])), [project_id] + dummy_scan_ids)
            deleted_counts['competitor_history'] = c.rowcount
            
            # Delete scan_points
            c.execute('DELETE FROM scan_points WHERE scan_id IN ({})'.format(','.join(['?' for _ in dummy_scan_ids])), dummy_scan_ids)
            deleted_counts['scan_points'] = c.rowcount
            
            # Delete scans
            c.execute('DELETE FROM scans WHERE id IN ({})'.format(','.join(['?' for _ in dummy_scan_ids])), dummy_scan_ids)
            deleted_counts['scans'] = c.rowcount
        
        # Also delete point_history entries with dummy keywords or business names
        for keyword in dummy_keywords:
            c.execute('DELETE FROM point_history WHERE project_id = ? AND keyword = ?', (project_id, keyword))
            deleted_counts['point_history'] += c.rowcount
        
        for pattern in dummy_business_patterns:
            c.execute('DELETE FROM point_history WHERE project_id = ? AND business_name LIKE ?', (project_id, f'%{pattern}%'))
            deleted_counts['point_history'] += c.rowcount
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'deleted': deleted_counts,
            'message': f'Removed {deleted_counts["scans"]} dummy scans and associated data'
        })
    
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Error cleaning up dummy data: {str(e)}'}), 500

@app.route('/api/cleanup-all-project-data', methods=['POST'])
def cleanup_all_project_data():
    """Remove ALL data for the current project (use with caution!)"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    data = request.json
    confirm = data.get('confirm', False)
    
    if not confirm:
        return jsonify({'error': 'Must confirm deletion by setting confirm: true'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        # Get all scan IDs for this project
        c.execute('SELECT id FROM scans WHERE project_id = ?', (project_id,))
        scan_ids = [row[0] for row in c.fetchall()]
        
        deleted_counts = {
            'scans': 0,
            'scan_points': 0,
            'point_history': 0,
            'competitor_snapshots': 0,
            'competitor_history': 0,
            'scheduled_scans': 0
        }
        
        if scan_ids:
            # Delete competitor_snapshots
            c.execute('''
                DELETE FROM competitor_snapshots 
                WHERE scan_point_id IN (
                    SELECT id FROM scan_points WHERE scan_id IN ({})
                )
            '''.format(','.join(['?' for _ in scan_ids])), scan_ids)
            deleted_counts['competitor_snapshots'] = c.rowcount
            
            # Delete competitor_history
            c.execute('DELETE FROM competitor_history WHERE project_id = ?', (project_id,))
            deleted_counts['competitor_history'] = c.rowcount
            
            # Delete scan_points
            c.execute('DELETE FROM scan_points WHERE scan_id IN ({})'.format(','.join(['?' for _ in scan_ids])), scan_ids)
            deleted_counts['scan_points'] = c.rowcount
            
            # Delete scans
            c.execute('DELETE FROM scans WHERE project_id = ?', (project_id,))
            deleted_counts['scans'] = c.rowcount
        
        # Delete point_history
        c.execute('DELETE FROM point_history WHERE project_id = ?', (project_id,))
        deleted_counts['point_history'] = c.rowcount
        
        # Delete scheduled_scans
        c.execute('DELETE FROM scheduled_scans WHERE project_id = ?', (project_id,))
        deleted_counts['scheduled_scans'] = c.rowcount
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'deleted': deleted_counts,
            'message': f'Removed all data for project {project_id}'
        })
    
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'Error cleaning up project data: {str(e)}'}), 500

@app.route('/api/projects/select', methods=['POST'])
def select_project():
    """Select a project (set in session)"""
    data = request.json
    project_id = data.get('project_id')
    if not project_id:
        return jsonify({'error': 'Project ID is required'}), 400
    
    # Verify project exists and get its data
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, name, business_names, keywords FROM projects WHERE id = ?', (project_id,))
    project = c.fetchone()
    if not project:
        conn.close()
        return jsonify({'error': 'Project not found'}), 404
    
    # Check if project has any scans - if not, add dummy data
    c.execute('SELECT COUNT(*) FROM scans WHERE project_id = ?', (project_id,))
    scan_count = c.fetchone()[0]
    conn.close()
    
    session['project_id'] = project_id
    
    # If no scans, automatically add dummy data
    if scan_count == 0:
        add_dummy_data(project_id)
    
    # Return project data including business_names and keywords
    import json as json_lib
    return jsonify({
        'success': True,
        'business_names': json_lib.loads(project[2]) if project[2] else [],
        'keywords': json_lib.loads(project[3]) if project[3] else []
    })

@app.route('/api/projects/current', methods=['GET'])
def get_current_project():
    """Get current project data"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT id, name, business_names, keywords FROM projects WHERE id = ?', (project_id,))
    project = c.fetchone()
    conn.close()
    
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    import json as json_lib
    return jsonify({
        'id': project[0],
        'name': project[1],
        'business_names': json_lib.loads(project[2]) if project[2] else [],
        'keywords': json_lib.loads(project[3]) if project[3] else []
    })

@app.route('/api/projects/<int:project_id>/settings', methods=['PUT'])
def update_project_settings(project_id):
    """Update project settings (business_names and keywords)"""
    if session.get('project_id') != project_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    business_names = data.get('business_names', [])
    keywords = data.get('keywords', [])
    
    import json as json_lib
    business_names_json = json_lib.dumps(business_names)
    keywords_json = json_lib.dumps(keywords)
    
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE projects SET business_names = ?, keywords = ?, updated_at = ? WHERE id = ?', 
              (business_names_json, keywords_json, now, project_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/scheduled-scans', methods=['GET'])
def get_scheduled_scans():
    """Get all scheduled scans for current project"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT id, name, frequency, start_date, next_run_date, is_active, created_at
        FROM scheduled_scans
        WHERE project_id = ?
        ORDER BY created_at DESC
    ''', (project_id,))
    
    scans = []
    for row in c.fetchall():
        scans.append({
            'id': row[0],
            'name': row[1],
            'frequency': row[2],
            'start_date': row[3],
            'next_run_date': row[4],
            'is_active': bool(row[5]),
            'created_at': row[6]
        })
    conn.close()
    
    return jsonify({'scans': scans})

@app.route('/api/scheduled-scans', methods=['POST'])
def create_scheduled_scan():
    """Create a new scheduled scan"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    data = request.json
    from datetime import timedelta
    import json as json_lib
    
    frequency = data.get('frequency')
    start_date_str = data.get('start_date')
    start_date = datetime.fromisoformat(start_date_str)
    
    # Calculate next run date
    if frequency == 'weekly':
        next_run = start_date + timedelta(weeks=1)
    elif frequency == 'monthly':
        next_run = start_date + timedelta(days=30)
    else:
        return jsonify({'error': 'Invalid frequency'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO scheduled_scans (project_id, name, frequency, start_date, next_run_date,
                                     business_names, keywords, grid_spacing, polygon_coords,
                                     bbox_north, bbox_east, bbox_south, bbox_west, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        project_id,
        data.get('name'),
        frequency,
        start_date_str,
        next_run.isoformat(),
        json_lib.dumps(data.get('business_names', [])),
        json_lib.dumps(data.get('keywords', [])),
        data.get('grid_spacing', 2.0),
        json_lib.dumps(data.get('polygon_coords')),
        data.get('bbox', {}).get('north'),
        data.get('bbox', {}).get('east'),
        data.get('bbox', {}).get('south'),
        data.get('bbox', {}).get('west'),
        datetime.now().isoformat()
    ))
    scan_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'id': scan_id})

@app.route('/api/scheduled-scans/<int:scan_id>', methods=['DELETE'])
def delete_scheduled_scan(scan_id):
    """Delete a scheduled scan"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM scheduled_scans WHERE id = ? AND project_id = ?', (scan_id, project_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/point-history', methods=['GET'])
def point_history():
    """Get historical ranking data for a specific point and keyword"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    keyword = request.args.get('keyword', '')
    
    if not keyword:
        return jsonify({'error': 'Keyword parameter is required'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get historical data for this point and keyword, filtered by project
    c.execute('''
        SELECT scan_date, local_pack_rank, organic_rank, display_rank, 
               matched_business_name, search_query
        FROM point_history
        WHERE lat = ? AND lon = ? AND keyword = ? AND project_id = ?
        ORDER BY scan_date ASC
    ''', (lat, lon, keyword, project_id))
    
    rows = c.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        history.append({
            'date': row[0],
            'local_pack_rank': row[1],
            'organic_rank': row[2],
            'display_rank': row[3],
            'matched_business_name': row[4],
            'search_query': row[5]
        })
    
    return jsonify({'history': history})

@app.route('/api/point-competitors', methods=['GET'])
def point_competitors():
    """Get top 5 competitors for a scan point"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    keyword = request.args.get('keyword', '')
    
    if not keyword:
        return jsonify({'error': 'Keyword parameter is required'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Find the most recent scan_point_id for this location/keyword combination
    # by joining with scans table to filter by project_id
    c.execute('''
        SELECT sp.id
        FROM scan_points sp
        INNER JOIN scans s ON sp.scan_id = s.id
        WHERE sp.lat = ? AND sp.lon = ? AND sp.keyword = ? AND s.project_id = ?
        ORDER BY s.date DESC, sp.id DESC
        LIMIT 1
    ''', (lat, lon, keyword, project_id))
    
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'competitors': []})
    
    scan_point_id = row[0]
    
    # Get top 5 competitors sorted by rank
    c.execute('''
        SELECT rank, competitor_name, review_count, rating_stars
        FROM competitor_snapshots
        WHERE scan_point_id = ?
        ORDER BY rank ASC
        LIMIT 5
    ''', (scan_point_id,))
    
    rows = c.fetchall()
    conn.close()
    
    competitors = []
    for row in rows:
        competitors.append({
            'rank': row[0],
            'name': row[1],
            'review_count': row[2],
            'rating_stars': row[3]
        })
    
    return jsonify({'competitors': competitors})

@app.route('/api/competitors/overview', methods=['GET'])
def competitors_overview():
    """Get top 10 competitors with all metrics"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    keyword = request.args.get('keyword', '')

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Build query with optional keyword filter
    if keyword:
        c.execute('''
            SELECT DISTINCT cs.competitor_name
            FROM competitor_snapshots cs
            INNER JOIN scan_points sp ON cs.scan_point_id = sp.id
            INNER JOIN scans s ON sp.scan_id = s.id
            WHERE s.project_id = ? AND sp.keyword = ?
        ''', (project_id, keyword))
    else:
        # Get all unique competitors for this project
        # Join competitor_snapshots with scan_points and scans to filter by project
        c.execute('''
            SELECT DISTINCT cs.competitor_name
            FROM competitor_snapshots cs
            INNER JOIN scan_points sp ON cs.scan_point_id = sp.id
            INNER JOIN scans s ON sp.scan_id = s.id
            WHERE s.project_id = ?
        ''', (project_id,))

    competitor_names = [row[0] for row in c.fetchall()]

    # If no competitors found (due to broken scan_point_id references),
    # fall back to returning all real competitors (they're from actual scans)
    if not competitor_names:
        print(f"[DEBUG] No competitors found via JOIN, falling back to all competitors")
        c.execute('SELECT DISTINCT competitor_name FROM competitor_snapshots WHERE competitor_name NOT LIKE "Competitor %"')
        competitor_names = [row[0] for row in c.fetchall()]
        print(f"[DEBUG] Found {len(competitor_names)} competitors via fallback")

    # Get total number of unique scan points (for coverage calculation)
    if keyword:
        c.execute('''
            SELECT COUNT(DISTINCT sp.id) FROM scan_points sp
            INNER JOIN scans s ON sp.scan_id = s.id
            WHERE s.project_id = ? AND sp.keyword = ?
        ''', (project_id, keyword))
    else:
        c.execute('''
            SELECT COUNT(DISTINCT sp.id) FROM scan_points sp
            INNER JOIN scans s ON sp.scan_id = s.id
            WHERE s.project_id = ?
        ''', (project_id,))
    total_scan_points = c.fetchone()[0] or 1
    conn.close()
    
    competitors_data = []
    for competitor_name in competitor_names:
        # Calculate all metrics
        dominance = calculate_dominance_score(competitor_name, project_id)
        consistency = calculate_consistency(competitor_name, project_id)
        trend_data = calculate_growth_trend(competitor_name, project_id)
        classification = classify_competitor(competitor_name, project_id)
        
        # Get aggregate stats
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        c.execute('''
            SELECT
                COUNT(*) as total_appearances,
                AVG(cs.rank) as avg_rank,
                AVG(cs.review_count) as avg_reviews,
                AVG(cs.rating_stars) as avg_rating,
                COUNT(DISTINCT cs.scan_point_id) as unique_locations
            FROM competitor_snapshots cs
            INNER JOIN scan_points sp ON cs.scan_point_id = sp.id
            INNER JOIN scans s ON sp.scan_id = s.id
            WHERE s.project_id = ? AND cs.competitor_name = ?
        ''', (project_id, competitor_name))
        
        row = c.fetchone()
        conn.close()
        
        total_appearances = row[0] or 0
        avg_rank = round(row[1], 2) if row[1] else None
        avg_reviews = round(row[2], 2) if row[2] else None
        avg_rating = round(row[3], 2) if row[3] else None
        unique_locations = row[4] or 0
        coverage = round((unique_locations / total_scan_points) * 100, 2) if total_scan_points > 0 else 0.0
        
        competitors_data.append({
            'name': competitor_name,
            'total_appearances': total_appearances,
            'avg_rank': avg_rank,
            'avg_reviews': avg_reviews,
            'avg_rating': avg_rating,
            'dominance_score': dominance,
            'consistency': consistency,
            'growth_trend': trend_data.get('trend'),
            'trend_change': trend_data.get('change'),
            'classification': classification,
            'coverage': coverage
        })
    
    # Sort by dominance score descending
    competitors_data.sort(key=lambda x: x['dominance_score'], reverse=True)
    
    # Return top 500 (increased from 10)
    return jsonify({'competitors': competitors_data[:500]})

@app.route('/api/competitors/<path:competitor_name>/trends', methods=['GET'])
def competitor_trends(competitor_name):
    """Get historical ranking trend for a specific competitor"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get historical trend data grouped by scan date
    c.execute('''
        SELECT scan_date, AVG(rank) as avg_rank, COUNT(*) as appearances
        FROM competitor_history
        WHERE project_id = ? AND competitor_name = ?
        GROUP BY scan_date
        ORDER BY scan_date ASC
    ''', (project_id, competitor_name))
    
    rows = c.fetchall()
    conn.close()
    
    trends = []
    for row in rows:
        trends.append({
            'date': row[0],
            'avg_rank': round(row[1], 2) if row[1] else None,
            'appearances': row[2]
        })
    
    return jsonify({'trends': trends})

@app.route('/api/competitors/<path:competitor_name>/details', methods=['GET'])
def competitor_details(competitor_name):
    """Get detailed breakdown by keyword and city for a competitor"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get keyword breakdown
    c.execute('''
        SELECT 
            keyword,
            AVG(rank) as avg_rank,
            COUNT(*) as appearances,
            COUNT(DISTINCT scan_point_id) as unique_locations
        FROM competitor_history
        WHERE project_id = ? AND competitor_name = ?
        GROUP BY keyword
        ORDER BY appearances DESC
    ''', (project_id, competitor_name))
    
    keyword_rows = c.fetchall()
    keyword_breakdown = []
    for row in keyword_rows:
        keyword_breakdown.append({
            'keyword': row[0],
            'avg_rank': round(row[1], 2) if row[1] else None,
            'appearances': row[2],
            'unique_locations': row[3]
        })
    
    # Get city breakdown - show ALL cities from scans, with competitor data if available
    # First get all cities from the project's scans
    c.execute('''
        SELECT DISTINCT city FROM competitor_history
        WHERE project_id = ? AND city IS NOT NULL AND city != ''
        ORDER BY city ASC
    ''', (project_id,))
    
    all_cities = [row[0] for row in c.fetchall()]
    
    # Get competitor-specific data for each city
    c.execute('''
        SELECT 
            city,
            AVG(rank) as avg_rank,
            COUNT(*) as appearances,
            COUNT(DISTINCT scan_point_id) as unique_locations
        FROM competitor_history
        WHERE project_id = ? AND competitor_name = ? AND city IS NOT NULL
        GROUP BY city
    ''', (project_id, competitor_name))
    
    competitor_city_data = {}
    for row in c.fetchall():
        competitor_city_data[row[0]] = {
            'avg_rank': round(row[1], 2) if row[1] else None,
            'appearances': row[2],
            'unique_locations': row[3]
        }
    
    # Build city breakdown with all cities
    city_breakdown = []
    for city in all_cities:
        if city in competitor_city_data:
            # Competitor appears in this city
            data = competitor_city_data[city]
            city_breakdown.append({
                'city': city,
                'avg_rank': data['avg_rank'],
                'appearances': data['appearances'],
                'unique_locations': data['unique_locations']
            })
        else:
            # Competitor doesn't appear in this city
            city_breakdown.append({
                'city': city,
                'avg_rank': None,
                'appearances': 0,
                'unique_locations': 0
            })
    
    # Sort by appearances descending (cities with appearances first, then by city name)
    city_breakdown.sort(key=lambda x: (-x['appearances'], x['city']))
    
    # Get total coverage metrics
    c.execute('''
        SELECT 
            COUNT(DISTINCT scan_point_id) as total_locations,
            COUNT(DISTINCT keyword) as total_keywords,
            COUNT(DISTINCT city) as total_cities,
            MIN(scan_date) as first_seen,
            MAX(scan_date) as last_seen
        FROM competitor_history
        WHERE project_id = ? AND competitor_name = ?
    ''', (project_id, competitor_name))
    
    coverage_row = c.fetchone()
    conn.close()
    
    return jsonify({
        'keyword_breakdown': keyword_breakdown,
        'city_breakdown': city_breakdown,
        'total_locations': coverage_row[0] or 0,
        'total_keywords': coverage_row[1] or 0,
        'total_cities': coverage_row[2] or 0,
        'first_seen': coverage_row[3],
        'last_seen': coverage_row[4]
    })

@app.route('/api/competitors/by-type', methods=['GET'])
def competitors_by_type():
    """Get competitors filtered by classification type"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    filter_type = request.args.get('type', 'all')
    
    # Get overview data first
    overview_response = competitors_overview()
    overview_data = overview_response.get_json()
    
    if filter_type == 'all':
        return jsonify(overview_data)
    
    # Filter by classification
    filtered_competitors = [
        comp for comp in overview_data.get('competitors', [])
        if comp.get('classification') == filter_type
    ]
    
    return jsonify({'competitors': filtered_competitors})

@app.route('/api/competitors/cities', methods=['GET'])
def competitors_cities():
    """Get list of cities available for filtering"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get distinct cities from competitor_history
    c.execute('''
        SELECT DISTINCT city FROM competitor_history
        WHERE project_id = ? AND city IS NOT NULL AND city != ''
        ORDER BY city ASC
    ''', (project_id,))
    
    cities = [row[0] for row in c.fetchall()]
    conn.close()
    
    return jsonify({'cities': cities})

@app.route('/api/competitors/by-city', methods=['GET'])
def competitors_by_city():
    """Get competitor rankings filtered by city"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    city = request.args.get('city')
    if not city:
        return jsonify({'error': 'City parameter required'}), 400

    keyword = request.args.get('keyword', '')

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Get unique competitors for this city (and keyword if provided)
    query = '''
        SELECT DISTINCT competitor_name FROM competitor_history
        WHERE project_id = ? AND city = ?
    '''
    params = [project_id, city]

    if keyword:
        query += ' AND keyword = ?'
        params.append(keyword)

    c.execute(query, params)

    competitor_names = [row[0] for row in c.fetchall()]
    
    competitors_data = []
    for competitor_name in competitor_names:
        # Build query for this competitor - include keyword filter if provided
        where_clause = 'WHERE project_id = ? AND competitor_name = ? AND city = ?'
        where_params = [project_id, competitor_name, city]

        if keyword:
            where_clause += ' AND keyword = ?'
            where_params.append(keyword)

        # Get aggregate stats for this city only
        c.execute(f'''
            SELECT
                COUNT(*) as total_appearances,
                AVG(rank) as avg_rank,
                AVG(review_count) as avg_reviews,
                AVG(rating_stars) as avg_rating,
                MIN(rank) as best_rank,
                MAX(rank) as worst_rank,
                COUNT(DISTINCT keyword) as keywords_count,
                COUNT(DISTINCT scan_point_id) as unique_locations,
                MAX(address) as address,
                MAX(phone_number) as phone_number,
                MAX(website) as website,
                MAX(category) as category
            FROM competitor_history
            {where_clause}
        ''', where_params)

        row = c.fetchone()

        # Calculate dominance for this city
        c.execute(f'''
            SELECT
                SUM(CASE WHEN rank BETWEEN 1 AND 3 THEN 1 ELSE 0 END) as top3,
                SUM(CASE WHEN rank BETWEEN 4 AND 10 THEN 1 ELSE 0 END) as top10,
                COUNT(*) as total
            FROM competitor_history
            {where_clause}
        ''', where_params)
        
        dom_row = c.fetchone()
        total = dom_row[2] or 1
        dominance = (dom_row[0] * 3 + dom_row[1] * 2) / total if total > 0 else 0
        
        competitors_data.append({
            'name': competitor_name,
            'total_appearances': row[0] or 0,
            'avg_rank': round(row[1], 2) if row[1] else None,
            'avg_reviews': round(row[2], 2) if row[2] else None,
            'avg_rating': round(row[3], 2) if row[3] else None,
            'best_rank': row[4] or None,
            'worst_rank': row[5] or None,
            'keywords_count': row[6] or 0,
            'unique_locations': row[7] or 0,
            'address': row[8] or '',
            'phone_number': row[9] or '',
            'website': row[10] or '',
            'category': row[11] or '',
            'dominance_score': round(dominance, 2)
        })
    
    # Sort by avg_rank (best first)
    competitors_data.sort(key=lambda x: x['avg_rank'] or 999)
    
    conn.close()
    
    return jsonify({
        'city': city,
        'competitors': competitors_data
    })

@app.route('/dashboard')
def dashboard():
    """Serve dashboard page"""
    return render_template('dashboard.html')

@app.route('/competitors')
def competitors():
    """Serve competitors dashboard page"""
    return render_template('competitors.html')

@app.route('/intelligence')
def intelligence():
    """Serve market intelligence & reporting page"""
    return render_template('intelligence.html')

@app.route('/point/<float:lat>/<float:lon>/<path:keyword>')
def point_detail(lat, lon, keyword):
    """Serve point detail page"""
    return render_template('point_detail.html')

@app.route('/api/dashboard/scans', methods=['GET'])
def dashboard_scans():
    """Get all scans for dashboard"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('''
        SELECT s.id, s.date, s.business_name, s.keyword, s.grid_spacing,
               COUNT(sp.id) as point_count,
               AVG(sp.display_rank) as avg_rank
        FROM scans s
        LEFT JOIN scan_points sp ON s.id = sp.scan_id
        GROUP BY s.id
        ORDER BY s.date DESC
    ''')
    
    rows = c.fetchall()
    conn.close()
    
    scans = []
    for row in rows:
        scans.append({
            'id': row[0],
            'date': row[1],
            'business_name': row[2],
            'keyword': row[3],
            'grid_spacing': row[4],
            'point_count': row[5] or 0,
            'avg_rank': row[6]
        })
    
    return jsonify({'scans': scans})

@app.route('/api/dashboard/aggregates', methods=['GET'])
def dashboard_aggregates():
    """Get aggregated statistics"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    keyword_filter = request.args.get('keyword', '')
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Build base WHERE clause for keyword filtering
    keyword_where = ''
    keyword_params = []
    if keyword_filter:
        keyword_where = ' AND keyword = ?'
        keyword_params = [keyword_filter]
    
    # Total scans (filtered by project and keyword)
    scan_query = '''
        SELECT COUNT(*) FROM scans 
        WHERE project_id = ?
    '''
    scan_params = [project_id]
    if keyword_filter:
        scan_query += ' AND keyword = ?'
        scan_params.append(keyword_filter)
    c.execute(scan_query, scan_params)
    total_scans = c.fetchone()[0]
    
    # Total points (filtered by project and keyword)
    points_query = '''
        SELECT COUNT(*) FROM scan_points 
        WHERE scan_id IN (
            SELECT id FROM scans WHERE project_id = ?
    '''
    points_params = [project_id]
    if keyword_filter:
        points_query += ' AND keyword = ?'
        points_params.append(keyword_filter)
    points_query += ')'
    c.execute(points_query, points_params)
    total_points = c.fetchone()[0]
    
    # Average rank (filtered by project and keyword)
    avg_query = '''
        SELECT AVG(display_rank) FROM scan_points 
        WHERE scan_id IN (SELECT id FROM scans WHERE project_id = ?
    '''
    avg_params = [project_id]
    if keyword_filter:
        avg_query += ' AND keyword = ?'
        avg_params.append(keyword_filter)
    avg_query += ') AND display_rank IS NOT NULL'
    c.execute(avg_query, avg_params)
    avg_rank_row = c.fetchone()
    avg_rank = avg_rank_row[0] if avg_rank_row[0] else None
    
    # Top 3 coverage
    top3_query = '''
        SELECT COUNT(*) FROM scan_points 
        WHERE scan_id IN (SELECT id FROM scans WHERE project_id = ?
    '''
    top3_params = [project_id]
    if keyword_filter:
        top3_query += ' AND keyword = ?'
        top3_params.append(keyword_filter)
    top3_query += ') AND display_rank BETWEEN 1 AND 3'
    c.execute(top3_query, top3_params)
    top3_count = c.fetchone()[0]
    top3_coverage = (top3_count / total_points * 100) if total_points > 0 else 0
    
    # Top 10 coverage
    top10_query = '''
        SELECT COUNT(*) FROM scan_points 
        WHERE scan_id IN (SELECT id FROM scans WHERE project_id = ?
    '''
    top10_params = [project_id]
    if keyword_filter:
        top10_query += ' AND keyword = ?'
        top10_params.append(keyword_filter)
    top10_query += ') AND display_rank BETWEEN 1 AND 10'
    c.execute(top10_query, top10_params)
    top10_count = c.fetchone()[0]
    top10_coverage = (top10_count / total_points * 100) if total_points > 0 else 0
    
    # Local Pack presence (any local pack rank, not null)
    local_pack_query = '''
        SELECT COUNT(*) FROM scan_points 
        WHERE scan_id IN (SELECT id FROM scans WHERE project_id = ?
    '''
    local_pack_params = [project_id]
    if keyword_filter:
        local_pack_query += ' AND keyword = ?'
        local_pack_params.append(keyword_filter)
    local_pack_query += ') AND local_pack_rank IS NOT NULL'
    c.execute(local_pack_query, local_pack_params)
    local_pack_count = c.fetchone()[0]
    local_pack_presence = (local_pack_count / total_points * 100) if total_points > 0 else 0
    
    # Rank distribution
    dist_query = '''
        SELECT 
            SUM(CASE WHEN display_rank BETWEEN 1 AND 3 THEN 1 ELSE 0 END) as rank_1_3,
            SUM(CASE WHEN display_rank BETWEEN 4 AND 10 THEN 1 ELSE 0 END) as rank_4_10,
            SUM(CASE WHEN display_rank BETWEEN 11 AND 20 THEN 1 ELSE 0 END) as rank_11_20,
            SUM(CASE WHEN display_rank BETWEEN 21 AND 30 THEN 1 ELSE 0 END) as rank_21_30,
            SUM(CASE WHEN display_rank IS NULL THEN 1 ELSE 0 END) as not_found
        FROM scan_points
        WHERE scan_id IN (SELECT id FROM scans WHERE project_id = ?
    '''
    dist_params = [project_id]
    if keyword_filter:
        dist_query += ' AND keyword = ?'
        dist_params.append(keyword_filter)
    dist_query += ')'
    c.execute(dist_query, dist_params)
    dist_row = c.fetchone()
    rank_distribution = {
        '1-3': dist_row[0] or 0,
        '4-10': dist_row[1] or 0,
        '11-20': dist_row[2] or 0,
        '21-30': dist_row[3] or 0,
        'not_found': dist_row[4] or 0
    }
    
    # Rank trends - average position for Local Pack and Organic separately
    trends_query = '''
        SELECT DATE(scan_date) as date, 
               AVG(local_pack_rank) as avg_local_pack,
               AVG(organic_rank) as avg_organic
        FROM point_history
        WHERE project_id = ? AND (local_pack_rank IS NOT NULL OR organic_rank IS NOT NULL)
    '''
    trends_params = [project_id]
    if keyword_filter:
        trends_query += ' AND keyword = ?'
        trends_params.append(keyword_filter)
    trends_query += '''
        GROUP BY DATE(scan_date)
        ORDER BY date ASC
        LIMIT 30
    '''
    c.execute(trends_query, trends_params)
    trend_rows = c.fetchall()
    rank_trends = {
        'dates': [row[0] for row in trend_rows],
        'avg_local_pack': [float(row[1]) if row[1] else None for row in trend_rows],
        'avg_organic': [float(row[2]) if row[2] else None for row in trend_rows]
    }
    
    conn.close()
    
    return jsonify({
        'total_scans': total_scans,
        'total_points': total_points,
        'avg_rank': avg_rank,
        'top3_coverage': top3_coverage,
        'top10_coverage': top10_coverage,
        'local_pack_presence': local_pack_presence,
        'rank_distribution': rank_distribution,
        'rank_trends': rank_trends
    })

@app.route('/api/toggle-testing-mode', methods=['POST'])
def toggle_testing_mode():
    """Toggle testing mode (dummy mode) in session"""
    data = request.json
    enable = data.get('enable', True)
    session['use_dummy_mode'] = enable
    return jsonify({'success': True, 'testing_mode': enable})

@app.route('/api/testing-mode-status', methods=['GET'])
def testing_mode_status():
    """Get current testing mode status"""
    testing_mode = is_dummy_mode()
    return jsonify({'testing_mode': testing_mode})

_city_cache = {}

def reverse_geocode(lat, lon, dummy_mode=None):
    """City name from Nominatim. Points within about 100m share one lookup."""
    use_dummy = dummy_mode if dummy_mode is not None else is_dummy_mode()
    fallback = f"{lat:.4f}, {lon:.4f}"
    if use_dummy:
        return fallback

    key = (round(float(lat), 3), round(float(lon), 3))
    cached = _city_cache.get(key)
    if cached:
        return cached

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "addressdetails": 1},
            headers={"User-Agent": "RankTracker/1.0 (local rank grid)"},
            timeout=5,
        )
        time.sleep(1.1)
        city = fallback
        if response.ok:
            address = response.json().get("address", {})
            city = (
                address.get("city") or address.get("town") or address.get("village")
                or address.get("municipality") or address.get("suburb")
                or address.get("neighbourhood") or fallback
            )
    except requests.RequestException as exc:
        logger.warning("Reverse geocode failed for (%s, %s): %s", lat, lon, exc)
        time.sleep(1.1)
        city = fallback
    _city_cache[key] = city
    return city

def calculate_dominance_score(competitor_name, project_id):
    """
    Calculate dominance score for a competitor
    Formula: (Top3_appearances * 3 + Top10_appearances * 2 + Top30_appearances * 1) / total_appearances
    Returns: float (0-3.0)
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Count total appearances
    c.execute('''
        SELECT COUNT(*) FROM competitor_snapshots cs
        INNER JOIN scan_points sp ON cs.scan_point_id = sp.id
        INNER JOIN scans s ON sp.scan_id = s.id
        WHERE s.project_id = ? AND cs.competitor_name = ?
    ''', (project_id, competitor_name))
    total_appearances = c.fetchone()[0]
    
    if total_appearances == 0:
        conn.close()
        return 0.0
    
    # Count appearances in each rank range
    c.execute('''
        SELECT
            SUM(CASE WHEN cs.rank BETWEEN 1 AND 3 THEN 1 ELSE 0 END) as top3,
            SUM(CASE WHEN cs.rank BETWEEN 4 AND 10 THEN 1 ELSE 0 END) as top10,
            SUM(CASE WHEN cs.rank BETWEEN 11 AND 30 THEN 1 ELSE 0 END) as top30
        FROM competitor_snapshots cs
        INNER JOIN scan_points sp ON cs.scan_point_id = sp.id
        INNER JOIN scans s ON sp.scan_id = s.id
        WHERE s.project_id = ? AND cs.competitor_name = ?
    ''', (project_id, competitor_name))
    
    row = c.fetchone()
    top3_count = row[0] or 0
    top10_count = row[1] or 0
    top30_count = row[2] or 0
    
    conn.close()
    
    # Calculate dominance score
    dominance = (top3_count * 3 + top10_count * 2 + top30_count * 1) / total_appearances
    return round(dominance, 2)

def calculate_consistency(competitor_name, project_id):
    """
    Calculate consistency (standard deviation) of ranks for a competitor
    Lower value = more consistent
    Returns: float
    """
    import statistics
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get all ranks for this competitor
    c.execute('''
        SELECT cs.rank FROM competitor_snapshots cs
        INNER JOIN scan_points sp ON cs.scan_point_id = sp.id
        INNER JOIN scans s ON sp.scan_id = s.id
        WHERE s.project_id = ? AND cs.competitor_name = ?
    ''', (project_id, competitor_name))
    
    ranks = [row[0] for row in c.fetchall()]
    conn.close()
    
    if len(ranks) < 2:
        return 0.0
    
    try:
        std_dev = statistics.stdev(ranks)
        return round(std_dev, 2)
    except:
        return 0.0

def calculate_growth_trend(competitor_name, project_id):
    """
    Calculate growth trend by comparing recent vs old average ranks from competitor_history
    Returns: dict with 'trend' ('improving', 'declining', 'stable'), 'recent_avg', 'old_avg', 'change'
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get unique dates for this competitor in this project
    c.execute('''
        SELECT DISTINCT scan_date FROM competitor_history
        WHERE project_id = ? AND competitor_name = ?
        ORDER BY scan_date ASC
    ''', (project_id, competitor_name))
    
    dates = [row[0] for row in c.fetchall()]
    
    if len(dates) < 2:
        conn.close()
        return {'trend': 'stable', 'recent_avg': None, 'old_avg': None, 'change': 0.0}
    
    # Split into recent (last 30%) and older (rest)
    # Using 30/70 split to capture recent movement vs baseline
    split_idx = max(1, int(len(dates) * 0.7))
    recent_dates = dates[split_idx:]
    old_dates = dates[:split_idx]
    
    if not recent_dates: # Handle edge case
        recent_dates = [dates[-1]]
        old_dates = dates[:-1]
    
    # Calculate average rank for recent period
    placeholders_recent = ','.join(['?'] * len(recent_dates))
    c.execute(f'''
        SELECT AVG(rank) FROM competitor_history
        WHERE project_id = ? AND competitor_name = ? AND scan_date IN ({placeholders_recent})
    ''', [project_id, competitor_name] + recent_dates)
    recent_avg = c.fetchone()[0]
    
    # Calculate average rank for old period
    placeholders_old = ','.join(['?'] * len(old_dates))
    c.execute(f'''
        SELECT AVG(rank) FROM competitor_history
        WHERE project_id = ? AND competitor_name = ? AND scan_date IN ({placeholders_old})
    ''', [project_id, competitor_name] + old_dates)
    old_avg = c.fetchone()[0]
    
    conn.close()
    
    if recent_avg is None or old_avg is None:
        return {'trend': 'stable', 'recent_avg': recent_avg, 'old_avg': old_avg, 'change': 0.0}
    
    # Lower rank is better, so improving = recent_avg < old_avg
    change = old_avg - recent_avg  # Positive change = improving (rank went from 10 to 5)
    threshold = 0.3  # Minimum rank change to be considered a trend
    
    if change > threshold:
        trend = 'improving'
    elif change < -threshold:
        trend = 'declining'
    else:
        trend = 'stable'
    
    return {
        'trend': trend,
        'recent_avg': round(recent_avg, 2),
        'old_avg': round(old_avg, 2),
        'change': round(change, 2)
    }

def classify_competitor(competitor_name, project_id):
    """
    Classify competitor based on dominance and growth trend
    Returns: string classification slug
    """
    dominance = calculate_dominance_score(competitor_name, project_id)
    trend_data = calculate_growth_trend(competitor_name, project_id)
    trend = trend_data['trend']

    # Updated thresholds to match dominanceScoreToLabel in frontend
    if dominance >= 2.5:
        if trend == 'improving': return "Dominant & Growing"
        if trend == 'declining': return "Dominant & Declining"
        return "Market Leader"

    if dominance >= 1.8:
        if trend == 'improving': return "Rising Challenger"
        return "Strong Competitor"

    if dominance >= 1.2:
        if trend == 'improving': return "Growing Challenger"
        return "Moderate Competitor"

    if trend == 'improving':
        return "Emerging"

    return "Minor Competitor"

@app.route('/api/reverse-geocode', methods=['GET'])
def reverse_geocode_api():
    """Reverse geocode coordinates to get city name"""
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    city = reverse_geocode(lat, lon)
    return jsonify({'city': city})

@app.route('/api/dashboard/keywords', methods=['GET'])
def dashboard_keywords():
    """Get unique keywords for the current project"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get unique keywords from point_history
    c.execute('''
        SELECT DISTINCT keyword 
        FROM point_history 
        WHERE project_id = ? AND keyword IS NOT NULL AND keyword != ''
        ORDER BY keyword ASC
    ''', (project_id,))
    
    keywords = [row[0] for row in c.fetchall()]
    conn.close()
    
    return jsonify({'keywords': keywords})

@app.route('/api/dashboard/points', methods=['GET'])
def dashboard_points():
    """Get all scan points with filters"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    keyword_filter = request.args.get('keyword', '')
    business_filter = request.args.get('business', '')
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    query = '''
        SELECT lat, lon, keyword, matched_business_name, 
               local_pack_rank, organic_rank, display_rank, scan_date, city
        FROM point_history
        WHERE project_id = ?
    '''
    params = [project_id]
    
    if keyword_filter:
        query += ' AND keyword = ?'
        params.append(keyword_filter)
    
    if business_filter:
        query += ' AND matched_business_name LIKE ?'
        params.append(f'%{business_filter}%')
    
    query += ' ORDER BY scan_date DESC LIMIT 1000'
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    points = []
    for row in rows:
        points.append({
            'lat': row[0],
            'lon': row[1],
            'city': row[8] if len(row) > 8 else None,  # City from database
            'keyword': row[2],
            'matched_business_name': row[3],
            'local_pack_rank': row[4],
            'organic_rank': row[5],
            'display_rank': row[6],
            'scan_date': row[7]
        })
    
    return jsonify({'points': points})


@app.route('/api/dashboard/delete', methods=['DELETE'])
def delete_dashboard_data():
    """Delete all scan data within a date range"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    data = request.get_json()
    date_from = data.get('date_from')
    date_to = data.get('date_to')

    if not date_from or not date_to:
        return jsonify({'error': 'Both date_from and date_to are required'}), 400

    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # Delete from point_history table
        # Use date() function to compare only date parts, ignoring time
        c.execute('''
            DELETE FROM point_history
            WHERE project_id = ? AND date(scan_date) >= date(?) AND date(scan_date) <= date(?)
        ''', (project_id, date_from, date_to))

        # Also delete from competitor_history (which has scan_date, not date)
        c.execute('''
            DELETE FROM competitor_history
            WHERE project_id = ? AND date(scan_date) >= date(?) AND date(scan_date) <= date(?)
        ''', (project_id, date_from, date_to))

        deleted_count = c.rowcount
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Successfully deleted {deleted_count} records from the selected date range'
        })

    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/city/<path:city_name>')
def city_detail(city_name):
    """Render city detail page"""
    project_id = session.get('project_id')
    if not project_id:
        return render_template('project_select.html')
    
    return render_template('city_detail.html', city_name=city_name)

@app.route('/api/city/<path:city_name>/data', methods=['GET'])
def city_data(city_name):
    """Get all historical data for a specific city"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    keyword_filter = request.args.get('keyword', '')
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get all historical scans for this city
    query = '''
        SELECT lat, lon, keyword, matched_business_name, 
               local_pack_rank, organic_rank, display_rank, scan_date
        FROM point_history
        WHERE project_id = ? AND city = ?
    '''
    params = [project_id, city_name]
    
    if keyword_filter:
        query += ' AND keyword = ?'
        params.append(keyword_filter)
    
    query += ' ORDER BY scan_date DESC'
    
    c.execute(query, params)
    rows = c.fetchall()
    
    historical_scans = []
    for row in rows:
        historical_scans.append({
            'lat': row[0],
            'lon': row[1],
            'keyword': row[2],
            'matched_business_name': row[3],
            'local_pack_rank': row[4],
            'organic_rank': row[5],
            'display_rank': row[6],
            'scan_date': row[7]
        })
    
    # Get unique keywords for this city
    c.execute('''
        SELECT DISTINCT keyword FROM point_history
        WHERE project_id = ? AND city = ?
        ORDER BY keyword ASC
    ''', (project_id, city_name))
    keywords = [row[0] for row in c.fetchall()]
    
    # Calculate rank trends over time
    trends_query = '''
        SELECT DATE(scan_date) as date,
               AVG(local_pack_rank) as avg_local_pack,
               AVG(organic_rank) as avg_organic,
               AVG(display_rank) as avg_display
        FROM point_history
        WHERE project_id = ? AND city = ?
    '''
    trends_params = [project_id, city_name]
    
    if keyword_filter:
        trends_query += ' AND keyword = ?'
        trends_params.append(keyword_filter)
    
    trends_query += '''
        GROUP BY DATE(scan_date)
        ORDER BY date ASC
    '''
    
    c.execute(trends_query, trends_params)
    trend_rows = c.fetchall()
    
    rank_trends = {
        'dates': [row[0] for row in trend_rows],
        'avg_local_pack': [float(row[1]) if row[1] else None for row in trend_rows],
        'avg_organic': [float(row[2]) if row[2] else None for row in trend_rows],
        'avg_display': [float(row[3]) if row[3] else None for row in trend_rows]
    }
    
    # Calculate keyword performance
    keyword_perf_query = '''
        SELECT keyword,
               AVG(display_rank) as avg_rank,
               COUNT(*) as scan_count,
               MIN(display_rank) as best_rank,
               MAX(display_rank) as worst_rank
        FROM point_history
        WHERE project_id = ? AND city = ? AND display_rank IS NOT NULL
        GROUP BY keyword
        ORDER BY avg_rank ASC
    '''
    
    c.execute(keyword_perf_query, (project_id, city_name))
    perf_rows = c.fetchall()
    
    keyword_performance = []
    for row in perf_rows:
        keyword_performance.append({
            'keyword': row[0],
            'avg_rank': round(row[1], 1) if row[1] else None,
            'scan_count': row[2],
            'best_rank': row[3],
            'worst_rank': row[4]
        })
    
    conn.close()
    
    return jsonify({
        'city': city_name,
        'total_points': len(historical_scans),
        'keywords': keywords,
        'historical_scans': historical_scans,
        'rank_trends': rank_trends,
        'keyword_performance': keyword_performance
    })

def run_scan_job(job_id, project_id, business_names, keywords, grid_spacing, bbox, polygon_coords, dummy_mode=False, cache_only=False):
    """
    Background function to run scan job with progress tracking
    Updates scan_jobs[job_id] with progress as it runs
    """
    logger.info(f"Scan job started - job_id: {job_id}, project_id: {project_id}")

    if not dummy_mode and not cache_only and not credentials_configured():
        with scan_jobs_lock:
            job = scan_jobs[job_id]
            job['status'] = 'error'
            job['error'] = (
                'DataForSEO login and password are missing. '
                'Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD in .env.'
            )
        logger.error("Scan %s aborted: DataForSEO credentials missing", job_id)
        return

    try:
        with scan_jobs_lock:
            job = scan_jobs[job_id]
            job['status'] = 'running'
            job['start_time'] = time.time()
        
        # Calculate grid FIRST to know total work units
        grid_points = calculate_grid(bbox, grid_spacing, polygon_coords)
        total_grid_points = len(grid_points)
        total_keywords = len(keywords)
        total_work_units = total_grid_points * total_keywords
        total_api_calls = total_work_units
        
        # Update job with totals
        with scan_jobs_lock:
            job = scan_jobs[job_id]
            job['total'] = total_work_units
            job['total_api_calls'] = total_api_calls
            job['total_grid_points'] = total_grid_points
            job['total_keywords'] = total_keywords

        if total_work_units == 0:
            with scan_jobs_lock:
                job = scan_jobs[job_id]
                job['status'] = 'error'
                job['error'] = 'The area has no grid points. Use a larger area or a smaller spacing.'
            return
        
        # Track timing for ETA calculation
        times_per_unit = []
        completed = 0
        completed_api_calls = 0
        
        # For each keyword, scan all grid points
        all_results = []
        
        for keyword in keywords:
            keyword_results = []
            for lat, lon in grid_points:
                # Check for cancellation
                with scan_jobs_lock:
                    if scan_jobs[job_id].get('status') == 'cancelled':
                        logger.info("Job %s cancelled during execution", job_id)
                        return

                unit_start = time.time()

                logger.debug("Point (%s, %s) keyword %s", lat, lon, keyword)

                try:
                    rank_data = fetch_local_rank(
                        lat,
                        lon,
                        business_names,
                        keyword,
                        grid_spacing=grid_spacing,
                        dummy_mode=dummy_mode,
                        cache_only=cache_only,
                    )
                except Exception as e:
                    logger.error("Rank check failed for %s at (%s, %s): %s", keyword, lat, lon, e, exc_info=True)
                    rank_data = {
                        'local_pack_rank': None,
                        'organic_rank': None,
                        'status': 'error',
                        'error': str(e),
                        'all_competitors': [],
                    }

                completed_api_calls += 1
                all_competitors = rank_data.get('all_competitors', [])

                try:
                    city = reverse_geocode(lat, lon, dummy_mode)
                except Exception as e:
                    city = f"{lat:.4f}, {lon:.4f}"
                    logger.warning("Reverse geocode failed for (%s, %s): %s", lat, lon, e)

                rank_data['display_rank'] = rank_data.get('local_pack_rank')
                if rank_data.get('status') != 'error':
                    rank_data['status'] = 'success' if rank_data.get('display_rank') else 'not_found'

                rank_data['lat'] = lat
                rank_data['lon'] = lon
                rank_data['keyword'] = keyword
                rank_data['city'] = city
                rank_data['landing_page_exists'] = False
                rank_data['landing_page_status_code'] = None
                rank_data['landing_page_url'] = None
                rank_data['all_competitors'] = all_competitors
                
                keyword_results.append(rank_data)
                
                # Update progress
                completed += 1
                unit_duration = time.time() - unit_start
                
                # Track timing for ETA (keep last 10 samples)
                times_per_unit.append(unit_duration)
                if len(times_per_unit) > 10:
                    times_per_unit.pop(0)
                
                # Calculate ETA
                avg_time = sum(times_per_unit) / len(times_per_unit) if times_per_unit else unit_duration
                remaining = total_work_units - completed
                eta_seconds = remaining * avg_time
                
                # Update job progress
                with scan_jobs_lock:
                    job = scan_jobs[job_id]
                    job['completed'] = completed
                    job['progress'] = (completed / total_work_units) * 100 if total_work_units > 0 else 0
                    job['completed_api_calls'] = completed_api_calls
                    job['eta_seconds'] = eta_seconds
                    job['current_keyword'] = keyword
                    job['current_point'] = f"{completed}/{total_work_units}"
                
            all_results.extend(keyword_results)
        
        # Save to database
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        scan_ids = []
        for keyword in keywords:
            primary_business_name = ', '.join(business_names[:3])
            if len(business_names) > 3:
                primary_business_name += '...'
            
            c.execute('''
                INSERT INTO scans (project_id, date, business_name, keyword, grid_spacing, 
                                  bbox_north, bbox_east, bbox_south, bbox_west)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (project_id, datetime.now().isoformat(), primary_business_name, keyword, grid_spacing,
                  bbox['north'], bbox['east'], bbox['south'], bbox['west']))
            
            scan_ids.append(c.lastrowid)
        
        point_idx = 0
        scan_date = datetime.now().isoformat()
        
        for keyword_idx, keyword in enumerate(keywords):
            scan_id = scan_ids[keyword_idx]
            primary_business_name = ', '.join(business_names[:3])
            if len(business_names) > 3:
                primary_business_name += '...'
            
            for _ in grid_points:
                point = all_results[point_idx]
                search_query = keyword
                
                c.execute('''
                    INSERT INTO scan_points (scan_id, lat, lon, local_pack_rank, 
                                           organic_rank, display_rank, status,
                                           matched_business_name, keyword, search_query)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (scan_id, point['lat'], point['lon'], 
                      point['local_pack_rank'], point['organic_rank'], 
                      point['display_rank'], point['status'],
                      point.get('matched_business_name'), keyword, search_query))
                
                scan_point_id = c.lastrowid
                
                # Save competitors and point history
                all_competitors = point.get('all_competitors', [])
                city = point.get('city', f"{point['lat']:.4f}, {point['lon']:.4f}")
                
                if all_competitors:
                    # Filter for local pack competitors for the snapshot/history
                    local_pack_competitors = [c for c in all_competitors if c.get('type') == 'local_pack']

                    # Deduplicate competitors within this point's results using normalized names
                    seen_normalized_names = set()
                    deduplicated_competitors = []

                    for competitor in local_pack_competitors:
                        normalized = normalize_competitor_name(competitor.get('name', ''))

                        if normalized not in seen_normalized_names:
                            seen_normalized_names.add(normalized)
                            deduplicated_competitors.append(competitor)
                        else:
                            logger.debug(f"Skipped duplicate competitor: {competitor.get('name')} (normalized: {normalized})")

                    for competitor in deduplicated_competitors:
                        if not (competitor.get('name') or '').strip():
                            continue
                        try:
                            # 1. Save to current snapshot
                            c.execute('''
                                INSERT INTO competitor_snapshots (scan_point_id, rank, competitor_name,
                                                                 review_count, rating_stars, address, 
                                                                 phone_number, website, category)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (scan_point_id, competitor.get('rank'), competitor.get('name'),
                                  competitor.get('review_count'), competitor.get('rating_stars'),
                                  competitor.get('address'), competitor.get('phone_number'),
                                  competitor.get('website'), competitor.get('category')))

                            # 2. Save to historical tracking
                            c.execute('''
                                INSERT INTO competitor_history (project_id, scan_point_id, competitor_name,
                                                               rank, review_count, rating_stars,
                                                               scan_date, keyword, city, address,
                                                               phone_number, website, category)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (project_id, scan_point_id, competitor.get('name'),
                                  competitor.get('rank'), competitor.get('review_count'),
                                  competitor.get('rating_stars'), scan_date, keyword, city,
                                  competitor.get('address'), competitor.get('phone_number'),
                                  competitor.get('website'), competitor.get('category')))

                        except Exception as e:
                            # Log error with full context for debugging
                            error_msg = f"Error saving competitor {competitor.get('name')}: {str(e)}"
                            logger.error(error_msg, exc_info=True)
                            logger.debug(f"Competitor data: {competitor}")
                            # Continue processing other competitors instead of silently failing

                # Save to point_history
                try:
                    c.execute('''
                        INSERT INTO point_history (project_id, lat, lon, keyword, business_name, scan_date,
                                                 local_pack_rank, organic_rank, display_rank,
                                                 matched_business_name, search_query, city)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (project_id, point['lat'], point['lon'], keyword, primary_business_name, scan_date,
                          point['local_pack_rank'], point['organic_rank'],
                          point['display_rank'], point.get('matched_business_name'), search_query, city))
                except sqlite3.OperationalError as e:
                    # If city column doesn't exist (old schema), fall back to insert without city
                    logger.warning(f"SQLite error on point_history insert with city field: {e}. Trying fallback schema.")
                    try:
                        c.execute('''
                            INSERT INTO point_history (project_id, lat, lon, keyword, business_name, scan_date,
                                                     local_pack_rank, organic_rank, display_rank,
                                                     matched_business_name, search_query)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (project_id, point['lat'], point['lon'], keyword, primary_business_name, scan_date,
                              point['local_pack_rank'], point['organic_rank'],
                              point['display_rank'], point.get('matched_business_name'), search_query))
                    except Exception as fallback_error:
                        logger.error(f"Failed to insert point_history even with fallback: {fallback_error}", exc_info=True)
                        raise
                
                point_idx += 1
        
        import json as json_lib
        business_names_json = json_lib.dumps(business_names)
        keywords_json = json_lib.dumps(keywords)
        now = datetime.now().isoformat()
        c.execute('UPDATE projects SET business_names = ?, keywords = ?, updated_at = ? WHERE id = ?',
                  (business_names_json, keywords_json, now, project_id))
        conn.commit()
        conn.close()
        
        # Remove all_competitors from response
        response_results = []
        for result in all_results:
            result_copy = result.copy()
            result_copy.pop('all_competitors', None)
            response_results.append(result_copy)
        
        # Mark job as complete
        with scan_jobs_lock:
            job = scan_jobs[job_id]
            job['status'] = 'complete'
            job['progress'] = 100.0
            job['completed'] = total_work_units
            job['completed_api_calls'] = total_api_calls
            job['results'] = response_results
            job['scan_ids'] = scan_ids
            job['eta_seconds'] = 0
        
    except Exception as e:
        # Mark job as failed
        with scan_jobs_lock:
            job = scan_jobs[job_id]
            job['status'] = 'error'
            job['error'] = str(e)
        logger.error(f"Scan job {job_id} failed: {str(e)}", exc_info=True)

@app.route('/api/scan-cache-only', methods=['POST'])
def scan_cache_only():
    """Handle cache-only scan request: uses only cached data, no API calls"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    data = request.json

    # Support both old format (single) and new format (arrays)
    business_names = data.get('business_names', [])
    keywords = data.get('keywords', [])

    # Fallback to old format for backward compatibility
    if not business_names:
        business_name = data.get('business_name', '').strip()
        if business_name:
            business_names = [business_name]

    if not keywords:
        keyword = data.get('keyword', '').strip()
        if keyword:
            keywords = [keyword]

    grid_spacing = float(data.get('grid_spacing', 2.0))
    bbox = data.get('bbox', {})
    polygon_coords = data.get('polygon_coords', None)

    # Validate inputs
    if not business_names or len(business_names) == 0:
        return jsonify({'error': 'At least one business name is required'}), 400

    if not keywords or len(keywords) == 0:
        return jsonify({'error': 'At least one keyword is required'}), 400

    if not bbox or not all(k in bbox for k in ['north', 'south', 'east', 'west']):
        return jsonify({'error': 'Invalid bounding box'}), 400

    # Validate polygon if provided
    if polygon_coords and len(polygon_coords) < 3:
        return jsonify({'error': 'Polygon must have at least 3 points'}), 400

    # Calculate grid to get total work units BEFORE starting
    grid_points = calculate_grid(bbox, grid_spacing, polygon_coords)
    total_grid_points = len(grid_points)
    total_keywords = len(keywords)
    total_work_units = total_grid_points * total_keywords
    if total_work_units == 0:
        return jsonify({'error': 'The area has no grid points. Use a larger area or a smaller spacing.'}), 400

    total_api_calls = 0

    # Create job
    job_id = str(uuid.uuid4())
    with scan_jobs_lock:
        scan_jobs[job_id] = {
            'status': 'starting',
            'progress': 0,
            'completed': 0,
            'total': total_work_units,
            'total_api_calls': total_api_calls,
            'completed_api_calls': 0,
            'total_grid_points': total_grid_points,
            'total_keywords': total_keywords,
            'results': None,
            'scan_ids': None,
            'start_time': None,
            'eta_seconds': None,
            'current_keyword': None,
            'current_point': None,
            'error': None
        }

    # Start background thread with cache-only mode
    thread = threading.Thread(
        target=run_scan_job,
        args=(job_id, project_id, business_names, keywords, grid_spacing, bbox, polygon_coords, False, True),  # False = not dummy mode, True = cache_only
        daemon=True
    )
    thread.start()

    return jsonify({
        'job_id': job_id,
        'total_work_units': total_work_units,
        'total_api_calls': total_api_calls,
        'total_grid_points': total_grid_points,
        'total_keywords': total_keywords,
        'cache_only': True
    })


@app.route('/api/scan', methods=['POST'])
def scan():
    """Handle scan request: start background job and return job_id"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400
    
    data = request.json
    
    # Support both old format (single) and new format (arrays)
    business_names = data.get('business_names', [])
    keywords = data.get('keywords', [])
    
    # Fallback to old format for backward compatibility
    if not business_names:
        business_name = data.get('business_name', '').strip()
        if business_name:
            business_names = [business_name]
    
    if not keywords:
        keyword = data.get('keyword', '').strip()
        if keyword:
            keywords = [keyword]
    
    grid_spacing = float(data.get('grid_spacing', 2.0))
    bbox = data.get('bbox', {})
    polygon_coords = data.get('polygon_coords', None)
    
    # Validate inputs
    if not business_names or len(business_names) == 0:
        return jsonify({'error': 'At least one business name is required'}), 400
    
    if not keywords or len(keywords) == 0:
        return jsonify({'error': 'At least one keyword is required'}), 400
    
    if not bbox or not all(k in bbox for k in ['north', 'south', 'east', 'west']):
        return jsonify({'error': 'Invalid bounding box'}), 400
    
    # Validate polygon if provided
    if polygon_coords and len(polygon_coords) < 3:
        return jsonify({'error': 'Polygon must have at least 3 points'}), 400
    
    # Calculate grid to get total work units BEFORE starting
    grid_points = calculate_grid(bbox, grid_spacing, polygon_coords)
    total_grid_points = len(grid_points)
    total_keywords = len(keywords)
    total_work_units = total_grid_points * total_keywords
    if total_work_units == 0:
        return jsonify({'error': 'The area has no grid points. Use a larger area or a smaller spacing.'}), 400
    if not is_dummy_mode() and not credentials_configured():
        return jsonify({
            'error': 'DataForSEO login and password are missing. Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD in .env.'
        }), 400

    total_api_calls = total_work_units
    
    # Create job
    job_id = str(uuid.uuid4())
    with scan_jobs_lock:
        scan_jobs[job_id] = {
            'status': 'starting',
            'progress': 0,
            'completed': 0,
            'total': total_work_units,
            'total_api_calls': total_api_calls,
            'completed_api_calls': 0,
            'total_grid_points': total_grid_points,
            'total_keywords': total_keywords,
            'results': None,
            'scan_ids': None,
            'start_time': None,
            'eta_seconds': None,
            'current_keyword': None,
            'current_point': None,
            'error': None
        }
    
    # Start background thread
    # Pass dummy mode setting to avoid session access in background thread
    dummy_mode = is_dummy_mode()
    thread = threading.Thread(
        target=run_scan_job,
        args=(job_id, project_id, business_names, keywords, grid_spacing, bbox, polygon_coords, dummy_mode),
        daemon=True
    )
    thread.start()
    
    return jsonify({
        'job_id': job_id,
        'total_work_units': total_work_units,
        'total_api_calls': total_api_calls,
        'total_grid_points': total_grid_points,
        'total_keywords': total_keywords
    })

@app.route('/api/scan/cancel', methods=['POST'])
def cancel_scan():
    """Cancel a running scan job"""
    print(f"[DEBUG] /api/scan/cancel called", flush=True)
    data = request.get_json()
    job_id = data.get('job_id')
    print(f"[DEBUG] Cancellation requested for job_id: {job_id}", flush=True)
    
    if not job_id:
        return jsonify({'error': 'No job_id provided'}), 400
        
    with scan_jobs_lock:
        if job_id in scan_jobs:
            current_status = scan_jobs[job_id]['status']
            print(f"[DEBUG] Job {job_id} current status: {current_status}", flush=True)
            if current_status in ['running', 'queued', 'starting']:
                scan_jobs[job_id]['status'] = 'cancelled'
                print(f"[INFO] Mark job {job_id} as cancelled by user", flush=True)
                return jsonify({'success': True, 'message': 'Scan cancellation requested'})
            else:
                print(f"[WARN] Job {job_id} is not running (status: {current_status})", flush=True)
                return jsonify({'error': f'Job is not running (status: {current_status})'}), 400
        else:
            print(f"[WARN] Job {job_id} not found in scan_jobs", flush=True)
            return jsonify({'error': 'Job not found'}), 404

@app.route('/api/scan/status', methods=['GET'])
def scan_status():
    """Get scan job status and progress"""
    job_id = request.args.get('job_id')
    if not job_id:
        return jsonify({'error': 'job_id parameter required'}), 400
    
    with scan_jobs_lock:
        job = scan_jobs.get(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Calculate elapsed time
        elapsed_seconds = None
        if job.get('start_time'):
            elapsed_seconds = time.time() - job['start_time']
        
        return jsonify({
            'status': job['status'],
            'progress': round(job['progress'], 2),
            'completed': job['completed'],
            'total': job['total'],
            'completed_api_calls': job.get('completed_api_calls', 0),
            'total_api_calls': job.get('total_api_calls', 0),
            'eta_seconds': round(job.get('eta_seconds', 0)) if job.get('eta_seconds') else None,
            'elapsed_seconds': round(elapsed_seconds) if elapsed_seconds else None,
            'current_keyword': job.get('current_keyword'),
            'current_point': job.get('current_point'),
            'error': job.get('error')
        })

@app.route('/api/scan/results', methods=['GET'])
def scan_results():
    """Get scan job results (only available when status is 'complete')"""
    job_id = request.args.get('job_id')
    if not job_id:
        return jsonify({'error': 'job_id parameter required'}), 400
    
    with scan_jobs_lock:
        job = scan_jobs.get(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        if job['status'] != 'complete':
            return jsonify({'error': 'Job not complete yet', 'status': job['status']}), 400
        
        return jsonify({
            'results': job['results'],
            'scan_ids': job['scan_ids'],
            'total_work_units': job['total'],
            'completed_api_calls': job.get('completed_api_calls', 0),
            'total_api_calls': job.get('total_api_calls', 0)
        })


@app.route('/api/polygons', methods=['GET'])
def get_saved_polygons():
    """Get all saved polygons for the current project"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('''
        SELECT id, name, coordinates, created_at, updated_at
        FROM saved_polygons
        WHERE project_id = ?
        ORDER BY updated_at DESC
    ''', (project_id,))

    polygons = []
    for row in c.fetchall():
        polygons.append({
            'id': row[0],
            'name': row[1],
            'coordinates': json.loads(row[2]),
            'created_at': row[3],
            'updated_at': row[4]
        })

    conn.close()
    return jsonify({'polygons': polygons})


@app.route('/api/polygons', methods=['POST'])
def save_polygon():
    """Save a polygon for the current project"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    data = request.json
    name = data.get('name', '').strip()
    coordinates = data.get('coordinates', [])

    if not name:
        return jsonify({'error': 'Polygon name is required'}), 400

    if not coordinates or len(coordinates) < 3:
        return jsonify({'error': 'Polygon must have at least 3 coordinates'}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Check if polygon with this name already exists
    c.execute('SELECT id FROM saved_polygons WHERE project_id = ? AND name = ?',
              (project_id, name))
    existing = c.fetchone()

    coordinates_json = json.dumps(coordinates)

    if existing:
        # Update existing polygon
        c.execute('''
            UPDATE saved_polygons
            SET coordinates = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (coordinates_json, existing[0]))
        polygon_id = existing[0]
    else:
        # Create new polygon
        c.execute('''
            INSERT INTO saved_polygons (project_id, name, coordinates)
            VALUES (?, ?, ?)
        ''', (project_id, name, coordinates_json))
        polygon_id = c.lastrowid

    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'polygon_id': polygon_id,
        'message': f'Polygon "{name}" saved successfully'
    })


@app.route('/api/polygons/<int:polygon_id>', methods=['DELETE'])
def delete_polygon(polygon_id):
    """Delete a saved polygon"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Delete only if it belongs to current project
    c.execute('DELETE FROM saved_polygons WHERE id = ? AND project_id = ?',
              (polygon_id, project_id))

    deleted = c.rowcount > 0
    conn.commit()
    conn.close()

    if deleted:
        return jsonify({'success': True, 'message': 'Polygon deleted successfully'})
    else:
        return jsonify({'error': 'Polygon not found'}), 404

def add_dummy_data(project_id):
    """Add 8 weeks of dummy scan data for testing"""
    from datetime import timedelta
    import random as rand
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Sample data
    business_names_dummy = ["My Business", "My Business Inc", "My Business LLC"]
    keywords_dummy = ["pizza delivery", "italian restaurant", "food near me"]
    dummy_locations = [
        (45.6251, 9.0352), (45.6350, 9.0450), (45.6150, 9.0250),
        (45.6450, 9.0550), (45.6050, 9.0150), (45.6550, 9.0650)
    ]
    
    # Generate 8 weekly scans going backwards from today (BEFORE today for historical data)
    # In testing mode, these should appear as past scans
    today = datetime.now()
    for week in range(1, 9):  # Start from week 1 (skip today), go back 8 weeks
        scan_date = today - timedelta(weeks=week)
        date_str = scan_date.isoformat()
        
        for keyword in keywords_dummy:
            # Create a scan record
            primary_business = ", ".join(business_names_dummy[:2])
            c.execute('''
                INSERT INTO scans (project_id, date, business_name, keyword, grid_spacing,
                                  bbox_north, bbox_east, bbox_south, bbox_west)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (project_id, date_str, primary_business, keyword, 2.0,
                  45.66, 9.07, 45.60, 9.00))
            scan_id = c.lastrowid
            
            # Add scan points with varying ranks (trending upward over time)
            for lat, lon in dummy_locations:
                # Simulate ranking improvement over time (better ranks in recent weeks)
                base_rank = 25 - (week * 2)  # Gets better each week
                local_pack_rank = rand.randint(1, 3) if base_rank < 5 else None
                organic_rank = max(1, min(30, base_rank + rand.randint(-3, 3)))
                display_rank = local_pack_rank if local_pack_rank else organic_rank
                
                c.execute('''
                    INSERT INTO scan_points (scan_id, lat, lon, local_pack_rank,
                                           organic_rank, display_rank, status,
                                           matched_business_name, keyword, search_query)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (scan_id, lat, lon, local_pack_rank, organic_rank, display_rank,
                      'success' if display_rank else 'not_found',
                      business_names_dummy[0] if local_pack_rank else None,
                      keyword, f"{primary_business} {keyword}"))
                
                # Get city name for dummy location
                city = reverse_geocode(lat, lon)
                
                # Add to point_history
                c.execute('''
                    INSERT INTO point_history (project_id, lat, lon, keyword, business_name, scan_date,
                                             local_pack_rank, organic_rank, display_rank,
                                             matched_business_name, search_query, city)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (project_id, lat, lon, keyword, primary_business, date_str,
                      local_pack_rank, organic_rank, display_rank,
                      business_names_dummy[0] if local_pack_rank else None,
                      f"{primary_business} {keyword}", city))
    
    conn.commit()
    conn.close()

# ============================================================================
# NEW FEATURE ENDPOINTS: Local SEO Reporting & Market Intelligence
# ============================================================================

@app.route('/api/business/performance', methods=['GET'])
def business_performance():
    """Feature 2: Your Business Performance Summary"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    keyword_filter = request.args.get('keyword', '')

    # Build query
    query = '''
        SELECT
            COUNT(*) as total_locations,
            AVG(CASE WHEN local_pack_rank IS NOT NULL THEN local_pack_rank END) as avg_local_pack_rank,
            AVG(CASE WHEN organic_rank IS NOT NULL THEN organic_rank END) as avg_organic_rank,
            SUM(CASE WHEN local_pack_rank IS NOT NULL THEN 1 ELSE 0 END) as local_pack_locations,
            SUM(CASE WHEN organic_rank IS NOT NULL THEN 1 ELSE 0 END) as organic_locations,
            SUM(CASE WHEN local_pack_rank BETWEEN 1 AND 3 THEN 1 ELSE 0 END) as top3_locations,
            SUM(CASE WHEN local_pack_rank BETWEEN 1 AND 10 THEN 1 ELSE 0 END) as top10_locations
        FROM scan_points sp
        INNER JOIN scans s ON sp.scan_id = s.id
        WHERE s.project_id = ?
    '''
    params = [project_id]

    if keyword_filter:
        query += ' AND sp.keyword = ?'
        params.append(keyword_filter)

    c.execute(query, params)
    row = c.fetchone()

    total_locations = row[0] or 0
    avg_local_pack = row[1]
    avg_organic = row[2]
    local_pack_locations = row[3] or 0
    organic_locations = row[4] or 0
    top3_locations = row[5] or 0
    top10_locations = row[6] or 0

    # Calculate percentages
    local_pack_pct = round((local_pack_locations / total_locations * 100), 1) if total_locations > 0 else 0
    organic_pct = round((organic_locations / total_locations * 100), 1) if total_locations > 0 else 0
    top3_pct = round((top3_locations / total_locations * 100), 1) if total_locations > 0 else 0
    top10_pct = round((top10_locations / total_locations * 100), 1) if total_locations > 0 else 0

    # Find best and worst performing locations
    c.execute('''
        SELECT lat, lon, local_pack_rank, organic_rank, keyword
        FROM scan_points
        WHERE scan_id IN (SELECT id FROM scans WHERE project_id = ?)
        ORDER BY local_pack_rank ASC, organic_rank ASC
        LIMIT 5
    ''', (project_id,))
    best_locations = [{
        'lat': row[0], 'lon': row[1],
        'local_pack_rank': row[2],
        'organic_rank': row[3],
        'keyword': row[4]
    } for row in c.fetchall()]

    c.execute('''
        SELECT lat, lon, local_pack_rank, organic_rank, keyword
        FROM scan_points
        WHERE scan_id IN (SELECT id FROM scans WHERE project_id = ?)
        AND (local_pack_rank IS NULL OR local_pack_rank > 10)
        ORDER BY local_pack_rank DESC
        LIMIT 5
    ''', (project_id,))
    worst_locations = [{
        'lat': row[0], 'lon': row[1],
        'local_pack_rank': row[2],
        'organic_rank': row[3],
        'keyword': row[4]
    } for row in c.fetchall()]

    conn.close()

    return jsonify({
        'total_locations': total_locations,
        'avg_local_pack_rank': round(avg_local_pack, 1) if avg_local_pack else None,
        'avg_organic_rank': round(avg_organic, 1) if avg_organic else None,
        'local_pack_presence_pct': local_pack_pct,
        'organic_presence_pct': organic_pct,
        'top3_coverage_pct': top3_pct,
        'top10_coverage_pct': top10_pct,
        'local_pack_locations': local_pack_locations,
        'organic_locations': organic_locations,
        'best_locations': best_locations,
        'worst_locations': worst_locations
    })

@app.route('/api/market/insights', methods=['GET'])
def market_insights():
    """Feature 3: Actionable Market Insights"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    keyword_filter = request.args.get('keyword', '')

    # Market Saturation: competitor count by keyword
    query = '''
        SELECT
            sp.keyword,
            COUNT(DISTINCT ch.competitor_name) as competitor_count,
            COUNT(DISTINCT sp.id) as location_count
        FROM scan_points sp
        INNER JOIN scans s ON sp.scan_id = s.id
        LEFT JOIN competitor_history ch ON ch.project_id = s.project_id
            AND ch.keyword = sp.keyword
        WHERE s.project_id = ?
    '''
    params = [project_id]

    if keyword_filter:
        query += ' AND sp.keyword = ?'
        params.append(keyword_filter)

    query += ' GROUP BY sp.keyword'

    c.execute(query, params)
    market_saturation = []
    for row in c.fetchall():
        keyword = row[0]
        competitors = row[1] or 0
        locations = row[2] or 0
        avg_competitors_per_location = round(competitors / locations, 1) if locations > 0 else 0

        # Saturation level
        if avg_competitors_per_location < 5:
            saturation = 'Low'
            opportunity = 'High'
        elif avg_competitors_per_location < 10:
            saturation = 'Medium'
            opportunity = 'Medium'
        else:
            saturation = 'High'
            opportunity = 'Low'

        market_saturation.append({
            'keyword': keyword,
            'saturation_level': saturation,
            'opportunity_level': opportunity,
            'total_competitors': competitors,
            'avg_per_location': avg_competitors_per_location
        })

    # Market Gap: locations where client doesn't appear
    c.execute('''
        SELECT COUNT(DISTINCT sp.id) FROM scan_points sp
        INNER JOIN scans s ON sp.scan_id = s.id
        WHERE s.project_id = ? AND sp.local_pack_rank IS NULL
    ''', (project_id,))
    gap_locations = c.fetchone()[0] or 0

    c.execute('''
        SELECT COUNT(DISTINCT sp.id) FROM scan_points sp
        INNER JOIN scans s ON sp.scan_id = s.id
        WHERE s.project_id = ?
    ''', (project_id,))
    total_locations = c.fetchone()[0] or 1

    gap_pct = round((gap_locations / total_locations * 100), 1) if total_locations > 0 else 0

    conn.close()

    return jsonify({
        'market_saturation': market_saturation,
        'market_gap': {
            'missing_locations': gap_locations,
            'total_locations': total_locations,
            'gap_percentage': gap_pct
        }
    })

@app.route('/api/competitors/comparison/<path:competitor_name>', methods=['GET'])
def competitor_comparison(competitor_name):
    """Feature 4: Competitor Comparison Tool"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    keyword_filter = request.args.get('keyword', '')

    # Get your business ranks
    query = '''
        SELECT sp.keyword, sp.local_pack_rank, sp.organic_rank
        FROM scan_points sp
        INNER JOIN scans s ON sp.scan_id = s.id
        WHERE s.project_id = ?
    '''
    params = [project_id]

    if keyword_filter:
        query += ' AND sp.keyword = ?'
        params.append(keyword_filter)

    c.execute(query, params)
    your_ranks = {}
    for row in c.fetchall():
        keyword = row[0]
        if keyword not in your_ranks:
            your_ranks[keyword] = {'local_pack': [], 'organic': []}
        if row[1]:
            your_ranks[keyword]['local_pack'].append(row[1])
        if row[2]:
            your_ranks[keyword]['organic'].append(row[2])

    # Calculate averages for your business
    your_avg = {}
    for keyword, ranks in your_ranks.items():
        your_avg[keyword] = {
            'avg_local_pack': round(sum(ranks['local_pack']) / len(ranks['local_pack']), 1) if ranks['local_pack'] else None,
            'avg_organic': round(sum(ranks['organic']) / len(ranks['organic']), 1) if ranks['organic'] else None
        }

    # Get competitor ranks
    c.execute('''
        SELECT keyword, AVG(rank) as avg_rank
        FROM competitor_history
        WHERE project_id = ? AND competitor_name = ?
    ''' + (' AND keyword = ?' if keyword_filter else ''),
    [project_id, competitor_name] + ([keyword_filter] if keyword_filter else []))

    competitor_ranks = {}
    for row in c.fetchall():
        competitor_ranks[row[0]] = round(row[1], 1) if row[1] else None

    # Calculate head-to-head
    comparison = []
    for keyword in set(list(your_avg.keys()) + list(competitor_ranks.keys())):
        your_rank = your_avg.get(keyword, {}).get('avg_local_pack')
        comp_rank = competitor_ranks.get(keyword)

        if your_rank and comp_rank:
            if your_rank < comp_rank:
                status = 'Winning'
            else:
                status = 'Losing'
            rank_diff = abs(your_rank - comp_rank)
        else:
            status = 'No data'
            rank_diff = None

        comparison.append({
            'keyword': keyword,
            'your_rank': your_rank,
            'competitor_rank': comp_rank,
            'head_to_head': status,
            'rank_difference': rank_diff
        })

    conn.close()

    return jsonify({
        'competitor': competitor_name,
        'comparison': comparison
    })

@app.route('/api/keywords/performance', methods=['GET'])
def keyword_performance():
    """Feature 5: Keyword Performance Matrix"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('''
        SELECT DISTINCT keyword FROM scan_points
        WHERE scan_id IN (SELECT id FROM scans WHERE project_id = ?)
    ''', (project_id,))

    keywords = [row[0] for row in c.fetchall()]
    performance = []

    for keyword in keywords:
        # Your performance for this keyword
        c.execute('''
            SELECT
                AVG(sp.local_pack_rank) as avg_rank,
                SUM(CASE WHEN sp.local_pack_rank BETWEEN 1 AND 3 THEN 1 ELSE 0 END) as top3_count,
                SUM(CASE WHEN sp.local_pack_rank BETWEEN 4 AND 10 THEN 1 ELSE 0 END) as top10_count,
                SUM(CASE WHEN sp.local_pack_rank BETWEEN 11 AND 30 THEN 1 ELSE 0 END) as top30_count,
                COUNT(DISTINCT sp.id) as total_locations
            FROM scan_points sp
            INNER JOIN scans s ON sp.scan_id = s.id
            WHERE s.project_id = ? AND sp.keyword = ?
        ''', (project_id, keyword))

        row = c.fetchone()
        avg_rank = row[0]
        top3_count = row[1] or 0
        top10_count = row[2] or 0
        top30_count = row[3] or 0
        total_locations = row[4] or 1

        # Competitor count
        c.execute('''
            SELECT COUNT(DISTINCT competitor_name) FROM competitor_history
            WHERE project_id = ? AND keyword = ?
        ''', (project_id, keyword))

        competitor_count = c.fetchone()[0] or 0

        # Difficulty score (0-100 based on avg rank and competitor count)
        difficulty = min(100, int((avg_rank or 50) * 2 + (competitor_count / 10)))
        opportunity = 100 - difficulty

        performance.append({
            'keyword': keyword,
            'avg_rank': round(avg_rank, 1) if avg_rank else None,
            'top3_locations': top3_count,
            'top10_locations': top10_count,
            'top30_locations': top30_count,
            'total_locations': total_locations,
            'competitor_count': competitor_count,
            'difficulty_score': difficulty,
            'opportunity_score': opportunity
        })

    conn.close()

    return jsonify({'keywords': performance})

@app.route('/api/heatmap/data', methods=['GET'])
def heatmap_data():
    """Feature 6: Enhanced Heatmap Data"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    keyword_filter = request.args.get('keyword', '')
    show_competitors = request.args.get('show_competitors', 'false').lower() == 'true'

    if show_competitors:
        # Competitor density heatmap
        c.execute('''
            SELECT
                lat, lon,
                COUNT(DISTINCT competitor_name) as competitor_count,
                AVG(rank) as avg_competitor_rank
            FROM competitor_history ch
            INNER JOIN scan_points sp ON ch.project_id = ? AND sp.keyword = ch.keyword
            WHERE ch.project_id = ?
        ''' + (' AND ch.keyword = ?' if keyword_filter else '') + '''
            GROUP BY lat, lon
        ''', [project_id, project_id] + ([keyword_filter] if keyword_filter else []))

        points = []
        for row in c.fetchall():
            competitor_count = row[2] or 0
            # Color density based on competitor count
            if competitor_count < 5:
                density = 'low'
            elif competitor_count < 10:
                density = 'medium'
            else:
                density = 'high'

            points.append({
                'lat': row[0],
                'lon': row[1],
                'type': 'competitor_density',
                'density': density,
                'competitor_count': competitor_count,
                'avg_rank': round(row[3], 1) if row[3] else None
            })
    else:
        # Your business performance heatmap
        c.execute('''
            SELECT lat, lon, local_pack_rank, organic_rank, keyword
            FROM scan_points
            WHERE scan_id IN (SELECT id FROM scans WHERE project_id = ?)
        ''' + (' AND keyword = ?' if keyword_filter else ''),
        [project_id] + ([keyword_filter] if keyword_filter else []))

        points = []
        for row in c.fetchall():
            local_pack_rank = row[2]

            # Determine performance color
            if local_pack_rank and local_pack_rank <= 3:
                performance = 'top3'
                color = 'green'
            elif local_pack_rank and local_pack_rank <= 10:
                performance = 'top10'
                color = 'yellow'
            elif local_pack_rank and local_pack_rank <= 30:
                performance = 'top30'
                color = 'orange'
            else:
                performance = 'no_rank'
                color = 'red'

            points.append({
                'lat': row[0],
                'lon': row[1],
                'type': 'your_business',
                'performance': performance,
                'color': color,
                'local_pack_rank': local_pack_rank,
                'organic_rank': row[3],
                'keyword': row[4]
            })

    conn.close()

    return jsonify({'points': points})

@app.route('/api/trends/growth', methods=['GET'])
def trends_growth():
    """Feature 7: Trending & Growth Metrics"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    keyword_filter = request.args.get('keyword', '')

    # Get recent vs older data
    c.execute('''
        SELECT
            DATE(MAX(scan_date)) as latest_date,
            AVG(rank) as latest_avg_rank
        FROM competitor_history
        WHERE project_id = ?
    ''' + (' AND keyword = ?' if keyword_filter else ''),
    [project_id] + ([keyword_filter] if keyword_filter else []))

    row = c.fetchone()
    latest_date = row[0]
    latest_avg_rank = row[1]

    # Get trends by competitor (top 10)
    c.execute('''
        SELECT
            competitor_name,
            COUNT(*) as appearances,
            AVG(rank) as avg_rank,
            MIN(rank) as best_rank,
            MAX(rank) as worst_rank
        FROM competitor_history
        WHERE project_id = ?
    ''' + (' AND keyword = ?' if keyword_filter else '') + '''
        GROUP BY competitor_name
        ORDER BY appearances DESC
        LIMIT 10
    ''', [project_id] + ([keyword_filter] if keyword_filter else []))

    top_competitors = [{
        'name': row[0],
        'appearances': row[1],
        'avg_rank': round(row[2], 1) if row[2] else None,
        'best_rank': row[3],
        'worst_rank': row[4]
    } for row in c.fetchall()]

    conn.close()

    return jsonify({
        'latest_date': latest_date,
        'market_avg_rank': round(latest_avg_rank, 1) if latest_avg_rank else None,
        'top_competitors': top_competitors
    })

@app.route('/api/export/report', methods=['GET'])
def export_report():
    """Feature 8: Export & Reporting - Generate JSON report"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Get project info
    c.execute('SELECT name, business_names, keywords FROM projects WHERE id = ?', (project_id,))
    proj = c.fetchone()

    report = {
        'generated_at': datetime.now().isoformat(),
        'project': {
            'name': proj[0],
            'business_names': json.loads(proj[1]),
            'keywords': json.loads(proj[2])
        },
        'performance': {},
        'market': {},
        'keywords': {}
    }

    conn.close()

    return jsonify(report)

@app.route('/api/history/comparison', methods=['GET'])
def history_comparison():
    """Feature 9: Historical Comparison - Month over month"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Get data grouped by month
    c.execute('''
        SELECT
            strftime('%Y-%m', scan_date) as month,
            AVG(CASE WHEN local_pack_rank IS NOT NULL THEN local_pack_rank END) as avg_local_pack,
            COUNT(DISTINCT id) as scan_count
        FROM point_history
        WHERE project_id = ?
        GROUP BY strftime('%Y-%m', scan_date)
        ORDER BY month DESC
        LIMIT 12
    ''', (project_id,))

    monthly_data = [{
        'month': row[0],
        'avg_rank': round(row[1], 1) if row[1] else None,
        'scan_count': row[2]
    } for row in c.fetchall()]

    conn.close()

    return jsonify({'monthly_history': monthly_data})

@app.route('/api/analysis/gaps', methods=['GET'])
def gap_analysis():
    """Feature 10: Gap Analysis Report"""
    project_id = session.get('project_id')
    if not project_id:
        return jsonify({'error': 'No project selected'}), 400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Find locations where you don't appear but competitors do
    c.execute('''
        SELECT
            sp.lat, sp.lon, sp.keyword,
            COUNT(DISTINCT ch.competitor_name) as competitor_count
        FROM scan_points sp
        LEFT JOIN competitor_history ch ON
            ch.project_id = ? AND ch.keyword = sp.keyword
        INNER JOIN scans s ON sp.scan_id = s.id
        WHERE s.project_id = ? AND sp.local_pack_rank IS NULL
        GROUP BY sp.lat, sp.lon, sp.keyword
        HAVING COUNT(DISTINCT ch.competitor_name) > 0
        LIMIT 20
    ''', (project_id, project_id))

    gaps = [{
        'lat': row[0],
        'lon': row[1],
        'keyword': row[2],
        'competitors_present': row[3],
        'gap_type': 'Missing Location'
    } for row in c.fetchall()]

    conn.close()

    return jsonify({'gaps': gaps})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
