# user_service.py
# User Management API - Run this on port 5002
from flask import Flask, jsonify, request
from datetime import datetime

app = Flask(__name__)

# Mock user database
users = {
    1: {"id": 1, "name": "John Doe", "email": "john@example.com", "role": "admin"},
    2: {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "role": "user"},
    3: {"id": 3, "name": "Bob Wilson", "email": "bob@example.com", "role": "user"}
}

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "user-api"})

@app.route('/users')
def get_users():
    return jsonify({
        "users": list(users.values()),
        "total": len(users),
        "service": "user-api",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/users/<int:user_id>')
def get_user(user_id):
    if user_id in users:
        return jsonify({
            "user": users[user_id],
            "service": "user-api"
        })
    else:
        return jsonify({"error": "User not found"}), 404

@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    new_id = max(users.keys()) + 1 if users else 1
    
    new_user = {
        "id": new_id,
        "name": data.get("name", "Unknown"),
        "email": data.get("email", "unknown@example.com"),
        "role": data.get("role", "user"),
        "created": datetime.now().isoformat()
    }
    
    users[new_id] = new_user
    return jsonify({
        "message": "User created",
        "user": new_user,
        "service": "user-api"
    }), 201

@app.route('/users/<int:user_id>/profile')
def get_user_profile(user_id):
    if user_id in users:
        user = users[user_id]
        # Simulate a more detailed profile
        profile = {
            **user,
            "last_login": "2025-01-02T10:30:00",
            "preferences": {"theme": "dark", "notifications": True},
            "stats": {"logins": 42, "posts": 15}
        }
        return jsonify({
            "profile": profile,
            "service": "user-api"
        })
    else:
        return jsonify({"error": "User not found"}), 404

if __name__ == '__main__':
    print("👥 User API starting on port 5042")
    app.run(host='0.0.0.0', port=5042, debug=True)