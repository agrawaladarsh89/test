from flask import Flask, render_template, request, jsonify, session
import subprocess
import json
from typing import List, Optional

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

def run_command(command: str) -> tuple[bool, str]:
    """
    Execute a shell command and return success status and output
    """
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, f"Error executing command: {str(e)}"

def get_services_for_project(project: str) -> List[str]:
    """
    Get list of services for a given project by running pcm run <projectname>
    """
    command = f"pcm run {project}"
    success, output = run_command(command)
    
    if success and output:
        # Assuming the command returns services one per line or comma-separated
        # Adjust this parsing logic based on your actual pcm command output format
        services = [service.strip() for service in output.split('\n') if service.strip()]
        return services
    else:
        # Return empty list if command fails
        return []

@app.route('/', methods=['GET', 'POST'])
def index():
    projects = ['A', 'B', 'C']
    todo_options = ['Start', 'Stop', 'Restart']
    
    # Initialize session variables if they don't exist
    if 'services' not in session:
        session['services'] = []
    if 'selected_project' not in session:
        session['selected_project'] = None
    
    selected_project = request.form.get('project')
    selected_service = request.form.get('service')
    selected_todo = request.form.get('todo')
    
    services = []
    service_error = None
    
    # If project changed, load services
    if selected_project and selected_project != session.get('selected_project'):
        session['selected_project'] = selected_project
        services = get_services_for_project(selected_project)
        session['services'] = services
        if not services:
            service_error = f"No services found for the selected project or failed to load services."
    elif selected_project:
        services = session.get('services', [])
    
    # Check if all options are selected
    all_selected = all([selected_project, selected_service, selected_todo])
    command = None
    if all_selected:
        command = f"pcm {selected_todo.lower()} {selected_project} {selected_service}"
    
    # Calculate missing items
    missing_items = []
    if not selected_project:
        missing_items.append("Project")
    if not selected_service:
        missing_items.append("Service")
    if not selected_todo:
        missing_items.append("Action")
    
    return render_template('index.html', 
                         projects=projects,
                         todo_options=todo_options,
                         selected_project=selected_project,
                         selected_service=selected_service,
                         selected_todo=selected_todo,
                         services=services,
                         service_error=service_error,
                         all_selected=all_selected,
                         command=command,
                         missing_items=missing_items,
                         service_count=len(services) if services else 0)

@app.route('/get_services', methods=['POST'])
def get_services():
    """AJAX endpoint to get services for a project"""
    project = request.json.get('project')
    if not project:
        return jsonify({'error': 'No project specified'}), 400
    
    services = get_services_for_project(project)
    session['services'] = services
    session['selected_project'] = project
    
    return jsonify({
        'services': services,
        'count': len(services)
    })

@app.route('/execute', methods=['POST'])
def execute_command():
    """Execute the PCM command"""
    command = request.form.get('command')
    if not command:
        return jsonify({'error': 'No command specified'}), 400
    
    success, output = run_command(command)
    
    return render_template('result.html',
                         command=command,
                         success=success,
                         output=output)

@app.route('/confirm', methods=['POST'])
def confirm_command():
    """Show confirmation page"""
    command = request.form.get('command')
    selected_project = request.form.get('project')
    selected_service = request.form.get('service')
    selected_todo = request.form.get('todo')
    
    return render_template('confirm.html',
                         command=command,
                         selected_project=selected_project,
                         selected_service=selected_service,
                         selected_todo=selected_todo)

if __name__ == "__main__":
    app.run(debug=True)
