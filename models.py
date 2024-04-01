from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'User Data'  
    id = db.Column('UserID', db.Integer, primary_key=True)  
    email = db.Column('Email', db.String(255), unique=True, nullable=False)
    password = db.Column('Password', db.String(255), nullable=False)
    role = db.Column('UserRole', db.String(50), nullable=False)

    def __init__(self, email, password, role):
        self.email = email
        self.password = password
        self.role = role
