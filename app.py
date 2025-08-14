# app.py
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- Mock Data and Functions ---
# A dictionary to simulate the output of 'pcm run <projectname>'.
# You can replace this with your actual logic to run the command.
MOCK_SERVICES = {
    'A': ['service-A1', 'service-A2', 'service-A3'],
    'B': ['service-B1', 'service-B2'],
    'C': ['service-C1', 'service-C2', 'service-C3', 'service-C4']
}

@app.route('/')
def index():
    """Renders the main page with all the UI elements."""
    projects = list(MOCK_SERVICES.keys())
    todos = ['Start', 'Stop', 'Restart']
    return render_template('index.html', projects=projects, todos=todos)

@app.route('/get_services', methods=['POST'])
def get_services():
    """
    An API endpoint to get a list of services for a given project.
    Simulates the 'pcm run <projectname>' command.
    """
    project_name = request.json.get('project')
    services = MOCK_SERVICES.get(project_name, [])
    return jsonify({'services': services})

@app.route('/run_command', methods=['POST'])
def run_command():
    """
    An API endpoint to simulate running the final command.
    """
    data = request.json
    project = data.get('project')
    todo = data.get('todo')
    service = data.get('service')
    
    # Construct the simulated command string.
    # Replace this with your actual subprocess call to run the command.
    command_to_run = f'pcm {todo} {project} {service}'
    
    # In a real-world scenario, you would execute the command here.
    # For example:
    # import subprocess
    # try:
    #     result = subprocess.run(command_to_run.split(), capture_output=True, text=True)
    #     return jsonify({'status': 'success', 'output': result.stdout})
    # except Exception as e:
    #     return jsonify({'status': 'error', 'output': str(e)})

    return jsonify({'status': 'success', 'command': command_to_run, 'message': 'Command has been prepared.'})

if __name__ == '__main__':
    app.run(debug=True)
