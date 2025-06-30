from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
import json
import os
import subprocess
import shutil
from datetime import datetime
from functools import wraps

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://xxx.xxx.x.xx:3000"])
app.secret_key = 'krakend-secret-key-change-in-production'

CONFIG_PATH = '/app/config/krakend.json'
BACKUP_DIR = '/app/backups'

# Simple user store (in production, use a database)
USERS = {
    'admin': 'krakend123',
    'user': 'password123',
    'demo': 'demo123'
}

os.makedirs(BACKUP_DIR, exist_ok=True)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'error': 'Authentication required', 'redirect': '/login'}), 401
        return f(*args, **kwargs)
    return decorated_function

def load_config():
    """Load current KrakenD configuration"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"Failed to load config: {str(e)}"}

def save_config(config):
    """Save configuration with backup"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{BACKUP_DIR}/krakend_backup_{timestamp}.json"
        shutil.copy2(CONFIG_PATH, backup_path)
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
        return {"success": True, "backup": backup_path}
    except Exception as e:
        return {"error": f"Failed to save config: {str(e)}"}

# Authentication endpoints
@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if username in USERS and USERS[username] == password:
        session['logged_in'] = True
        session['username'] = username
        session['login_time'] = datetime.now().isoformat()
        return jsonify({
            'success': True, 
            'username': username,
            'message': f'Welcome back, {username}!'
        })
    
    return jsonify({'error': 'Invalid username or password'}), 401

@app.route('/auth/logout', methods=['POST'])
def logout():
    username = session.get('username', 'Unknown')
    session.clear()
    return jsonify({'success': True, 'message': f'Goodbye, {username}!'})

@app.route('/auth/status')
def auth_status():
    if 'logged_in' in session:
        return jsonify({
            'logged_in': True, 
            'username': session.get('username'),
            'login_time': session.get('login_time')
        })
    return jsonify({'logged_in': False})

# Protected management endpoints
@app.route('/')
def home():
    return jsonify({
        "service": "KrakenD Configuration Manager",
        "version": "1.0",
        "authentication": "enabled",
        "endpoints": {
            "POST /auth/login": "User login",
            "POST /auth/logout": "User logout", 
            "GET /auth/status": "Check auth status",
            "GET /config": "Get current configuration",
            "POST /config": "Update configuration",
            "POST /endpoints": "Add new endpoint",
            "DELETE /endpoints/<endpoint>": "Remove endpoint",
            "POST /restart": "Restart KrakenD",
            "GET /validate": "Validate current configuration"
        }
    })

@app.route('/config', methods=['GET'])
@login_required
def get_config():
    """Get current KrakenD configuration"""
    config = load_config()
    if "error" in config:
        return jsonify(config), 500
    
    metadata = {
        "total_endpoints": len(config.get("endpoints", [])),
        "port": config.get("port", 8080),
        "cors_enabled": "server/cors" in config.get("extra_config", {}),
        "timeout": config.get("timeout", "3000ms"),
        "last_modified": datetime.now().isoformat()
    }
    
    return jsonify({"config": config, "metadata": metadata})

@app.route('/endpoints', methods=['POST'])
@login_required
def add_endpoint():
    """Add a new endpoint"""
    try:
        config = load_config()
        if "error" in config:
            return jsonify(config), 500
        
        data = request.get_json()
        
        new_endpoint = {
            "endpoint": data["endpoint"],
            "method": data["method"],
            "output_encoding": "json",
            "backend": [{
                "url_pattern": data["backend_path"],
                "encoding": "json",
                "method": data["method"],
                "host": [data["backend_host"]],
                "disable_host_sanitize": False
            }]
        }
        
        if data.get("headers"):
            new_endpoint["input_headers"] = data["headers"]
        
        config["endpoints"].append(new_endpoint)
        
        result = save_config(config)
        if "error" in result:
            return jsonify(result), 500
            
        return jsonify({
            "success": True, 
            "endpoint": new_endpoint,
            "message": f"Endpoint {data['endpoint']} created by {session.get('username')}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/endpoints/<path:endpoint_path>', methods=['DELETE'])
@login_required
def remove_endpoint(endpoint_path):
    """Remove an endpoint"""
    try:
        config = load_config()
        if "error" in config:
            return jsonify(config), 500
        
        original_count = len(config["endpoints"])
        config["endpoints"] = [ep for ep in config["endpoints"] if ep["endpoint"] != f"/{endpoint_path}"]
        
        if len(config["endpoints"]) == original_count:
            return jsonify({"error": "Endpoint not found"}), 404
        
        result = save_config(config)
        if "error" in result:
            return jsonify(result), 500
            
        return jsonify({
            "success": True, 
            "message": f"Endpoint /{endpoint_path} removed by {session.get('username')}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/restart', methods=['POST'])
@login_required
def restart_gateway():
    """Restart KrakenD gateway"""
    try:
        subprocess.run(['docker', 'restart', 'krakend-gateway'], check=True)
        return jsonify({
            "success": True, 
            "message": f"KrakenD restarted by {session.get('username')}"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to restart KrakenD: {str(e)}"}), 500

@app.route('/validate', methods=['GET'])
@login_required
def validate_config():
    """Validate current configuration"""
    config = load_config()
    if "error" in config:
        return jsonify(config), 500
    
    issues = []
    
    if not config.get("endpoints"):
        issues.append("No endpoints configured")
    
    if not config.get("port"):
        issues.append("No port specified")
    
    endpoints = [ep["endpoint"] for ep in config.get("endpoints", [])]
    duplicates = set([ep for ep in endpoints if endpoints.count(ep) > 1])
    if duplicates:
        issues.append(f"Duplicate endpoints found: {list(duplicates)}")
    
    for ep in config.get("endpoints", []):
        for backend in ep.get("backend", []):
            if not backend.get("host"):
                issues.append(f"Endpoint {ep['endpoint']}: No backend host specified")
    
    return jsonify({
        "valid": len(issues) == 0,
        "issues": issues,
        "endpoints_count": len(config.get("endpoints", [])),
        "config_size": len(json.dumps(config)),
        "validated_by": session.get('username')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

