from flask import Flask, render_template, request, redirect, url_for, session
from models import QueryResult, UserData, db
import logging
from flask_debugtoolbar import DebugToolbarExtension

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
    
    # Attempt to fetch the QueryResult only once
    query_result = QueryResult.query.get(query_id)
    if query_result is None:
        # Handle the case where the query result does not exist
        app.logger.error('QueryResult with id %s not found.', query_id)
        return "Query not found", 404

    if request.method == 'POST':
        additional_info = request.form['additional_info'].strip()
        query_result.Query += "\n\nAdditional Details:\n" + additional_info
        try:
            db.session.commit()
            app.logger.debug('Database commit successful')
            return redirect(url_for('new_case'))
        except Exception as e:
            app.logger.error('Error in database commit: %s', str(e))
            # Here you might want to return an error message to the user or handle the exception gracefully

    # For GET request, process the Query string to display it nicely on the webpage
    symptom_details = query_result.Query.split(', ') if query_result.Query else []
    return render_template('edit_case.html', query=query_result, symptom_details=symptom_details)



if __name__ == '__main__':
    app.run(debug=True)
