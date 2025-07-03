# task_service.py
# Task Management API - Run this on port 5003
from flask import Flask, jsonify, request
from datetime import datetime
import random

app = Flask(__name__)

# Mock task database
tasks = {
    1: {"id": 1, "title": "Learn KrakenD", "completed": False, "priority": "high", "user_id": 1},
    2: {"id": 2, "title": "Build Flask APIs", "completed": True, "priority": "medium", "user_id": 1},
    3: {"id": 3, "title": "Setup Docker", "completed": False, "priority": "low", "user_id": 2},
    4: {"id": 4, "title": "Configure Proxmox", "completed": True, "priority": "high", "user_id": 1}
}

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "task-api"})

@app.route('/tasks')
def get_tasks():
    user_id = request.args.get('user_id', type=int)
    status = request.args.get('status')  # 'completed' or 'pending'
    
    filtered_tasks = list(tasks.values())
    
    # Filter by user_id if provided
    if user_id:
        filtered_tasks = [t for t in filtered_tasks if t['user_id'] == user_id]
    
    # Filter by status if provided
    if status == 'completed':
        filtered_tasks = [t for t in filtered_tasks if t['completed']]
    elif status == 'pending':
        filtered_tasks = [t for t in filtered_tasks if not t['completed']]
    
    return jsonify({
        "tasks": filtered_tasks,
        "total": len(filtered_tasks),
        "filters": {"user_id": user_id, "status": status},
        "service": "task-api",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/tasks/<int:task_id>')
def get_task(task_id):
    if task_id in tasks:
        return jsonify({
            "task": tasks[task_id],
            "service": "task-api"
        })
    else:
        return jsonify({"error": "Task not found"}), 404

@app.route('/tasks', methods=['POST'])
def create_task():
    data = request.get_json()
    new_id = max(tasks.keys()) + 1 if tasks else 1
    
    new_task = {
        "id": new_id,
        "title": data.get("title", "New Task"),
        "completed": False,
        "priority": data.get("priority", "medium"),
        "user_id": data.get("user_id", 1),
        "created": datetime.now().isoformat()
    }
    
    tasks[new_id] = new_task
    return jsonify({
        "message": "Task created",
        "task": new_task,
        "service": "task-api"
    }), 201

@app.route('/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    if task_id in tasks:
        tasks[task_id]['completed'] = True
        tasks[task_id]['completed_at'] = datetime.now().isoformat()
        return jsonify({
            "message": "Task completed",
            "task": tasks[task_id],
            "service": "task-api"
        })
    else:
        return jsonify({"error": "Task not found"}), 404

@app.route('/tasks/stats')
def get_task_stats():
    total = len(tasks)
    completed = sum(1 for t in tasks.values() if t['completed'])
    pending = total - completed
    
    priorities = {"high": 0, "medium": 0, "low": 0}
    for task in tasks.values():
        priorities[task['priority']] += 1
    
    return jsonify({
        "stats": {
            "total": total,
            "completed": completed,
            "pending": pending,
            "completion_rate": round((completed / total * 100), 1) if total > 0 else 0
        },
        "priorities": priorities,
        "service": "task-api"
    })

if __name__ == '__main__':
    print("📝 Task API starting on port 5003")
    app.run(host='0.0.0.0', port=5003, debug=True)