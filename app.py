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
        # POST request handling for new case submission by assistant
        query_text = request.form['query'].strip()
        new_query = QueryResult(UserID=session['UserID'], Query=query_text)
        db.session.add(new_query)
        db.session.commit()
        app.logger.debug('New case added to QueryResults: %s', query_text)
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
    
    query_result = QueryResult.query.get(query_id)
    if request.method == 'POST':
        # Here, we assume you have a form field for the additional details named 'additional_info'
        additional_info = request.form['additional_info'].strip()
        query_result.Query += "\n\nAdditional Details:\n" + additional_info
        try:
            db.session.commit()
            app.logger.debug('Database commit successful')
        except Exception as e:
            app.logger.error('Error in database commit: %s', str(e))
        return redirect(url_for('new_case'))
    return render_template('edit_case.html', query=query_result)


if __name__ == '__main__':
    app.run(debug=True)
