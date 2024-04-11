from datetime import date
import tempfile
from flask import (
    Flask,
    flash,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
)
from models import (
    InitialHypothesis,
    MedicalCondition,
    Patient,
    Pawparent,
    QueryResult,
    Report,
    UserData,
    db,
)
import logging
from flask_debugtoolbar import DebugToolbarExtension
from openai import OpenAI, OpenAIError, RateLimitError, BadRequestError
from requests.exceptions import HTTPError, Timeout, RequestException
from cryptography.fernet import Fernet
import os
import time
from passlib.hash import argon2
from pdf2image import convert_from_path
import pytesseract
from werkzeug.utils import secure_filename


client = OpenAI()

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:1234@localhost/postgres"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "prdiagnosticsystem"
app.config["DEBUG_TB_INTERCEPT_REDIRECTS"] = (
    False  # Prevents the debug toolbar from intercepting redirects
)
# Set the project directory
project_dir = "C:/Users/Faithlin Hoe/PR-Veterinary-Diagnosis-System"
upload_folder = os.path.join(project_dir, "uploads")

# Now set the UPLOAD_FOLDER in your Flask app's config
app.config["UPLOAD_FOLDER"] = upload_folder

# Ensure the directory exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


db.init_app(app)
toolbar = DebugToolbarExtension(app)

# Retrieve the Fernet key from the environment variable
fernet_key = os.environ.get("FERNET_KEY")
cipher_suite = Fernet(fernet_key)


def encrypt_data(data):
    """Encrypt the data with Fernet."""
    return cipher_suite.encrypt(data.encode()).decode()


def decrypt_data(data):
    """Decrypt the data with Fernet."""
    return cipher_suite.decrypt(data.encode()).decode()


# Define the process_pdf function that handles PDF processing
def process_pdf(pdf_path):
    pages = convert_from_path(pdf_path)
    text = ""
    for page in pages:
        text += pytesseract.image_to_string(page)
    return text


def process_initial_evaluation(query_id, query_text, attempt=1, max_attempts=3):
    # Adjusted prompt to clearly define the expected response format and request only one medical condition
    prompt_for_gpt = (
        "The recipient is a veterinary assistant, do not worry about using professional terms. "
        "Please format your response as follows: 'Condition Name: Condition Name. "
        "Urgency Level: Low/Medium/High. Justification: Short and Concise Condition Justification. "
        "First-Aid Procedure Suggestion: Suggested Procedure. Reference: [link to source]'. "
        f"{query_text} Please provide 1 possible medical condition based on the above symptoms, "
        "with the condition's name, concise justification, urgency level, suggested first-aid procedure, and a reference link."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4-0125-preview",
            messages=[{"role": "system", "content": prompt_for_gpt}],
            temperature=0.5,
            max_tokens=4096,
            frequency_penalty=1.0,
            n=1,
            stop=None,
        )

        for choice in response.choices:
            api_response = choice.message.content.strip()
            print("API Response:", api_response)  # Print the generated text

            # Since only one condition is requested, the logic to handle multiple conditions is not needed.
            # Directly split and process the single response.
            parts = api_response.split("Urgency Level:")
            if len(parts) < 2:
                app.logger.error("Incomplete information for condition received.")
                raise ValueError("Incomplete data received from GPT.")

            name_part, rest = parts[0].strip(), parts[1].strip()
            name_text = name_part.replace(
                "Condition Name: ", ""
            ).strip()  # Extract the condition name

            urgency_and_rest = rest.split("Justification:")
            if len(urgency_and_rest) < 2:
                app.logger.error("Missing urgency or justification for condition.")
                continue

            urgency, justification_and_rest = (
                urgency_and_rest[0].strip(),
                urgency_and_rest[1].strip(),
            )

            justification_part, treatment_and_reference = justification_and_rest.split(
                "First-Aid Procedure Suggestion:"
            )
            justification = justification_part.strip()

            treatment_suggestion, reference = treatment_and_reference.split(
                "Reference:"
            )
            treatment_suggestion = treatment_suggestion.strip()
            reference = reference.strip().replace("[", "").replace("]", "")

            # Encrypt each part as needed before saving
            new_initial_hypothesis = InitialHypothesis(
                QResultID=query_id,
                Name=encrypt_data(name_text),
                Urgency=encrypt_data(urgency),
                justification=encrypt_data(justification),
                TreatmentSuggestion=encrypt_data(treatment_suggestion),
                Reference=encrypt_data(reference),
            )
            db.session.add(new_initial_hypothesis)
        db.session.commit()
    except (
        OpenAIError,
        RateLimitError,
        BadRequestError,
        HTTPError,
        Timeout,
        RequestException,
    ) as e:
        db.session.rollback()
        app.logger.error(f"API call failed: {str(e)}")
    except ValueError as ve:
        if attempt < max_attempts:
            app.logger.error(
                f"Trying again due to incomplete data: Attempt {attempt} of {max_attempts}. Error: {ve}"
            )
            time.sleep(2)  # Wait for 2 seconds before retrying
            return process_initial_evaluation(
                query_id, query_text, attempt + 1, max_attempts
            )
        else:
            app.logger.error(f"Max retry attempts reached with error: {ve}")
            flash(
                "Could not get complete data from GPT after several attempts.", "error"
            )
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Unexpected error: {str(e)}")


def process_query_with_gpt(query_id, query_text, attempt=1, max_attempts=3):
    # Adjusted prompt to clearly define the expected response format and request only one medical condition
    prompt_for_gpt = (
        "The recipient is a veterinarian, do not worry about using professional terms. "
        "Please format your response as follows: 'Condition Name: Condition Justification. "
        "Treatment Suggestion: Suggested Treatment. Reference: [link to source]'. "
        f"{query_text} Please provide 1 possible medical condition based on the above symptoms, "
        "with the condition's justification, suggested treatment, and a reference link."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4-0125-preview",
            messages=[{"role": "system", "content": prompt_for_gpt}],
            temperature=0.5,
            max_tokens=4096,
            frequency_penalty=0.0,
            n=1,
            stop=None,
        )

        for choice in response.choices:
            api_response = choice.message.content.strip()
            print("API Response:", api_response)  # Print the generated text

            # Directly process the single response since only one condition is requested.
            parts = api_response.split("Treatment Suggestion:")
            if len(parts) < 2:
                app.logger.error("Incomplete information for condition received.")
                raise ValueError("Incomplete data received from GPT.")

            name_justification_parts = parts[0].split("Condition Justification:")
            if len(name_justification_parts) < 2:
                app.logger.error("Missing justification for condition. Skipping.")
                continue

            name_text = (
                name_justification_parts[0].replace("Condition Name:", "").strip()
            )
            justification_text = name_justification_parts[1].strip()

            treatment_text, reference_text = parts[1].split("Reference:", 1)
            treatment_text = treatment_text.strip()
            reference_text = reference_text.strip().replace("[", "").replace("]", "")

            # Encrypt each part as needed before saving
            new_condition = MedicalCondition(
                QResultID=query_id,
                Name=encrypt_data(name_text),
                justification=encrypt_data(justification_text),
                TreatmentSuggestion=encrypt_data(treatment_text),
                Reference=encrypt_data(reference_text),
            )
            db.session.add(new_condition)

        db.session.commit()
    except (
        OpenAIError,
        RateLimitError,
        BadRequestError,
        HTTPError,
        Timeout,
        RequestException,
    ) as e:
        db.session.rollback()
        app.logger.error(f"API call failed: {str(e)}")
    except ValueError as ve:
        if attempt < max_attempts:
            app.logger.error(
                f"Trying again due to incomplete data: Attempt {attempt} of {max_attempts}. Error: {ve}"
            )
            time.sleep(2)  # Wait for 2 seconds before retrying
            return process_query_with_gpt(
                query_id, query_text, attempt + 1, max_attempts
            )
        else:
            app.logger.error(f"Max retry attempts reached with error: {ve}")
            flash(
                "Could not get complete data from GPT after several attempts.", "error"
            )
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Unexpected error: {str(e)}")


@app.route("/", methods=["GET"])
def login_page():
    return render_template("login.html")


@app.route("/documentation", methods=["GET"])
def documentation():
    return render_template("documentation.html")


@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"].strip()
    password = request.form["password"].strip()
    app.logger.debug("Attempting to log in with email: %s", email)

    user = UserData.query.filter_by(email=email).first()

    if user and argon2.verify(password, user.password):
        app.logger.debug("Login successful for user: %s", email)

        # Store user information in the session
        session["UserID"] = user.id
        session["role"] = user.role

        app.logger.debug("Session contents: %s", session)
        return redirect(url_for("home_page"))

    else:
        app.logger.debug("Login failed for user: %s", email)
        return render_template(
            "login.html", error="Invalid credentials. Please try again."
        )


@app.route("/logout")
def logout():
    # This removes all data stored in the session
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/home", methods=["GET"])
def home_page():
    app.logger.debug("Accessed home with session: %s", session)

    if session["role"] == "veterinarian" or session["role"] == "assistant":
        return render_template("client_home.html")
    elif session["role"] == "admin":
        return render_template("admin_home.html")
    else:
        # If role is not recognized, clear the session and redirect to login
        session.clear()
        return redirect(url_for("login_page"))


@app.route("/new_case", methods=["GET", "POST"])
def new_case():
    if "role" not in session:
        return redirect(url_for("login_page"))

    if request.method == "POST" and session["role"] == "assistant":
        # Collect all form data into a single string
        checklist_items = [
            f"activity:{request.form['activity']}",
            f"breathing:{request.form['breathing']}",
            f"eye_condition:{request.form['eye_condition']}",
            f"discharge:{request.form['discharge']}",
            f"diet_weight:{request.form['diet_weight']}",
            f"skin_coat_condition:{request.form['skin_coat_condition']}",
            f"ear_condition:{request.form['ear_condition']}",
            f"appetite:{request.form['appetite']}",
            f"vomiting_diarrhoea:{request.form['vomiting_diarrhoea']}",
            f"urination_defecation:{request.form['urination_defecation']}",
            f"behavioural_changes:{request.form['behavioural_changes']}",
            f"mobility:{request.form['mobility']}",
            f"gum_colour:{request.form['gum_colour']}",
            f"pain_response:{request.form['pain_response']}",
            f"others:{request.form['others']}",
        ]
        query_text = ", ".join(checklist_items)

        # Encrypt the query text before storing it
        encrypted_query_text = encrypt_data(query_text)
        new_query = QueryResult(UserID=session["UserID"], Query=encrypted_query_text)
        db.session.add(new_query)
        try:
            db.session.commit()
            flash("New case added successfully.", "success")

            # At this point, new_query.QResultID contains the ID of the new QueryResult
            print(f"New QueryResult ID: {new_query.QResultID}")

        except Exception as e:
            flash("Error in database commit: {}".format(e), "error")
            db.session.rollback()

        try:
            # Call the separate function for API interaction
            process_initial_evaluation(new_query.QResultID, query_text)

            new_report = Report(QResultID=new_query.QResultID)
            db.session.add(new_report)
            db.session.commit()
        except Exception as e:
            flash("Error in database commit: {}".format(e), "error")
            db.session.rollback()

        return redirect(url_for("home_page"))

    elif request.method == "GET":
        if session["role"] == "assistant":
            return render_template("new_case_assistant.html")
        elif session["role"] == "veterinarian":
            queries = QueryResult.query.order_by(QueryResult.QResultID.desc()).all()

            app.logger.debug("Number of queries found: %d", len(queries))
            decrypted_queries = []

            for q in queries:
                try:
                    decrypted_query = decrypt_data(q.Query)
                    decrypted_queries.append(
                        {"QResultID": q.QResultID, "Query": decrypted_query}
                    )
                    app.logger.debug(f"Query #{q.QResultID} decrypted successfully")
                    app.logger.debug(f"Query #{decrypted_query} decrypted successfully")

                except Exception as e:
                    app.logger.error(f"Error decrypting query #{q.QResultID}: {str(e)}")
                    # Consider whether to append a placeholder or handle individually
                    decrypted_queries.append(
                        {"QResultID": q.QResultID, "Query": "Error decrypting data"}
                    )

            return render_template(
                "new_case_veterinarian.html", queries=decrypted_queries
            )

    return redirect(url_for("home_page"))


@app.route("/edit_case/<int:query_id>", methods=["GET", "POST"])
def edit_case(query_id):
    if "role" not in session or session["role"] != "veterinarian":
        return redirect(url_for("login_page"))

    query_result = db.session.get(QueryResult, query_id)
    if query_result is None:
        app.logger.error(f"QueryResult with id {query_id} not found.")
        return "Query not found", 404

    decrypted_query = decrypt_data(query_result.Query)  # Decrypt the query data

    if request.method == "POST":
        additional_info = request.form.get("additional_info", "").strip()
        report_pdf = request.files.get("report_pdf")

        if report_pdf and report_pdf.filename != "":
            app.logger.debug("Received PDF file: %s", report_pdf.filename)
            filename = secure_filename(report_pdf.filename)
            filepath = os.path.join(tempfile.gettempdir(), filename)
            report_pdf.save(filepath)
            app.logger.debug("Saved PDF to temporary file: %s", filepath)
            pdf_text = process_pdf(filepath)
            app.logger.debug("Extracted text from PDF: %s", pdf_text)
            os.remove(filepath)  # Delete the file after processing
            # Define a title for the extracted PDF text
            pdf_text_title = "Extracted PDF Text (Pathology Report):"
            additional_info += f"\n, {pdf_text_title}{pdf_text}"

        # Append additional details in a comma-separated format and then encrypt again
        if decrypted_query and additional_info:
            updated_query = f"{decrypted_query}, additional details:{additional_info}"
        else:
            updated_query = f"additional details:{additional_info}"

        encrypted_query = encrypt_data(updated_query)  # Encrypt the updated query
        query_result.Query = encrypted_query
        query_result.UserID = session.get("UserID")

        try:
            db.session.commit()
            flash("Case updated successfully.", "success")

            # Call the separate function for API interaction
            process_query_with_gpt(query_id, updated_query)

            # After API call, create a new report entry
            new_report = Report(QResultID=query_id)
            db.session.add(new_report)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating case: {e}")
            flash(f"Error updating case: {e}", "error")

        return redirect(url_for("home_page"))

    else:
        symptom_details = decrypted_query.split(", ") if decrypted_query else []
        # Create a query object to pass to the template, including the decrypted Query.
        query_data = {
            "QResultID": query_result.QResultID,
            "Query": decrypted_query,  # Assuming this is the decrypted data to be shown.
            "UserID": query_result.UserID,
        }
        return render_template(
            "edit_case.html", query=query_data, symptom_details=symptom_details
        )


@app.route("/view_reports")
def view_reports():
    # Perform a join between Report and QueryResult based on QResultID
    reports_with_queries_raw = (
        db.session.query(Report.ReportID, QueryResult.Query)
        .join(QueryResult, Report.QResultID == QueryResult.QResultID)
        .order_by(Report.ReportID.desc())
        .all()
    )

    # Decrypt the Query data
    reports_with_queries = [
        (ReportID, decrypt_data(Query)) for ReportID, Query in reports_with_queries_raw
    ]

    # Pass the decrypted data to the template
    return render_template("view_reports.html", reports=reports_with_queries)


@app.route("/report_details/<int:report_id>", methods=["GET"])
def report_details(report_id):
    report = db.session.get(Report, report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404

    # Fetch MedicalCondition entries
    medical_conditions = MedicalCondition.query.filter_by(
        QResultID=report.QResultID
    ).all()
    initial_hypotheses = InitialHypothesis.query.filter_by(
        QResultID=report.QResultID
    ).all()

    # Preparing data from MedicalCondition
    medical_conditions_data = [
        {
            "type": "Medical Condition",
            "name": decrypt_data(condition.Name),
            "justification": decrypt_data(condition.justification),
            "treatment": decrypt_data(condition.TreatmentSuggestion),
            "reference": decrypt_data(condition.Reference),
        }
        for condition in medical_conditions
    ]

    # Preparing data from InitialHypothesis
    initial_hypotheses_data = [
        {
            "type": "Initial Hypothesis",
            "name": decrypt_data(hypothesis.Name),
            "urgency": decrypt_data(hypothesis.Urgency),
            "justification": decrypt_data(hypothesis.justification),
            "treatment": decrypt_data(hypothesis.TreatmentSuggestion),
            "reference": decrypt_data(hypothesis.Reference),
        }
        for hypothesis in initial_hypotheses
    ]

    # Combine both datasets into one list to pass to the frontend
    combined_data = medical_conditions_data + initial_hypotheses_data

    return jsonify(combined_data)


@app.route("/manage_account", methods=["GET", "POST"])
def manage_account():
    if "UserID" not in session:
        return redirect(url_for("login_page"))

    user_id = session["UserID"]
    user = UserData.query.get(user_id)
    if not user:
        return "User not found", 404

    message = None
    current_email = user.email if user else ""

    if request.method == "POST":
        new_email = request.form["new_email"].strip()
        new_password = request.form["new_password"].strip()
        hashed_password = argon2.hash(new_password)

        if new_email:
            user.email = new_email
        if hashed_password:
            user.password = hashed_password

        try:
            db.session.commit()
            message = "Details updated successfully."
        except Exception as e:
            message = str(e)
            db.session.rollback()

    return render_template(
        "manage_account.html", message=message, current_email=current_email
    )


@app.route("/manage_users", methods=["GET"])
def manage_users():
    if "role" in session and session["role"] == "admin":
        users = UserData.query.all()
        return render_template("edit_users.html", users=users)
    return redirect(url_for("login_page"))


@app.route("/update_user/<int:user_id>", methods=["POST"])
def update_user(user_id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login_page"))

    user = UserData.query.get(user_id)
    if user:
        user.email = request.form["email"]
        user.role = request.form["role"]
        db.session.commit()
        return redirect(url_for("manage_users"))
    return "User not found", 404


@app.route("/add_user", methods=["GET", "POST"])
def add_user():
    if "role" in session and session["role"] == "admin":
        if request.method == "POST":
            email = request.form["email"]
            password = request.form["password"]
            role = request.form["role"]
            hashed_password = argon2.hash(password)

            new_user = UserData(email=email, password=hashed_password, role=role)
            db.session.add(new_user)
            try:
                db.session.commit()
                return redirect(url_for("home_page"))
            except Exception as e:
                db.session.rollback()
                # handle exception, e.g., duplicate email
        return render_template("add_user.html")
    return redirect(url_for("login_page"))


@app.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    # Security check: Ensure that the current user has admin role
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login_page"))

    # Retrieve the user to delete
    user_to_delete = UserData.query.get(user_id)
    if user_to_delete:
        db.session.delete(user_to_delete)
        try:
            db.session.commit()
            # You can add a message to the flash storage to indicate success
            flash("User deleted successfully.", "success")
        except Exception as e:
            # You can add a message to the flash storage to indicate failure
            flash("An error occurred while deleting the user.", "error")
            db.session.rollback()
    else:
        flash("User not found.", "error")

    # Redirect to the manage users page
    return redirect(url_for("manage_users"))


#######################################################################################################################################
@app.route("/manage_patients", methods=["GET"])
def manage_patients():
    if "role" in session and (
        session["role"] == "assistant" or session["role"] == "veterinarian"
    ):
        patients = Patient.query.all()
        return render_template("edit_patients.html", patients=patients)
    return redirect(url_for("login_page"))


@app.route("/add_patient", methods=["GET", "POST"])
def add_patient():
    if "role" in session and (
        session["role"] == "assistant" or session["role"] == "veterinarian"
    ):
        if request.method == "POST":
            try:
                new_patient = Patient(
                    PatientName=request.form["patient_name"],
                    Species=request.form["species"],
                    Age=int(request.form["age"]),
                    Breed=request.form["breed"],
                    Gender=request.form["gender"],
                    PawparentID=int(request.form["pawparentID"]),
                    DateCreated=date.today(),
                )
                db.session.add(new_patient)
                db.session.commit()
                flash("Patient added successfully.", "success")
                return redirect(url_for("home_page"))
            except Exception as e:
                db.session.rollback()
                flash("An error occurred while adding the patient: " + str(e), "error")
                return redirect(url_for("add_patient"))
        else:
            pawparents = Pawparent.query.all()
            return render_template("add_patient.html", pawparents=pawparents)
    else:
        flash("Access denied. Please log in with appropriate credentials.", "error")
        return redirect(url_for("login_page"))


@app.route("/search_pawparents")
def search_pawparents():
    query = request.args.get("query", "").lower()
    if query:  # Ensure there is a query to search for
        pawparents = Pawparent.query.filter(
            Pawparent.Name.ilike(f"%{query}%")
            | Pawparent.PhoneNumber.ilike(f"%{query}%")
        ).all()
    else:
        pawparents = Pawparent.query.all()
    pawparent_list = [
        {
            "id": pawparent.PawparentID,
            "text": f"{pawparent.PawparentID} - {pawparent.Name} - {pawparent.PhoneNumber}",
        }
        for pawparent in pawparents
    ]
    return jsonify(pawparent_list)


@app.route("/update_patient/<int:patient_id>", methods=["POST"])
def update_patient(patient_id):
    if "role" not in session or (
        session["role"] != "assistant" and session["role"] != "veterinarian"
    ):
        return redirect(url_for("login_page"))

    patient = db.session.get(Patient, patient_id)

    if patient:
        patient.PatientName = request.form["patient_name"]
        patient.Species = request.form["species"]
        patient.Age = request.form["age"]
        patient.Breed = request.form["breed"]
        patient.Gender = request.form["gender"]
        patient.PawparentID = request.form["pawparentID"]
        db.session.commit()
        return redirect(url_for("manage_patients"))
    return "Patient not found", 404


@app.route("/delete_patient/<int:patient_id>", methods=["POST"])
def delete_patient(patient_id):
    if "role" not in session or (
        session["role"] != "assistant" and session["role"] != "veterinarian"
    ):
        return redirect(url_for("login_page"))
    patient_to_delete = Patient.query.get(patient_id)
    if patient_to_delete:
        db.session.delete(patient_to_delete)
        try:
            db.session.commit()
            flash("Patient deleted successfully.", "success")
        except Exception as e:
            flash("An error occurred while deleting the patient. " + str(e), "error")
            db.session.rollback()
    else:
        flash("Patient not found.", "error")
    return redirect(url_for("manage_patients"))


#######################################################################################################################################


@app.route("/manage_pawparents", methods=["GET"])
def manage_pawparents():
    if "role" in session and (
        session["role"] == "assistant" or session["role"] == "veterinarian"
    ):
        pawparents = Pawparent.query.all()
        return render_template("edit_pawparents.html", pawparents=pawparents)
    return redirect(url_for("login_page"))


@app.route("/add_pawparent", methods=["GET", "POST"])
def add_pawparent():
    if "role" in session and (
        session["role"] == "assistant" or session["role"] == "veterinarian"
    ):
        if request.method == "POST":
            name = request.form["name"]
            phone_number = request.form["phone_number"]
            new_pawparent = Pawparent(Name=name, PhoneNumber=phone_number)
            db.session.add(new_pawparent)
            try:
                db.session.commit()
                return redirect(url_for("home_page"))
            except Exception as e:
                db.session.rollback()
                flash(
                    "An error occurred while adding the pawparent. " + str(e), "error"
                )
        return render_template("add_pawparents.html")
    return redirect(url_for("login_page"))


@app.route("/update_pawparent/<int:pawparent_id>", methods=["POST"])
def update_pawparent(pawparent_id):
    if "role" not in session or (
        session["role"] != "assistant" and session["role"] != "veterinarian"
    ):
        return redirect(url_for("login_page"))

    pawparent = Pawparent.query.get(pawparent_id)
    if pawparent:
        pawparent.Name = request.form["name"]
        pawparent.PhoneNumber = request.form["phone_number"]
        db.session.commit()
        return redirect(url_for("manage_pawparents"))
    return "Pawparent not found", 404


@app.route("/delete_pawparent/<int:pawparent_id>", methods=["POST"])
def delete_pawparent(pawparent_id):
    if "role" not in session or (
        session["role"] != "assistant" and session["role"] != "veterinarian"
    ):
        return redirect(url_for("login_page"))
    pawparent_to_delete = Pawparent.query.get(pawparent_id)
    if pawparent_to_delete:
        db.session.delete(pawparent_to_delete)
        try:
            db.session.commit()
            flash("Pawparent deleted successfully.", "success")
        except Exception as e:
            flash("An error occurred while deleting the pawparent. " + str(e), "error")
            db.session.rollback()
    else:
        flash("Pawparent not found.", "error")
    return redirect(url_for("manage_pawparents"))


if __name__ == "__main__":
    app.run(debug=True)
