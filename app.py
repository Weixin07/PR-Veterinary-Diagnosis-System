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
from models import MedicalCondition, QueryResult, Report, UserData, db
import logging
from flask_debugtoolbar import DebugToolbarExtension
from openai import OpenAI, OpenAIError, RateLimitError, BadRequestError
from requests.exceptions import HTTPError, Timeout, RequestException
from cryptography.fernet import Fernet
import os
import time

client = OpenAI()

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:1234@localhost/postgres"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "prdiagnosticsystem"
app.config["DEBUG_TB_INTERCEPT_REDIRECTS"] = (
    False  # Prevents the debug toolbar from intercepting redirects
)

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


@app.route("/", methods=["GET"])
def login_page():
    return render_template("login.html")

@app.route("/documentation", methods=["GET"])
def documentation():
    return render_template("documentation.html")

## use hasing, later
@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"].strip()
    password = request.form["password"].strip()
    app.logger.debug("Attempting to log in with email: %s", email)

    user = UserData.query.filter_by(email=email, password=password).first()

    if user:
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
        ]
        query_text = ", ".join(checklist_items)

        # Encrypt the query text before storing it
        encrypted_query_text = encrypt_data(query_text)
        new_query = QueryResult(UserID=session["UserID"], Query=encrypted_query_text)
        db.session.add(new_query)
        try:
            db.session.commit()
            flash("New case added successfully.", "success")
        except Exception as e:
            flash("Error in database commit: {}".format(e), "error")
            db.session.rollback()

        return redirect(url_for("home_page"))

    elif request.method == "GET":
        if session["role"] == "assistant":
            return render_template("new_case_assistant.html")
        elif session["role"] == "veterinarian":
            queries = QueryResult.query.all()
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


def process_query_with_gpt(query_id, query_text, attempt=1, max_attempts=3):
    # Adjusted prompt to clearly define the expected response format
    prompt_for_gpt = (
        "The recipient is a veterinarian, do not worry about using professional terms. "
        "Please format your response as follows: 'Condition Name: Condition Justification. "
        "Treatment Suggestion: Suggested Treatment. Reference: [link to source]'. "
        f"{query_text} Please provide three possible medical conditions based on the above symptoms, "
        "with each condition's justification, suggested treatment, and a reference link."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": prompt_for_gpt}],
            temperature=0.5,
            max_tokens=256,
            frequency_penalty=0.0,
            n=1,
            stop=None,
        )

        for choice in response.choices:
            api_response = choice.message.content.strip()
            print("API Response:", api_response)  # Print the generated text

            # Use "Condition Name:" as a delimiter to split the response into conditions
            conditions = api_response.split("Condition Name:")
            if conditions and conditions[0] == "":
                conditions.pop(0)

            if not conditions or len(conditions) < 3:
                app.logger.error("Incomplete information for condition received.")
                raise ValueError("Incomplete data received from GPT.")

            for condition in conditions:
                parts = condition.split("Treatment Suggestion:")
                if len(parts) < 2:
                    app.logger.error("Incomplete information for condition. Skipping.")
                    continue

                # Splitting by 'Reference:' first to ensure we capture the name properly
                name_justification_parts = parts[0].split("Condition Justification:")
                if len(name_justification_parts) < 2:
                    app.logger.error("Missing justification for condition. Skipping.")
                    continue

                name_text = encrypt_data(name_justification_parts[0].strip())
                justification_text = encrypt_data(name_justification_parts[1].strip())

                treatment_text, reference_text = parts[1].split("Reference:", 1)
                treatment_text = encrypt_data(treatment_text.strip())
                reference_text = encrypt_data(
                    reference_text.strip().replace("[", "").replace("]", "")
                )

                new_condition = MedicalCondition(
                    QResultID=query_id,
                    Name=name_text,
                    justification=justification_text,
                    TreatmentSuggestion=treatment_text,
                    Reference=reference_text,
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
    except IndexError as ie:
        if attempt < max_attempts:
            app.logger.error(
                f"Trying again due to index error: Attempt {attempt} of {max_attempts}. Error: {ie}"
            )
            time.sleep(2)  # Wait for 2 seconds before retrying
            return process_query_with_gpt(
                query_id, query_text, attempt + 1, max_attempts
            )
        else:
            app.logger.error(f"Max retry attempts reached with error: {ie}")
            flash(
                "Could not get complete data from GPT after several attempts.", "error"
            )
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Unexpected error: {str(e)}")


@app.route("/view_reports")
def view_reports():
    # Perform a join between Report and QueryResult based on QResultID
    reports_with_queries_raw = (
        db.session.query(Report.ReportID, QueryResult.Query)
        .join(QueryResult, Report.QResultID == QueryResult.QResultID)
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
    if report:
        medical_conditions = MedicalCondition.query.filter_by(
            QResultID=report.QResultID
        ).all()
        medical_conditions_data = [
            {
                "name": decrypt_data(condition.Name),
                "justification": decrypt_data(condition.justification),
                "treatment": decrypt_data(condition.TreatmentSuggestion),
                "reference": decrypt_data(condition.Reference),
            }
            for condition in medical_conditions
        ]

        return jsonify(medical_conditions_data)
    else:
        return jsonify({"error": "Report not found"}), 404


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
    current_password = user.password if user else ""

    if request.method == "POST":
        new_email = request.form["new_email"].strip()
        new_password = request.form["new_password"].strip()

        if new_email:
            user.email = new_email
        if new_password:  # Assuming you are storing passwords in a hashed form.
            user.password = (
                new_password  # This is an example, use your password hashing method.
            )

        try:
            db.session.commit()
            message = "Details updated successfully."
        except Exception as e:
            message = str(e)
            db.session.rollback()

    return render_template(
        "manage_account.html",
        message=message,
        current_email=current_email,
        current_password=current_password,
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
            password = request.form["password"]  # This should be hashed
            role = request.form["role"]

            new_user = UserData(email=email, password=password, role=role)
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


if __name__ == "__main__":
    app.run(debug=True)
