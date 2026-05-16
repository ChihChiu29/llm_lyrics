import uuid
import time
import json
import threading
from collections import deque
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Queue of interactions
# Each interaction is a dict: { 'id': str, 'input_string': str, 'output_string': str, 'status': str }
# Status can be: 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'
interactions_queue = []

# Logging setup
interaction_logs = deque(maxlen=1000)
log_lock = threading.Lock()

def write_log_event(event_type, interaction):
    event = {
        'timestamp': time.time(),
        'event_type': event_type,
        'interaction': dict(interaction)
    }
    interaction_logs.append(event)
    
    with log_lock:
        try:
            with open('server_log.json', 'w', encoding='utf-8') as f:
                json.dump(list(interaction_logs), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to write log: {e}")

@app.route('/api/interaction', methods=['POST'])
def add_interaction():
    data = request.json
    if not data or 'input_string' not in data:
        return jsonify({'error': 'input_string is required'}), 400
        
    interaction_id = str(uuid.uuid4())
    interaction = {
        'id': interaction_id,
        'input_string': data['input_string'],
        'output_string': None,
        'status': 'PENDING'
    }
    
    interactions_queue.append(interaction)
    write_log_event('NEW', interaction)
    return jsonify({'id': interaction_id, 'status': interaction['status']}), 201

@app.route('/api/interaction/next', methods=['GET'])
def peek_next_interaction():
    if not interactions_queue:
        return jsonify(None), 200
        
    current_time = time.time()
    for interaction in interactions_queue:
        if interaction['status'] == 'RUNNING' and 'running_since' in interaction:
            if current_time - interaction['running_since'] > 300: # 5 minutes timeout
                interaction['status'] = 'PENDING'
                del interaction['running_since']
                print(f"Reset stuck interaction {interaction['id']} to PENDING")
                write_log_event('TIMEOUT_RESET', interaction)
                
    # The "next" interaction is the first one in the queue
    next_interaction = interactions_queue[0]
    if next_interaction['status'] == 'PENDING':
        return jsonify(next_interaction), 200
    else:
        # If the first interaction is still RUNNING and not expired, return None to keep client waiting
        return jsonify(None), 200

@app.route('/api/interaction/next', methods=['PUT'])
def update_next_interaction():
    if not interactions_queue:
        return jsonify({'error': 'Queue is empty'}), 404
        
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    next_interaction = interactions_queue[0]
    
    if 'status' in data:
        next_interaction['status'] = data['status']
        if data['status'] == 'RUNNING':
            next_interaction['running_since'] = time.time()
        elif 'running_since' in next_interaction:
            del next_interaction['running_since']
            
    if 'output_string' in data:
        next_interaction['output_string'] = data['output_string']
        
    write_log_event(next_interaction['status'], next_interaction)
        
    # When completed or failed, remove from queue
    if next_interaction['status'] in ['COMPLETED', 'FAILED']:
        interactions_queue.pop(0)
        
    return jsonify(next_interaction), 200

@app.route('/api/interactions', methods=['GET'])
def list_interactions():
    return jsonify(interactions_queue), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
