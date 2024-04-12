from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class UserData(db.Model):
    __tablename__ = "User Data"
    id = db.Column("UserID", db.Integer, primary_key=True)
    email = db.Column("Email", db.String(255), unique=True, nullable=False)
    password = db.Column("Password", db.String(255), nullable=False)
    role = db.Column("UserRole", db.String(50), nullable=False)

    def __init__(self, email, password, role):
        self.email = email
        self.password = password
        self.role = role


class Patient(db.Model):
    __tablename__ = "Patients"
    PatientID = db.Column("PatientID", db.Integer, primary_key=True)
    PatientName = db.Column("PatientName", db.String(255), nullable=False)
    Species = db.Column("Species", db.String(255), nullable=False)
    Age = db.Column("Age", db.Integer, nullable=False)
    Breed = db.Column("Breed", db.String(255), nullable=False)
    Gender = db.Column("Gender", db.String(255), nullable=False)
    PawparentID = db.Column(
        "PawparentID",
        db.Integer,
        db.ForeignKey("Pawparent.PawparentID"),
        nullable=False,
    )
    DateCreated = db.Column("DateCreated", db.Date, nullable=False)

    def __init__(
        self, PatientName, Species, Age, Breed, Gender, PawparentID, DateCreated
    ):
        self.PatientName = PatientName
        self.Species = Species
        self.Age = Age
        self.Breed = Breed
        self.Gender = Gender
        self.PawparentID = PawparentID
        self.DateCreated = DateCreated


class Pawparent(db.Model):
    __tablename__ = "Pawparent"
    PawparentID = db.Column("PawparentID", db.Integer, primary_key=True)
    Name = db.Column("Name", db.String(255), nullable=False)
    PhoneNumber = db.Column("PhoneNumber", db.String(255), nullable=False)

    def __init__(self, Name, PhoneNumber):
        self.Name = Name
        self.PhoneNumber = PhoneNumber


class QueryResult(db.Model):
    __tablename__ = "Query Results"
    QResultID = db.Column("QResultID", db.Integer, primary_key=True)
    UserID = db.Column(
        "UserID", db.Integer, db.ForeignKey("User Data.UserID"), nullable=False
    )
    PatientID = db.Column(
        "PatientID", db.Integer, db.ForeignKey("Patients.PatientID"), nullable=False
    )
    Query = db.Column("Query", db.Text, nullable=False)
    DateCreated = db.Column("DateCreated", db.Date, nullable=False)

    def __init__(self, UserID, PatientID, Query, DateCreated):
        self.UserID = UserID
        self.PatientID = PatientID
        self.Query = Query
        self.DateCreated = DateCreated



class InitialHypothesis(db.Model):
    __tablename__ = "Initial Hypothesis"
    IHypothesisID = db.Column("IHypothesisID", db.Integer, primary_key=True)
    QResultID = db.Column(
        "QResultID",
        db.Integer,
        db.ForeignKey("Query Results.QResultID"),
        nullable=False,
    )
    Name = db.Column("Name", db.Text)
    Urgency = db.Column("Urgency", db.Text)
    justification = db.Column("Justification", db.Text)
    TreatmentSuggestion = db.Column("TreatmentSuggestion", db.Text)
    Reference = db.Column("Reference", db.Text)

    def __init__(
        self, QResultID, Name, Urgency, justification, TreatmentSuggestion, Reference
    ):
        self.QResultID = QResultID
        self.Name = Name
        self.Urgency = Urgency
        self.justification = justification
        self.TreatmentSuggestion = TreatmentSuggestion
        self.Reference = Reference


class MedicalCondition(db.Model):
    __tablename__ = "Medical Conditions"
    MConditionID = db.Column("MConditionID", db.Integer, primary_key=True)
    QResultID = db.Column(
        "QResultID",
        db.Integer,
        db.ForeignKey("Query Results.QResultID"),
        nullable=False,
    )
    Name = db.Column("Name", db.Text)
    justification = db.Column("Justification", db.Text)
    TreatmentSuggestion = db.Column("TreatmentSuggestion", db.Text)
    Reference = db.Column("Reference", db.Text)

    def __init__(self, QResultID, Name, justification, TreatmentSuggestion, Reference):
        self.QResultID = QResultID
        self.Name = Name
        self.justification = justification
        self.TreatmentSuggestion = TreatmentSuggestion
        self.Reference = Reference


class Report(db.Model):
    __tablename__ = "Reports"
    ReportID = db.Column("ReportID", db.Integer, primary_key=True)
    QResultID = db.Column(
        "QResultID",
        db.Integer,
        db.ForeignKey("Query Results.QResultID"),
        nullable=False,
    )

    def __init__(self, QResultID):
        self.QResultID = QResultID
