from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI']='postgresql://postgres:1234@localhost/postgres'

db = SQLAlchemy(app)

class person(db.Model):
    __tablename__='person'
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(255))
    age=db.Column(db.Integer)
    gender=db.Column(db.Char) 

def __init__(self, name, age, gender):
    self.name=name
    self.age=age
    self.gender=gender

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__name__":
    app.run(debug=True)


