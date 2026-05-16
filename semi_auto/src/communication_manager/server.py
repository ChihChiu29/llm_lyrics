import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Queue of interactions
# Each interaction is a dict: { 'id': str, 'input_string': str, 'output_string': str, 'status': str }
# Status can be: 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'
interactions_queue = []

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
    return jsonify({'id': interaction_id, 'status': interaction['status']}), 201

@app.route('/api/interaction/next', methods=['GET'])
def peek_next_interaction():
    if not interactions_queue:
        return jsonify(None), 200
        
    # The "next" interaction is the first one in the queue
    return jsonify(interactions_queue[0]), 200

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
    if 'output_string' in data:
        next_interaction['output_string'] = data['output_string']
        
    # When completed or failed, remove from queue
    if next_interaction['status'] in ['COMPLETED', 'FAILED']:
        interactions_queue.pop(0)
        
    return jsonify(next_interaction), 200

@app.route('/api/interactions', methods=['GET'])
def list_interactions():
    return jsonify(interactions_queue), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
