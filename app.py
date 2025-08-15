from flask import Flask, render_template, request, jsonify, session
import subprocess
import json
import re
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
        microservices = []
        
        # Handle the format: http response code: ["a","b","c","d"]
        # First, try to find JSON array pattern in the output
        json_pattern = r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]'
        json_match = re.search(json_pattern, output)
        
        if json_match:
            # Found JSON array pattern, extract and parse it
            json_str = json_match.group()
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    microservices = [str(item).strip().strip('"') for item in parsed if str(item).strip()]
                else:
                    microservices = [str(parsed).strip().strip('"')] if str(parsed).strip() else []
            except (json.JSONDecodeError, ValueError):
                pass
        
        # If JSON parsing didn't work, try alternative parsing methods
        if not microservices:
            # Try to parse as full JSON first
            try:
                parsed = json.loads(output)
                if isinstance(parsed, list):
                    microservices = [str(item).strip().strip('"') for item in parsed if str(item).strip()]
                elif isinstance(parsed, dict) and 'apps' in parsed:
                    microservices = [str(app).strip().strip('"') for app in parsed['apps'] if str(app).strip()]
                else:
                    microservices = [str(parsed).strip().strip('"')] if str(parsed).strip() else []
            except (json.JSONDecodeError, ValueError):
                # If not JSON, try line-by-line parsing
                lines = output.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('-') and not line.lower().startswith('http'):
                        # Skip header lines, comment lines, or HTTP response lines
                        # Split by common separators and take the first meaningful part
                        parts = line.split()
                        if parts:
                            microservices.append(parts[0].strip('"').strip("'"))
        
        # Clean up microservice names - remove quotes, brackets, commas
        cleaned_microservices = []
        for ms in microservices:
            # Remove common unwanted characters
            cleaned = re.sub(r'["\[\],]', '', str(ms)).strip()
            if cleaned and cleaned.lower() not in ['http', 'response', 'code']:
                cleaned_microservices.append(cleaned)
        
        # Remove duplicates and empty entries, then sort
        microservices = sorted(list(set([ms for ms in cleaned_microservices if ms and ms.strip()])))
        return microservices
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
    
    # Dynamic foundations based on environment
    def get_foundations_for_environment(env):
        if env == 'dev-pnf':
            return ['EDI01_DEV', 'EDI02_DEV']
        elif env == 'prd-pnf':
            return ['EDI01_PRD', 'EDI02_PRD']
        return []
    
    todo_options = ['start', 'stop', 'restage']
    
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
    selected_foundation = request.form.get('foundation')
    selected_microservice = request.form.get('microservice')
    selected_action = request.form.get('action')
    
    # Get available spaces for selected environment
    available_spaces = get_spaces_for_environment(selected_environment) if selected_environment else []
    
    # Get available foundations for selected environment
    available_foundations = get_foundations_for_environment(selected_environment) if selected_environment else []
    
    # Reset space selection if environment changed and current space is not valid
    if selected_environment != session.get('selected_environment'):
        if selected_space and selected_space not in available_spaces:
            selected_space = None
        # Also reset foundation selection if environment changed
        if selected_foundation and selected_foundation not in available_foundations:
            selected_foundation = None
    
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
    all_selected = all([selected_application, selected_environment, selected_space, selected_foundation, selected_microservice, selected_action])
    command = None
    if all_selected:
        command = f"dws pcf operations {selected_action} -e {selected_environment} -c {selected_application} -s {selected_space} -a {selected_microservice} -x {selected_action} --foundation={selected_foundation}"
    
    # Calculate missing items
    missing_items = []
    if not selected_application:
        missing_items.append("Application")
    if not selected_environment:
        missing_items.append("Environment")
    if not selected_space:
        missing_items.append("Space")
    if not selected_foundation:
        missing_items.append("Foundation")
    if not selected_microservice:
        missing_items.append("Microservice")
    if not selected_action:
        missing_items.append("Action")
    
    return render_template('index.html', 
                         applications=applications,
                         environments=environments,
                         available_spaces=available_spaces,
                         available_foundations=available_foundations,
                         todo_options=todo_options,
                         selected_application=selected_application,
                         selected_environment=selected_environment,
                         selected_space=selected_space,
                         selected_foundation=selected_foundation,
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

@app.route('/get_foundations', methods=['POST'])
def get_foundations():
    """AJAX endpoint to get foundations for an environment"""
    environment = request.json.get('environment')
    
    if not environment:
        return jsonify({'error': 'Environment must be specified'}), 400
    
    if environment == 'dev-pnf':
        foundations = ['EDI01_DEV', 'EDI02_DEV']
    elif environment == 'prd-pnf':
        foundations = ['EDI01_PRD', 'EDI02_PRD']
    else:
        foundations = []
    
    return jsonify({
        'foundations': foundations,
        'count': len(foundations)
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
    selected_foundation = request.form.get('foundation')
    selected_microservice = request.form.get('microservice')
    selected_action = request.form.get('action')
    
    return render_template('confirm.html',
                         command=command,
                         selected_application=selected_application,
                         selected_environment=selected_environment,
                         selected_space=selected_space,
                         selected_foundation=selected_foundation,
                         selected_microservice=selected_microservice,
                         selected_action=selected_action)

if __name__ == "__main__":
    app.run(debug=True)
