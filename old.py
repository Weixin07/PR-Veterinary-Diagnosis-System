from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI']='postgresql://postgres:1234@localhost/postgres'

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Person(db.Model):
    __tablename__='Person'
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(255))
    age=db.Column(db.Integer)
    gender=db.Column(db.CHAR) 

    def __init__(self, name, age, gender):
        self.name=name
        self.age=age
        self.gender=gender

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    name=request.form['name']
    age=request.form['age']
    gender=request.form['gender']

    person=Person(name,age,gender)
    db.session.add(person)
    db.session.commit()

    #fetch a certain data
    personResult=db.session.query(Person).filter(Person.id==4)
    for result in personResult:
        print(result.name)

    return render_template('success.html', data=name)

if __name__ == "__name__":
    app.run(debug=True)


