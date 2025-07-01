# secure_quiz_api.py - Basic API Security Added
from flask import Flask, jsonify, request
from functools import wraps
import json
import os
from datetime import datetime

app = Flask(__name__)

# Simple API key (in production, use environment variables!)
API_KEY = "quiz-api-key-12345"

def require_api_key(f):
    """Decorator to require API key for endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != API_KEY:
            return jsonify({
                "error": "Invalid or missing API key",
                "hint": "Add 'X-API-Key: quiz-api-key-12345' header"
            }), 401
        return f(*args, **kwargs)
    return decorated_function

def validate_input(data, required_fields):
    """Helper to validate request data"""
    if not data:
        return "No data provided"
    
    for field in required_fields:
        if field not in data:
            return f"Missing required field: {field}"
        
        # Basic sanitization
        if isinstance(data[field], str):
            if '<script>' in data[field].lower():
                return f"Invalid characters in {field}"
            if len(data[field].strip()) == 0:
                return f"{field} cannot be empty"
    
    return None

# Data file helpers (same as before)
def load_json_file(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return []

def save_json_file(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

# =============================================================================
# SECURED API ENDPOINTS
# =============================================================================

@app.route('/api/questions', methods=['GET'])
@require_api_key  # 🔒 Security added!
def get_questions():
    """API: Get all quiz questions (requires API key)"""
    questions = load_json_file('questions.json')
    
    # Don't include correct answers in the response!
    safe_questions = []
    for q in questions:
        safe_q = {
            "id": q["id"],
            "question": q["question"],
            "options": q["options"]
            # Notice: no "correct_answer" field!
        }
        safe_questions.append(safe_q)
    
    return jsonify({
        "questions": safe_questions,
        "total": len(safe_questions),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/users', methods=['POST'])
@require_api_key  # 🔒 Security added!
def create_user():
    """API: Create a new user (requires API key)"""
    data = request.get_json()
    
    # Validate input
    error = validate_input(data, ['username'])
    if error:
        return jsonify({"error": error}), 400
    
    # Additional validation
    username = data['username'].strip()
    if len(username) < 3 or len(username) > 20:
        return jsonify({"error": "Username must be 3-20 characters"}), 400
    
    users = load_json_file('users.json')
    
    # Check if username already exists
    if any(u['username'] == username for u in users):
        return jsonify({"error": "Username already exists"}), 409
    
    new_user = {
        "id": len(users) + 1,
        "username": username,
        "email": data.get('email', '').strip(),
        "created_at": datetime.now().isoformat(),
        "quiz_scores": []
    }
    
    users.append(new_user)
    save_json_file('users.json', users)
    
    return jsonify({
        "message": "User created successfully",
        "user": {
            "id": new_user["id"],
            "username": new_user["username"],
            "created_at": new_user["created_at"]
            # Don't return email for privacy
        }
    }), 201

@app.route('/api/quiz/submit', methods=['POST'])
@require_api_key  # 🔒 Security added!
def submit_quiz():
    """API: Submit quiz answers (requires API key)"""
    data = request.get_json()
    
    # Validate input
    error = validate_input(data, ['user_id', 'answers'])
    if error:
        return jsonify({"error": error}), 400
    
    # Check if user exists
    users = load_json_file('users.json')
    user = next((u for u in users if u['id'] == data['user_id']), None)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Validate answers format
    if not isinstance(data['answers'], list):
        return jsonify({"error": "Answers must be a list"}), 400
    
    # Load questions to check answers
    questions = load_json_file('questions.json')
    results = load_json_file('results.json')
    
    # Calculate score
    correct_answers = 0
    total_questions = len(data['answers'])
    
    for answer in data['answers']:
        if not isinstance(answer, dict) or 'question_id' not in answer or 'answer' not in answer:
            continue
            
        question_id = answer.get('question_id')
        user_answer = answer.get('answer')
        
        question = next((q for q in questions if q.get('id') == question_id), None)
        if question and question.get('correct_answer') == user_answer:
            correct_answers += 1
    
    score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
    
    # Save result
    result = {
        "id": len(results) + 1,
        "user_id": data['user_id'],
        "username": user['username'],  # Include username for easier tracking
        "score": round(score, 2),
        "correct_answers": correct_answers,
        "total_questions": total_questions,
        "submitted_at": datetime.now().isoformat()
        # Don't save actual answers for privacy
    }
    
    results.append(result)
    save_json_file('results.json', results)
    
    return jsonify({
        "message": "Quiz submitted successfully",
        "result": {
            "score": result['score'],
            "correct_answers": correct_answers,
            "total_questions": total_questions,
            "rank": "Coming soon!"  # You could add ranking logic
        }
    })

# =============================================================================
# PUBLIC ENDPOINTS (no API key required)
# =============================================================================

@app.route('/')
def home():
    """Public: Home page (no API key required)"""
    return '''
    <h1>🔒 Secured Quiz App</h1>
    <p>This app now has API security!</p>
    
    <h2>🔓 Public Access:</h2>
    <ul>
        <li>This home page</li>
        <li>Basic info endpoint</li>
    </ul>
    
    <h2>🔒 Requires API Key:</h2>
    <ul>
        <li>GET /api/questions</li>
        <li>POST /api/users</li>
        <li>POST /api/quiz/submit</li>
    </ul>
    
    <h3>🧪 Test with API key:</h3>
    <pre>curl -H "X-API-Key: quiz-api-key-12345" http://localhost:3007/api/questions</pre>
    
    <h3>❌ Test without API key (should fail):</h3>
    <pre>curl http://localhost:3007/api/questions</pre>
    '''

@app.route('/api/info')
def api_info():
    """Public: API information (no key required)"""
    return jsonify({
        "service": "Secured Quiz API",
        "version": "1.0",
        "status": "running",
        "authentication": "API key required for most endpoints",
        "documentation": "See home page for usage examples"
    })

# =============================================================================
# ADMIN ENDPOINTS (would need stronger auth in production)
# =============================================================================

@app.route('/api/admin/stats')
@require_api_key
def admin_stats():
    """Admin: Get system statistics"""
    users = load_json_file('users.json')
    results = load_json_file('results.json')
    questions = load_json_file('questions.json')
    
    return jsonify({
        "total_users": len(users),
        "total_quiz_attempts": len(results),
        "total_questions": len(questions),
        "average_score": sum(r['score'] for r in results) / len(results) if results else 0,
        "generated_at": datetime.now().isoformat()
    })

if __name__ == '__main__':
    # Create sample data
    if not os.path.exists('questions.json'):
        sample_questions = [
            {
                "id": 1,
                "question": "What is the capital of France?",
                "options": ["London", "Berlin", "Paris", "Madrid"],
                "correct_answer": "Paris"
            },
            {
                "id": 2,
                "question": "What is 2 + 2?",
                "options": ["3", "4", "5", "6"],
                "correct_answer": "4"
            }
        ]
        save_json_file('questions.json', sample_questions)
    
    for file in ['users.json', 'results.json']:
        if not os.path.exists(file):
            save_json_file(file, [])
    
    print("🔒 Secured Quiz API starting...")
    print("🔑 API Key: quiz-api-key-12345")
    print("📱 Home: http://localhost:3007")
    print("\n🧪 Test commands:")
    print('curl -H "X-API-Key: quiz-api-key-12345" http://localhost:3007/api/questions')
    print('curl http://localhost:3007/api/questions  # Should fail!')
    
    app.run(host='0.0.0.0', port=3007, debug=True)