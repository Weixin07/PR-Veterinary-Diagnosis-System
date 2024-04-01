from flask import Flask, render_template, request, redirect, url_for
from models import User, db
import logging
from flask_debugtoolbar import DebugToolbarExtension

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI']='postgresql://postgres:1234@localhost/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False  # Prevents the debug toolbar from intercepting redirects

toolbar = DebugToolbarExtension(app)

@app.route('/', methods=['GET'])
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email'].strip()
    password = request.form['password'].strip()
    app.logger.debug('Attempting to log in with email: %s', email)
    
    user = User.query.filter_by(email=email, password=password).first()
    
    if user:
        app.logger.debug('Login successful for user: %s', email)
        return redirect(url_for(f'{user.role}_home'))
    else:
        app.logger.debug('Login failed for user: %s', email)
        return render_template('login.html', error='Invalid credentials. Please try again.')

@app.route('/veterinarian_home', methods=['GET'])
def veterinarian_home():
    return render_template('veterinarian_home.html')

@app.route('/assistant_home', methods=['GET'])
def assistant_home():
    return render_template('assistant_home.html')

@app.route('/admin_home', methods=['GET'])
def admin_home():
    return render_template('admin_home.html')

if __name__ == '__main__':
    app.run(debug=True)
