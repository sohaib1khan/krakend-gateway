# simple_todo_api.py
from flask import Flask, jsonify, request
import json
import os
from datetime import datetime
import uuid

app = Flask(__name__)

# Data file
TODOS_FILE = 'todos.json'

def load_todos():
    """Load todos from JSON file"""
    if os.path.exists(TODOS_FILE):
        try:
            with open(TODOS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_todos(todos):
    """Save todos to JSON file"""
    with open(TODOS_FILE, 'w') as f:
        json.dump(todos, f, indent=2)

def find_todo_by_id(todo_id):
    """Find a todo by ID"""
    todos = load_todos()
    return next((todo for todo in todos if todo['id'] == todo_id), None)

# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.route('/')
def home():
    """API information"""
    return jsonify({
        "service": "Simple Todo API",
        "version": "1.0",
        "description": "A simple task management API",
        "endpoints": {
            "GET /": "API information",
            "GET /health": "Health check",
            "GET /todos": "List all todos",
            "POST /todos": "Create new todo",
            "GET /todos/{id}": "Get specific todo",
            "PUT /todos/{id}": "Update todo",
            "DELETE /todos/{id}": "Delete todo",
            "GET /stats": "Todo statistics"
        },
        "total_todos": len(load_todos()),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    todos = load_todos()
    return jsonify({
        "status": "healthy",
        "service": "todo-api",
        "total_todos": len(todos),
        "completed_todos": len([t for t in todos if t.get('completed', False)]),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/todos', methods=['GET'])
def get_todos():
    """Get all todos with optional filtering"""
    todos = load_todos()
    
    # Optional query parameters
    status = request.args.get('status')  # completed, pending
    priority = request.args.get('priority')  # high, medium, low
    
    filtered_todos = todos
    
    # Filter by completion status
    if status == 'completed':
        filtered_todos = [t for t in filtered_todos if t.get('completed', False)]
    elif status == 'pending':
        filtered_todos = [t for t in filtered_todos if not t.get('completed', False)]
    
    # Filter by priority
    if priority:
        filtered_todos = [t for t in filtered_todos if t.get('priority', '').lower() == priority.lower()]
    
    return jsonify({
        "todos": filtered_todos,
        "total": len(filtered_todos),
        "filters_applied": {
            "status": status,
            "priority": priority
        },
        "timestamp": datetime.now().isoformat()
    })

@app.route('/todos', methods=['POST'])
def create_todo():
    """Create a new todo"""
    data = request.get_json()
    
    if not data or 'title' not in data:
        return jsonify({"error": "Title is required"}), 400
    
    # Validate title
    if len(data['title'].strip()) == 0:
        return jsonify({"error": "Title cannot be empty"}), 400
    
    todos = load_todos()
    
    new_todo = {
        "id": str(uuid.uuid4())[:8],  # Short UUID
        "title": data['title'].strip(),
        "description": data.get('description', '').strip(),
        "completed": False,
        "priority": data.get('priority', 'medium').lower(),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "due_date": data.get('due_date'),
        "tags": data.get('tags', [])
    }
    
    # Validate priority
    if new_todo['priority'] not in ['low', 'medium', 'high']:
        new_todo['priority'] = 'medium'
    
    todos.append(new_todo)
    save_todos(todos)
    
    return jsonify({
        "message": "Todo created successfully",
        "todo": new_todo
    }), 201

@app.route('/todos/<todo_id>', methods=['GET'])
def get_todo(todo_id):
    """Get a specific todo by ID"""
    todo = find_todo_by_id(todo_id)
    
    if not todo:
        return jsonify({"error": "Todo not found"}), 404
    
    return jsonify({
        "todo": todo,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/todos/<todo_id>', methods=['PUT'])
def update_todo(todo_id):
    """Update a specific todo"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    todos = load_todos()
    todo_index = next((i for i, todo in enumerate(todos) if todo['id'] == todo_id), None)
    
    if todo_index is None:
        return jsonify({"error": "Todo not found"}), 404
    
    todo = todos[todo_index]
    
    # Update fields if provided
    if 'title' in data:
        if len(data['title'].strip()) == 0:
            return jsonify({"error": "Title cannot be empty"}), 400
        todo['title'] = data['title'].strip()
    
    if 'description' in data:
        todo['description'] = data['description'].strip()
    
    if 'completed' in data:
        todo['completed'] = bool(data['completed'])
    
    if 'priority' in data:
        priority = data['priority'].lower()
        if priority in ['low', 'medium', 'high']:
            todo['priority'] = priority
    
    if 'due_date' in data:
        todo['due_date'] = data['due_date']
    
    if 'tags' in data:
        todo['tags'] = data['tags'] if isinstance(data['tags'], list) else []
    
    todo['updated_at'] = datetime.now().isoformat()
    
    todos[todo_index] = todo
    save_todos(todos)
    
    return jsonify({
        "message": "Todo updated successfully",
        "todo": todo
    })

@app.route('/todos/<todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    """Delete a specific todo"""
    todos = load_todos()
    todo_index = next((i for i, todo in enumerate(todos) if todo['id'] == todo_id), None)
    
    if todo_index is None:
        return jsonify({"error": "Todo not found"}), 404
    
    deleted_todo = todos.pop(todo_index)
    save_todos(todos)
    
    return jsonify({
        "message": "Todo deleted successfully",
        "deleted_todo": {
            "id": deleted_todo['id'],
            "title": deleted_todo['title']
        }
    })

@app.route('/stats')
def get_stats():
    """Get todo statistics"""
    todos = load_todos()
    
    total = len(todos)
    completed = len([t for t in todos if t.get('completed', False)])
    pending = total - completed
    
    # Priority breakdown
    priorities = {'high': 0, 'medium': 0, 'low': 0}
    for todo in todos:
        priority = todo.get('priority', 'medium')
        if priority in priorities:
            priorities[priority] += 1
    
    # Recent activity (todos created in last 7 days)
    from datetime import timedelta
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent = len([t for t in todos if datetime.fromisoformat(t.get('created_at', '1970-01-01T00:00:00')) > seven_days_ago])
    
    return jsonify({
        "total_todos": total,
        "completed": completed,
        "pending": pending,
        "completion_rate": round((completed / total * 100) if total > 0 else 0, 1),
        "priority_breakdown": priorities,
        "recent_todos": recent,
        "service": "todo-api",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/todos/complete/<todo_id>', methods=['POST'])
def complete_todo(todo_id):
    """Mark a todo as completed"""
    todos = load_todos()
    todo_index = next((i for i, todo in enumerate(todos) if todo['id'] == todo_id), None)
    
    if todo_index is None:
        return jsonify({"error": "Todo not found"}), 404
    
    todos[todo_index]['completed'] = True
    todos[todo_index]['updated_at'] = datetime.now().isoformat()
    todos[todo_index]['completed_at'] = datetime.now().isoformat()
    
    save_todos(todos)
    
    return jsonify({
        "message": "Todo marked as completed",
        "todo": todos[todo_index]
    })

@app.route('/todos/bulk', methods=['POST'])
def bulk_create_todos():
    """Create multiple todos at once"""
    data = request.get_json()
    
    if not data or 'todos' not in data or not isinstance(data['todos'], list):
        return jsonify({"error": "Provide 'todos' array"}), 400
    
    if len(data['todos']) > 50:
        return jsonify({"error": "Maximum 50 todos per bulk request"}), 400
    
    todos = load_todos()
    created_todos = []
    
    for todo_data in data['todos']:
        if 'title' not in todo_data or len(todo_data['title'].strip()) == 0:
            continue  # Skip invalid todos
        
        new_todo = {
            "id": str(uuid.uuid4())[:8],
            "title": todo_data['title'].strip(),
            "description": todo_data.get('description', '').strip(),
            "completed": False,
            "priority": todo_data.get('priority', 'medium').lower(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "due_date": todo_data.get('due_date'),
            "tags": todo_data.get('tags', [])
        }
        
        if new_todo['priority'] not in ['low', 'medium', 'high']:
            new_todo['priority'] = 'medium'
        
        todos.append(new_todo)
        created_todos.append(new_todo)
    
    save_todos(todos)
    
    return jsonify({
        "message": f"Created {len(created_todos)} todos",
        "created_todos": created_todos,
        "total_todos": len(todos)
    }), 201

if __name__ == '__main__':
    # Initialize with sample data if file doesn't exist
    if not os.path.exists(TODOS_FILE):
        sample_todos = [
            {
                "id": "todo001",
                "title": "Learn API Gateway concepts",
                "description": "Study how KrakenD routes requests to backend services",
                "completed": True,
                "priority": "high",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
                "tags": ["learning", "devops"]
            },
            {
                "id": "todo002", 
                "title": "Test distributed API setup",
                "description": "Create multiple backend services and route through gateway",
                "completed": False,
                "priority": "medium",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "due_date": "2025-07-05",
                "tags": ["testing", "api"]
            },
            {
                "id": "todo003",
                "title": "Build monitoring dashboard",
                "description": "Add real-time monitoring to KrakenD management interface",
                "completed": False,
                "priority": "low",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "tags": ["monitoring", "dashboard"]
            }
        ]
        save_todos(sample_todos)
    
    print("📝 Todo API starting...")
    print("🚀 Service: Simple Todo/Task Management")
    print("📍 Available endpoints:")
    print("   GET  /           - API information")
    print("   GET  /health     - Health check")
    print("   GET  /todos      - List todos (supports ?status=completed&priority=high)")
    print("   POST /todos      - Create new todo")
    print("   GET  /todos/{id} - Get specific todo")
    print("   PUT  /todos/{id} - Update todo") 
    print("   DELETE /todos/{id} - Delete todo")
    print("   POST /todos/complete/{id} - Mark as completed")
    print("   POST /todos/bulk - Create multiple todos")
    print("   GET  /stats      - Todo statistics")
    print()
    print("🌐 API running on http://0.0.0.0:4000")
    print("📊 Ready to be proxied by KrakenD!")
    
    app.run(host='0.0.0.0', port=4000, debug=True)