# weather_service.py
# Simple Weather API - Run this on port 5001
from flask import Flask, jsonify
import random
from datetime import datetime

app = Flask(__name__)

# Mock weather data
cities = {
    "tokyo": {"temp": 25, "humidity": 60, "condition": "sunny"},
    "london": {"temp": 15, "humidity": 80, "condition": "rainy"},
    "newyork": {"temp": 20, "humidity": 55, "condition": "cloudy"},
    "sydney": {"temp": 22, "humidity": 65, "condition": "sunny"}
}

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "weather-api"})

@app.route('/weather/<city>')
def get_weather(city):
    city_lower = city.lower()
    if city_lower in cities:
        weather = cities[city_lower].copy()
        # Add some randomness to make it interesting
        weather["temp"] += random.randint(-3, 3)
        weather["humidity"] += random.randint(-10, 10)
        weather["timestamp"] = datetime.now().isoformat()
        return jsonify({
            "city": city.title(),
            "weather": weather,
            "source": "weather-service"
        })
    else:
        return jsonify({"error": "City not found"}), 404

@app.route('/weather')
def list_cities():
    return jsonify({
        "available_cities": list(cities.keys()),
        "total_cities": len(cities),
        "service": "weather-api"
    })

if __name__ == '__main__':
    print("🌤️ Weather API starting on port 5074")
    app.run(host='0.0.0.0', port=5074, debug=True)