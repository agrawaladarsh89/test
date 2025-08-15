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

def get_microservices_for_app_env_space(application: str, environment: str, space: str) -> List[str]:
    """
    Get list of microservices for a given application, environment and space
    by running: dws pcf get apps -c applicationname -e environment name -s spacename
    """
    command = f"dws pcf get apps -c {application} -e {environment} -s {space}"
    success, output = run_command(command)
    
    if success and output:
        # Parse the output to extract microservice names
        # This assumes the output is either:
        # 1. One microservice per line
        # 2. JSON array format
        # 3. Comma/space separated values
        
        microservices = []
        
        # Try to parse as JSON first
        try:
            import json
            parsed = json.loads(output)
            if isinstance(parsed, list):
                microservices = [str(item).strip() for item in parsed if str(item).strip()]
            elif isinstance(parsed, dict) and 'apps' in parsed:
                microservices = [str(app).strip() for app in parsed['apps'] if str(app).strip()]
            else:
                microservices = [str(parsed).strip()] if str(parsed).strip() else []
        except (json.JSONDecodeError, ValueError):
            # If not JSON, try line-by-line parsing
            lines = output.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('-'):
                    # Skip header lines or comment lines
                    # Split by common separators and take the first meaningful part
                    parts = line.split()
                    if parts:
                        microservices.append(parts[0])
        
        # Remove duplicates and empty entries
        microservices = list(set([ms for ms in microservices if ms and ms.strip()]))
        return sorted(microservices)
    else:
        # Return empty list if command fails
        return []

@app.route('/', methods=['GET', 'POST'])
def index():
    applications = ['IFP', 'ODRP', 'FACFLOW']
    environments = ['dev-pnf', 'prd-pnf']
    
    # Dynamic spaces based on environment
    def get_spaces_for_environment(env):
        if env == 'dev-pnf':
            return ['dev', 'nft', 'sit']
        elif env == 'prd-pnf':
            return ['prd']
        return []
    
    datacentres = ['edi01', 'edi02']
    todo_options = ['start', 'stop', 'restart']
    
    # Initialize session variables if they don't exist
    if 'microservices' not in session:
        session['microservices'] = []
    if 'selected_application' not in session:
        session['selected_application'] = None
    if 'selected_environment' not in session:
        session['selected_environment'] = None
    if 'selected_space' not in session:
        session['selected_space'] = None
    
    selected_application = request.form.get('application')
    selected_environment = request.form.get('environment')
    selected_space = request.form.get('space')
    selected_datacentre = request.form.get('datacentre')
    selected_microservice = request.form.get('microservice')
    selected_action = request.form.get('action')
    
    # Get available spaces for selected environment
    available_spaces = get_spaces_for_environment(selected_environment) if selected_environment else []
    
    # Reset space selection if environment changed and current space is not valid
    if selected_environment != session.get('selected_environment'):
        if selected_space and selected_space not in available_spaces:
            selected_space = None
    
    microservices = []
    microservice_error = None
    
    # If application, environment or space changed, load microservices
    app_env_space_changed = (
        (selected_application and selected_application != session.get('selected_application')) or
        (selected_environment and selected_environment != session.get('selected_environment')) or
        (selected_space and selected_space != session.get('selected_space'))
    )
    
    if selected_application and selected_environment and selected_space and app_env_space_changed:
        session['selected_application'] = selected_application
        session['selected_environment'] = selected_environment
        session['selected_space'] = selected_space
        microservices = get_microservices_for_app_env_space(selected_application, selected_environment, selected_space)
        session['microservices'] = microservices
        if not microservices:
            microservice_error = f"No microservices found for {selected_application} in {selected_environment}-{selected_space} or failed to load microservices."
    elif selected_application and selected_environment and selected_space:
        microservices = session.get('microservices', [])
    
    # Check if all options are selected
    all_selected = all([selected_application, selected_environment, selected_space, selected_datacentre, selected_microservice, selected_action])
    command = None
    if all_selected:
        command = f"dws pcf operations {selected_action} -c {selected_application} -e {selected_environment} -s {selected_space} -a {selected_microservice} -f {selected_datacentre} --action {selected_action}"
    
    # Calculate missing items
    missing_items = []
    if not selected_application:
        missing_items.append("Application")
    if not selected_environment:
        missing_items.append("Environment")
    if not selected_space:
        missing_items.append("Space")
    if not selected_datacentre:
        missing_items.append("Datacentre")
    if not selected_microservice:
        missing_items.append("Microservice")
    if not selected_action:
        missing_items.append("Action")
    
    return render_template('index.html', 
                         applications=applications,
                         environments=environments,
                         available_spaces=available_spaces,
                         datacentres=datacentres,
                         todo_options=todo_options,
                         selected_application=selected_application,
                         selected_environment=selected_environment,
                         selected_space=selected_space,
                         selected_datacentre=selected_datacentre,
                         selected_microservice=selected_microservice,
                         selected_action=selected_action,
                         microservices=microservices,
                         microservice_error=microservice_error,
                         all_selected=all_selected,
                         command=command,
                         missing_items=missing_items,
                         microservice_count=len(microservices) if microservices else 0)

@app.route('/get_spaces', methods=['POST'])
def get_spaces():
    """AJAX endpoint to get spaces for an environment"""
    environment = request.json.get('environment')
    
    if not environment:
        return jsonify({'error': 'Environment must be specified'}), 400
    
    if environment == 'dev-pnf':
        spaces = ['dev', 'nft', 'sit']
    elif environment == 'prd-pnf':
        spaces = ['prd']
    else:
        spaces = []
    
    return jsonify({
        'spaces': spaces,
        'count': len(spaces)
    })

@app.route('/get_microservices', methods=['POST'])
def get_microservices():
    """AJAX endpoint to get microservices for an application, environment and space"""
    application = request.json.get('application')
    environment = request.json.get('environment')
    space = request.json.get('space')
    
    if not application or not environment or not space:
        return jsonify({'error': 'Application, environment and space must all be specified'}), 400
    
    microservices = get_microservices_for_app_env_space(application, environment, space)
    session['microservices'] = microservices
    session['selected_application'] = application
    session['selected_environment'] = environment
    session['selected_space'] = space
    
    return jsonify({
        'microservices': microservices,
        'count': len(microservices)
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
    selected_application = request.form.get('application')
    selected_environment = request.form.get('environment')
    selected_space = request.form.get('space')
    selected_datacentre = request.form.get('datacentre')
    selected_microservice = request.form.get('microservice')
    selected_action = request.form.get('action')
    
    return render_template('confirm.html',
                         command=command,
                         selected_application=selected_application,
                         selected_environment=selected_environment,
                         selected_space=selected_space,
                         selected_datacentre=selected_datacentre,
                         selected_microservice=selected_microservice,
                         selected_action=selected_action)

if __name__ == "__main__":
    app.run(debug=True)
