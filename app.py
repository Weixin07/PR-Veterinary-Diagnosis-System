from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from models import MedicalCondition, QueryResult, Report, UserData, db
import logging
from flask_debugtoolbar import DebugToolbarExtension
from openai import OpenAI, OpenAIError, RateLimitError, BadRequestError
from requests.exceptions import HTTPError, Timeout, RequestException

client = OpenAI()

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI']='postgresql://postgres:1234@localhost/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'prdiagnosticsystem'
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False  # Prevents the debug toolbar from intercepting redirects

db.init_app(app)
toolbar = DebugToolbarExtension(app)

@app.route('/', methods=['GET'])
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email'].strip()
    password = request.form['password'].strip()
    app.logger.debug('Attempting to log in with email: %s', email)
    
    user = UserData.query.filter_by(email=email, password=password).first()
    
    if user:
        app.logger.debug('Login successful for user: %s', email)

        # Store user information in the session
        session['UserID'] = user.id
        session['role'] = user.role
    
        app.logger.debug('Session contents: %s', session)
        return redirect(url_for('home_page'))
    
    else:
        app.logger.debug('Login failed for user: %s', email)
        return render_template('login.html', error='Invalid credentials. Please try again.')

@app.route('/logout')
def logout():
    # This removes all data stored in the session
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/home', methods=['GET'])
def home_page():
    app.logger.debug('Accessed home with session: %s', session)
    
    if session['role'] == 'veterinarian' or session['role'] == 'assistant':
        return render_template('client_home.html')
    elif session['role'] == 'admin':
        return render_template('admin_home.html')
    else:
        # If role is not recognized, clear the session and redirect to login
        session.clear()
        return redirect(url_for('login_page'))

@app.route('/new_case', methods=['GET', 'POST'])
def new_case():
    if 'role' not in session:
        return redirect(url_for('login_page'))

    if request.method == 'POST' and session['role'] == 'assistant':
         # Collect all form data into a single string
        checklist_items = [
            f"activity:{request.form['activity']}",
            f"breathing:{request.form['breathing']}",
            f"eye_condition:{request.form['eye_condition']}",
            f"discharge:{request.form['discharge']}",
            f"diet_weight:{request.form['diet_weight']}",
            f"skin_coat_condition:{request.form['skin_coat_condition']}",
            f"ear_condition:{request.form['ear_condition']}"
        ]
        query_text = ', '.join(checklist_items)
        
        new_query = QueryResult(UserID=session['UserID'], Query=query_text)
        db.session.add(new_query)
        try:
            db.session.commit()
            app.logger.debug('New case added to QueryResults: %s', query_text)
        except Exception as e:
            app.logger.error('Error in database commit: %s', str(e))
        
        return redirect(url_for('home_page'))

    elif request.method == 'GET':
        if session['role'] == 'assistant':
            return render_template('new_case_assistant.html')
        elif session['role'] == 'veterinarian':
            # Fetch all queries, not just those belonging to the current user
            queries = QueryResult.query.all()
            app.logger.debug('Number of queries found: %d', len(queries))
            return render_template('new_case_veterinarian.html', queries=queries)

    return redirect(url_for('home_page'))

@app.route('/edit_case/<int:query_id>', methods=['GET', 'POST'])
def edit_case(query_id):
    if 'role' not in session or session['role'] != 'veterinarian':
        return redirect(url_for('login_page'))
    
    query_result = db.session.get(QueryResult, query_id)
    if query_result is None:
        app.logger.error(f'QueryResult with id {query_id} not found.')
        return "Query not found", 404

    if request.method == 'POST':
        additional_info = request.form.get('additional_info', '').strip()
        # Ensure additional details are appended in a comma-separated format
        if query_result.Query and additional_info:
            query_result.Query += f", additional details:{additional_info}"
        else:
            query_result.Query = f"additional details:{additional_info}"

        db.session.add(query_result)
        db.session.commit()

        # Call the separate function for API interaction
        process_query_with_gpt(query_id, query_result.Query)

        return redirect(url_for('home_page'))

    else:
        symptom_details = query_result.Query.split(', ') if query_result.Query else []
        return render_template('edit_case.html', query=query_result, symptom_details=symptom_details)

def process_query_with_gpt(query_id, query_text):
    prompt_for_gpt = f"{query_text}. Please provide three possible medical conditions based on the above symptoms, with justification and suggested treatment for each."

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": prompt_for_gpt}],
            temperature=0.5,
            max_tokens=256,
            frequency_penalty=0.0,
            n=1,
            stop=None
        )
        
        for choice in response.choices:
            api_response = choice.message.content.strip()
            print("API Response:", api_response)  # Print the generated text
            
            conditions = api_response.split('\n')
            for condition in conditions:
                parts = condition.split(':')
                if len(parts) >= 2:
                    justification, treatment_suggestion = parts[0], ':'.join(parts[1:])
                    new_condition = MedicalCondition(
                        QResultID=query_id,
                        justification=justification.strip(),  # Corrected attribute name
                        TreatmentSuggestion=treatment_suggestion.strip()
                    )
                    db.session.add(new_condition)
        
        db.session.commit()
    except (OpenAIError, RateLimitError, BadRequestError, HTTPError, Timeout, RequestException) as e:
        db.session.rollback()
        app.logger.error(f'API call failed: {str(e)}')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Unexpected error: {str(e)}')

if __name__ == '__main__':
    app.run(debug=True)
