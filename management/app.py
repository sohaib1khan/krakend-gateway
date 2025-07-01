# Enhanced app.py with Real-time Monitoring Features
from flask import Flask, request, jsonify, session, send_from_directory
from functools import wraps
import json
import os
import subprocess
import time
import requests
from datetime import datetime, timedelta
import sqlite3
import threading

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# Simple user store (in production, use a database)
USERS = {
    'admin': 'krakend123',
    'user': 'password123',
    'demo': 'demo123'
}

# Configuration paths
CONFIG_PATH = '/app/config/krakend.json'
BACKUP_DIR = '/workspace/management/backups'

# Request metrics storage (in-memory for demo, use database in production)
request_metrics = {
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'avg_response_time': 0,
    'recent_requests': []
}

# Database setup for request logging
def init_database():
    """Initialize SQLite database for request logging"""
    conn = sqlite3.connect('request_logs.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            method TEXT,
            endpoint TEXT,
            status_code INTEGER,
            response_time INTEGER,
            client_ip TEXT,
            backend_url TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            service_url TEXT,
            status TEXT,
            response_time INTEGER,
            error_message TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_database()

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'logged_in': False, 'message': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def log_request_to_db(method, endpoint, status_code, response_time, client_ip, backend_url=None):
    """Log request to database"""
    try:
        conn = sqlite3.connect('request_logs.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO request_logs (method, endpoint, status_code, response_time, client_ip, backend_url)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (method, endpoint, status_code, response_time, client_ip, backend_url))
        
        conn.commit()
        conn.close()
        
        # Update in-memory metrics
        request_metrics['total_requests'] += 1
        if status_code < 400:
            request_metrics['successful_requests'] += 1
        else:
            request_metrics['failed_requests'] += 1
            
        # Add to recent requests (keep last 100)
        request_metrics['recent_requests'].append({
            'timestamp': datetime.now().isoformat(),
            'method': method,
            'endpoint': endpoint,
            'status_code': status_code,
            'response_time': response_time,
            'client_ip': client_ip
        })
        
        if len(request_metrics['recent_requests']) > 100:
            request_metrics['recent_requests'].pop(0)
            
    except Exception as e:
        print(f"Error logging request: {e}")

# ================================================================================
# AUTHENTICATION ENDPOINTS
# ================================================================================

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if username in USERS and USERS[username] == password:
        session['user'] = username
        return jsonify({'success': True, 'message': 'Login successful', 'username': username})
    
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/auth/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/auth/status')
def auth_status():
    if 'user' in session:
        return jsonify({'logged_in': True, 'username': session['user']})
    return jsonify({'logged_in': False})

# ================================================================================
# MONITORING ENDPOINTS
# ================================================================================

@app.route('/api/monitoring/metrics')
@require_auth
def get_metrics():
    """Get real-time metrics for monitoring dashboard"""
    return jsonify({
        'total_requests': request_metrics['total_requests'],
        'successful_requests': request_metrics['successful_requests'],
        'failed_requests': request_metrics['failed_requests'],
        'success_rate': (request_metrics['successful_requests'] / max(request_metrics['total_requests'], 1)) * 100,
        'recent_requests': request_metrics['recent_requests'][-20:],  # Last 20 requests
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/monitoring/logs')
@require_auth
def get_request_logs():
    """Get recent request logs"""
    try:
        conn = sqlite3.connect('request_logs.db')
        cursor = conn.cursor()
        
        # Get last 50 requests
        cursor.execute('''
            SELECT timestamp, method, endpoint, status_code, response_time, client_ip, backend_url
            FROM request_logs 
            ORDER BY timestamp DESC 
            LIMIT 50
        ''')
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                'timestamp': row[0],
                'method': row[1],
                'endpoint': row[2],
                'status_code': row[3],
                'response_time': row[4],
                'client_ip': row[5],
                'backend_url': row[6]
            })
        
        conn.close()
        return jsonify({'logs': logs})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/monitoring/health-check', methods=['POST'])
@require_auth
def check_backend_health():
    """Check health of a specific backend service"""
    data = request.get_json()
    service_url = data.get('url')
    
    if not service_url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        start_time = time.time()
        response = requests.get(service_url, timeout=5)
        response_time = int((time.time() - start_time) * 1000)
        
        # Log health check to database
        conn = sqlite3.connect('request_logs.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO health_checks (service_url, status, response_time)
            VALUES (?, ?, ?)
        ''', (service_url, 'healthy' if response.ok else 'unhealthy', response_time))
        conn.commit()
        conn.close()
        
        return jsonify({
            'url': service_url,
            'status': 'healthy' if response.ok else 'unhealthy',
            'status_code': response.status_code,
            'response_time': response_time,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        # Log failed health check
        conn = sqlite3.connect('request_logs.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO health_checks (service_url, status, response_time, error_message)
            VALUES (?, ?, ?, ?)
        ''', (service_url, 'error', 0, str(e)))
        conn.commit()
        conn.close()
        
        return jsonify({
            'url': service_url,
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/monitoring/health-history/<path:service_url>')
@require_auth
def get_health_history(service_url):
    """Get health check history for a service"""
    try:
        conn = sqlite3.connect('request_logs.db')
        cursor = conn.cursor()
        
        # Get last 24 hours of health checks
        yesterday = datetime.now() - timedelta(days=1)
        cursor.execute('''
            SELECT timestamp, status, response_time, error_message
            FROM health_checks 
            WHERE service_url = ? AND timestamp > ?
            ORDER BY timestamp DESC
        ''', (service_url, yesterday.isoformat()))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'timestamp': row[0],
                'status': row[1],
                'response_time': row[2],
                'error_message': row[3]
            })
        
        conn.close()
        return jsonify({'service_url': service_url, 'history': history})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ================================================================================
# EXISTING CONFIGURATION ENDPOINTS (Enhanced)
# ================================================================================

@app.route('/config')
@require_auth
def get_config():
    """Get current KrakenD configuration with enhanced metadata"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        # Enhanced metadata
        metadata = {
            'total_endpoints': len(config.get('endpoints', [])),
            'port': config.get('port', 8684),
            'cors_enabled': 'security/cors' in config.get('extra_config', {}),
            'last_modified': datetime.fromtimestamp(os.path.getmtime(CONFIG_PATH)).isoformat(),
            'file_size': os.path.getsize(CONFIG_PATH),
            'version': config.get('version', 'unknown')
        }
        
        return jsonify({
            'config': config,
            'metadata': metadata
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/endpoints', methods=['POST'])
@require_auth
def add_endpoint():
    """Add new endpoint with request logging"""
    try:
        data = request.get_json()
        
        # Log this configuration change
        log_request_to_db(
            method='POST',
            endpoint='/endpoints',
            status_code=200,
            response_time=0,
            client_ip=request.remote_addr,
            backend_url=data.get('backend_host', 'N/A')
        )
        
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        new_endpoint = {
            "endpoint": data['endpoint'],
            "method": data['method'],
            "output_encoding": "json",
            "backend": [
                {
                    "url_pattern": data.get('backend_path', data['endpoint']),
                    "encoding": "json",
                    "sd": "static",
                    "method": data['method'],
                    "host": [data['backend_host']]
                }
            ]
        }
        
        if 'endpoints' not in config:
            config['endpoints'] = []
        
        config['endpoints'].append(new_endpoint)
        
        # Create backup before saving
        backup_config()
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({
            'message': 'Endpoint added successfully',
            'endpoint': new_endpoint
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/validate')
@require_auth
def validate_config():
    """Validate KrakenD configuration with enhanced checks"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        issues = []
        
        # Basic validation
        if 'version' not in config:
            issues.append("Missing 'version' field")
        
        if 'port' not in config:
            issues.append("Missing 'port' field")
        
        endpoints = config.get('endpoints', [])
        
        # Validate endpoints
        for i, endpoint in enumerate(endpoints):
            if 'endpoint' not in endpoint:
                issues.append(f"Endpoint {i}: Missing 'endpoint' field")
            
            if 'backend' not in endpoint or not endpoint['backend']:
                issues.append(f"Endpoint {i}: Missing or empty 'backend' configuration")
            
            # Check for duplicate endpoints
            endpoint_path = endpoint.get('endpoint')
            method = endpoint.get('method', 'GET')
            duplicates = [e for e in endpoints if e.get('endpoint') == endpoint_path and e.get('method') == method]
            if len(duplicates) > 1:
                issues.append(f"Duplicate endpoint found: {method} {endpoint_path}")
        
        return jsonify({
            'valid': len(issues) == 0,
            'issues': issues,
            'endpoints_count': len(endpoints),
            'config_size': os.path.getsize(CONFIG_PATH),
            'validation_time': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'valid': False}), 500

@app.route('/restart', methods=['POST'])
@require_auth
def restart_gateway():
    """Restart KrakenD gateway with logging"""
    try:
        # Log restart action
        log_request_to_db(
            method='POST',
            endpoint='/restart',
            status_code=200,
            response_time=0,
            client_ip=request.remote_addr,
            backend_url='system'
        )
        
        # In a real implementation, this would restart the actual KrakenD process
        # For now, we'll simulate it
        result = subprocess.run(['docker-compose', 'restart', 'krakend'], 
                              capture_output=True, text=True, cwd='/workspace')
        
        if result.returncode == 0:
            return jsonify({
                'message': 'KrakenD restarted successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'error': f'Restart failed: {result.stderr}',
                'timestamp': datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def backup_config():
    """Create a backup of the current configuration"""
    try:
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'krakend_config_{timestamp}.json'
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        with open(CONFIG_PATH, 'r') as src, open(backup_path, 'w') as dst:
            dst.write(src.read())
        
        # Keep only last 10 backups
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('krakend_config_')])
        while len(backups) > 10:
            os.remove(os.path.join(BACKUP_DIR, backups.pop(0)))
            
    except Exception as e:
        print(f"Backup failed: {e}")

@app.route('/endpoints/<path:endpoint_path>', methods=['DELETE'])
@require_auth
def remove_endpoint(endpoint_path):
    """Remove endpoint with logging"""
    try:
        # Log this action
        log_request_to_db(
            method='DELETE',
            endpoint=f'/endpoints/{endpoint_path}',
            status_code=200,
            response_time=0,
            client_ip=request.remote_addr,
            backend_url='config'
        )
        
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        endpoint_path = '/' + endpoint_path if not endpoint_path.startswith('/') else endpoint_path
        
        original_count = len(config.get('endpoints', []))
        config['endpoints'] = [ep for ep in config.get('endpoints', []) 
                             if ep.get('endpoint') != endpoint_path]
        
        if len(config['endpoints']) == original_count:
            return jsonify({'error': 'Endpoint not found'}), 404
        
        # Create backup before saving
        backup_config()
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({'message': 'Endpoint removed successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ================================================================================
# STATIC FILE SERVING
# ================================================================================

@app.route('/')
@require_auth
def index():
    return send_from_directory('/workspace/web-ui', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('/workspace/web-ui', filename)

@app.route('/doc/')
def documentation():
    return send_from_directory('/workspace/docs', 'index.html')

# ================================================================================
# REQUEST LOGGING MIDDLEWARE
# ================================================================================

@app.before_request
def log_incoming_request():
    """Log incoming requests for monitoring"""
    # Skip logging for static files and auth checks
    if request.endpoint in ['serve_static', 'auth_status', 'get_metrics', 'get_request_logs']:
        return
        
    request.start_time = time.time()

@app.after_request
def log_outgoing_response(response):
    """Log outgoing responses for monitoring"""
    if hasattr(request, 'start_time') and request.endpoint:
        response_time = int((time.time() - request.start_time) * 1000)
        
        # Skip logging for certain endpoints to avoid infinite loops
        if request.endpoint not in ['get_metrics', 'get_request_logs', 'serve_static']:
            log_request_to_db(
                method=request.method,
                endpoint=request.path,
                status_code=response.status_code,
                response_time=response_time,
                client_ip=request.remote_addr
            )
    
    return response

if __name__ == '__main__':
    print("🚀 Enhanced KrakenD Management API starting...")
    print("📊 Real-time monitoring enabled")
    print("🏥 Health dashboard available")
    print("📱 Web UI: http://localhost:5001")
    print("🔑 Default credentials:")
    print("   admin / krakend123")
    print("   user / password123") 
    print("   demo / demo123")
    
    app.run(host='0.0.0.0', port=5001, debug=True)