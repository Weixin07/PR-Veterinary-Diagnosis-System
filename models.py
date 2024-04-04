from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class UserData(db.Model):
    __tablename__ = 'User Data'  
    id = db.Column('UserID', db.Integer, primary_key=True)  
    email = db.Column('Email', db.String(255), unique=True, nullable=False)
    password = db.Column('Password', db.String(255), nullable=False)
    role = db.Column('UserRole', db.String(50), nullable=False)

    def __init__(self, email, password, role):
        self.email = email
        self.password = password
        self.role = role

class QueryResult(db.Model):
    __tablename__ = 'Query Results'
    QResultID = db.Column('QResultID',db.Integer, primary_key=True)
    UserID = db.Column('UserID', db.Integer, db.ForeignKey('User Data.UserID'), nullable=False)
    Query = db.Column('Query', db.Text, nullable=False)

    def __init__(self, UserID, Query):
        self.UserID = UserID
        self.Query = Query

class MedicalCondition(db.Model):
    __tablename__ = 'Medical Conditions'
    MConditionID = db.Column('MConditionID', db.Integer, primary_key=True)
    QResultID = db.Column('QResultID', db.Integer, db.ForeignKey('Query Results.QResultID'), nullable=False)
    Name = db.Column('Name', db.Text)
    justification = db.Column('Justification', db.Text)
    TreatmentSuggestion = db.Column('TreatmentSuggestion', db.Text)
    Reference = db.Column('Reference', db.Text)

    def __init__(self, QResultID, Name, justification, TreatmentSuggestion, Reference):
        self.QResultID = QResultID
        self.Name = Name
        self.justification = justification
        self.TreatmentSuggestion = TreatmentSuggestion
        self.Reference = Reference

class Report(db.Model):
    __tablename__ = 'Reports'
    ReportID = db.Column('ReportID', db.Integer, primary_key=True)
    QResultID = db.Column('QResultID', db.Integer, db.ForeignKey('Query Results.QResultID'), nullable=False)

    def __init__(self, QResultID):
        self.QResultID = QResultID
