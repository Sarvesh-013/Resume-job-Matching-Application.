from flask import Flask, request, jsonify, render_template, send_file
from kafka import KafkaProducer
import mysql.connector
import os
import json
from flask_cors import CORS
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
import time
from dotenv import load_dotenv
import pandas as pd
from io import BytesIO

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder='templates')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Store uploaded file statuses
file_statuses = {}

# Kafka Producer Configuration
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "resume-topic")
KAFKA_SERVER = os.getenv("KAFKA_SERVER", "localhost:9092")
try:
    producer = KafkaProducer(bootstrap_servers=KAFKA_SERVER)
    print("✅ Kafka producer connected successfully")
except Exception as e:
    print(f"❌ Failed to connect to Kafka: {e}")
    exit(1)

UPLOAD_FOLDER = "Uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# MySQL Database Configuration
DB_CONFIG = {
    "host": os.getenv("host", "localhost"),
    "user": os.getenv("user", "root"),
    "password": os.getenv("password", "sarvesh#13"),
    "database": os.getenv("database", "resume_db")
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        print("✅ MySQL connected successfully")
        return conn
    except Exception as e:
        print(f"❌ MySQL connection error: {e}")
        return None

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/results", methods=["GET"])
def dashboard():
    return render_template("results.html")

@app.route("/upload", methods=["POST"])
def upload_resume():
    print("📥 Received upload request")
    if "files" not in request.files:
        return jsonify({"error": "No files provided"}), 400

    files = request.files.getlist("files")
    if not files or all(file.filename == "" for file in files):
        return jsonify({"error": "No selected files"}), 400

    allowed_extensions = {".pdf", ".docx", ".txt"}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    file_paths = []

    for file in files:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({"error": f"Unsupported file format: {file.filename}. Only PDF, DOCX, TXT allowed"}), 400

        file.seek(0, os.SEEK_END)
        if file.tell() > MAX_FILE_SIZE:
            return jsonify({"error": f"File too large: {file.filename}. Max 5MB allowed"}), 400
        file.seek(0)

        timestamp = int(time.time() * 1000)
        original_filename = secure_filename(file.filename)
        filename = f"{timestamp}_{original_filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        print(f"💾 File saved to {filepath}")
        file_paths.append(filepath)
        file_statuses[filepath] = {"status": "queued", "filename": original_filename}

    try:
        for filepath in file_paths:
            message = {
                "file_path": filepath,
                "original_filename": os.path.basename(filepath)
            }
            producer.send(KAFKA_TOPIC, value=json.dumps(message).encode("utf-8"))
            print(f"📡 Sent to Kafka: {message}")
        producer.flush()
    except Exception as e:
        for filepath in file_paths:
            file_statuses[filepath]["status"] = "failed"
            file_statuses[filepath]["error"] = str(e)
        socketio.emit('upload_status', {
            'file_paths': file_paths,
            'status': 'failed',
            'error': str(e),
            'filenames': {fp: file_statuses[fp]["filename"] for fp in file_paths}
        })
        return jsonify({"error": f"Kafka error: {str(e)}"}), 500

    socketio.emit('upload_status', {
        'file_paths': file_paths,
        'status': 'queued',
        'filenames': {fp: file_statuses[fp]["filename"] for fp in file_paths}
    })

    return jsonify({
        "message": "Resumes uploaded successfully, processing started",
        "file_paths": file_paths
    }), 200

@app.route("/download_csv", methods=["GET"])
def download_csv():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT r.id, r.name, r.phone, r.email, r.skills, r.file_path, rj.job_role, rj.score, rj.job_skills
        FROM resumes r
        LEFT JOIN resume_jobs rj ON r.id = rj.resume_id
        """
        cursor.execute(query)
        resumes = cursor.fetchall()
        cursor.close()
        conn.close()

        df_data = []
        resume_groups = {}
        for row in resumes:
            resume_id = row['id']
            if resume_id not in resume_groups:
                resume_groups[resume_id] = {
                    'Filename': os.path.basename(row['file_path']),
                    'Name': row['name'],
                    'Email': row['email'],
                    'Phone': row['phone'],
                    'Skills': row['skills'],
                    'Jobs': []
                }
            if row['job_role']:
                resume_groups[resume_id]['Jobs'].append({
                    'Job': row['job_role'],
                    'Score': row['score'],
                    'Job_Skills': row['job_skills']
                })

        for resume_id, data in resume_groups.items():
            row = {
                'Filename': data['Filename'],
                'Name': data['Name'],
                'Email': data['Email'],
                'Phone': data['Phone'],
                'Skills': data['Skills']
            }
            for i, job in enumerate(data['Jobs'], 1):
                row[f'Job{i}'] = job['Job']
                row[f'Job{i}_Score'] = job['Score']
                row[f'Job{i}_Skills'] = job['Job_Skills']
            df_data.append(row)

        df = pd.DataFrame(df_data)
        csv_buffer = BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        return send_file(
            csv_buffer,
            mimetype='text/csv',
            as_attachment=True,
            download_name='resume_predictions.csv'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/resume/<int:resume_id>", methods=["GET"])
def serve_resume(resume_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM resumes WHERE id = %s", (resume_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if not result or not result[0]:
            return jsonify({"error": "Resume not found"}), 404

        file_path = result[0]
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found on server"}), 404

        return send_file(file_path, as_attachment=False)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/store_resume", methods=["POST"])
def store_resume():
    try:
        data = request.json
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Invalid data provided"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor()

        sql = """
        INSERT INTO resumes (name, phone, email, skills, uploaded_at, file_path)
        VALUES (%s, %s, %s, %s, NOW(), %s)
        """
        values = (
            data.get("name", "None"),
            data.get("phone", "None"),
            data.get("email", "None"),
            data.get("skills", "None"),
            data.get("file_path", None)
        )
        cursor.execute(sql, values)
        resume_id = cursor.lastrowid

        job_predictions = data.get("job_predictions", [])
        if job_predictions:
            job_query = """
            INSERT INTO resume_jobs (resume_id, job_role, score, job_skills)
            VALUES (%s, %s, %s, %s)
            """
            for job in job_predictions:
                job_values = (
                    resume_id,
                    job.get("job", "Unknown"),
                    job.get("score", 0),
                    ",".join(job.get("skills", [])) if job.get("skills") else "None"
                )
                cursor.execute(job_query, job_values)

        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Resume data stored successfully")
        socketio.emit('new_resume', {**data, 'id': resume_id})
        return jsonify({"message": "Resume data stored successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/resumes", methods=["GET"])
def get_resumes():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor(dictionary=True)

        # Get query parameters
        skills = request.args.get('skills', '').strip()
        job_role = request.args.get('job_role', '').strip()
        min_score = request.args.get('min_score', type=int)
        max_score = request.args.get('max_score', type=int)
        name = request.args.get('name', '').strip()
        sort_by = request.args.get('sort_by', 'top_score')
        sort_order = request.args.get('sort_order', 'desc').upper()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        show_all_jobs = request.args.get('show_all_jobs', 'false').lower() == 'true'

        # Build query
        query = """
        SELECT r.id, r.name, r.phone, r.email, r.skills, r.file_path,
               rj.job_role, rj.score, rj.job_skills
        FROM resumes r
        LEFT JOIN resume_jobs rj ON r.id = rj.resume_id
        WHERE 1=1
        """
        params = []
        conditions = []

        if skills:
            skills_list = [s.strip().lower() for s in skills.split(',') if s.strip()]
            if skills_list:
                conditions.append("LOWER(r.skills) LIKE %s")
                params.append('%' + '%'.join(skills_list) + '%')

        if job_role:
            conditions.append("LOWER(rj.job_role) LIKE %s")
            params.append(f'%{job_role.lower()}%')

        if name:
            conditions.append("LOWER(r.name) LIKE %s")
            params.append(f'%{name.lower()}%')

        if min_score is not None or max_score is not None:
            conditions.append("rj.score BETWEEN %s AND %s")
            params.append(min_score if min_score is not None else 0)
            params.append(max_score if max_score is not None else 100)

        if conditions:
            query += " AND " + " AND ".join(conditions)

        # Sorting
        if sort_by == 'top_score':
            query += " ORDER BY rj.score " + sort_order
        elif sort_by == 'name':
            query += " ORDER BY r.name " + sort_order

        # Pagination
        offset = (page - 1) * per_page
        query += " LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        # Execute query
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Group by resume
        resumes = {}
        for row in rows:
            resume_id = row['id']
            if resume_id not in resumes:
                resumes[resume_id] = {
                    'id': resume_id,
                    'name': row['name'],
                    'phone': row['phone'],
                    'email': row['email'],
                    'skills': row['skills'],
                    'file_path': row['file_path'],
                    'job_predictions': []
                }
            if row['job_role']:
                resumes[resume_id]['job_predictions'].append({
                    'job': row['job_role'],
                    'score': row['score'],
                    'skills': row['job_skills'].split(',') if row['job_skills'] and row['job_skills'] != 'None' else []
                })

        resume_list = list(resumes.values())
        if sort_by == 'top_score' and not job_role:
            resume_list.sort(key=lambda x: max([p['score'] for p in x['job_predictions']] or [0]), reverse=(sort_order == 'DESC'))

        # Get total count for pagination
        count_query = "SELECT COUNT(DISTINCT r.id) AS total FROM resumes r LEFT JOIN resume_jobs rj ON r.id = rj.resume_id WHERE 1=1"
        if conditions:
            count_query += " AND " + " AND ".join(conditions)
        cursor.execute(count_query, params[:-2])
        total = cursor.fetchone()['total']

        cursor.close()
        conn.close()
        return jsonify({
            "resumes": resume_list,
            "total": total,
            "page": page,
            "per_page": per_page
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stats", methods=["GET"])
def get_stats():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cursor = conn.cursor()

        # Job counts (all resumes, all job predictions)
        cursor.execute("SELECT job_role, COUNT(*) AS count FROM resume_jobs GROUP BY job_role")
        job_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Filtered job counts (apply filters and adjust for show_all_jobs)
        skills = request.args.get('skills', '').strip()
        job_role = request.args.get('job_role', '').strip()
        min_score = request.args.get('min_score', type=int)
        max_score = request.args.get('max_score', type=int)
        name = request.args.get('name', '').strip()
        show_all_jobs = request.args.get('show_all_jobs', 'false').lower() == 'true'

        if show_all_jobs:
            # Count all job predictions that match the filters
            filtered_query = """
            SELECT rj.job_role, COUNT(*) AS count
            FROM resumes r
            JOIN resume_jobs rj ON r.id = rj.resume_id
            WHERE 1=1
            """
            params = []
            conditions = []

            if skills:
                skills_list = [s.strip().lower() for s in skills.split(',') if s.strip()]
                if skills_list:
                    conditions.append("LOWER(r.skills) LIKE %s")
                    params.append('%' + '%'.join(skills_list) + '%')

            if job_role:
                conditions.append("LOWER(rj.job_role) LIKE %s")
                params.append(f'%{job_role.lower()}%')

            if name:
                conditions.append("LOWER(r.name) LIKE %s")
                params.append(f'%{name.lower()}%')

            if min_score is not None or max_score is not None:
                conditions.append("rj.score BETWEEN %s AND %s")
                params.append(min_score if min_score is not None else 0)
                params.append(max_score if max_score is not None else 100)

            if conditions:
                filtered_query += " AND " + " AND ".join(conditions)

            filtered_query += " GROUP BY rj.job_role"
            cursor.execute(filtered_query, params)
            filtered_job_counts = {row[0]: row[1] for row in cursor.fetchall() if row[0]}
        else:
            # Count only the top-scoring job per resume that matches the filters
            filtered_query = """
            SELECT sub.job_role, COUNT(*) AS count
            FROM (
                SELECT r.id, rj.job_role,
                       ROW_NUMBER() OVER (PARTITION BY r.id ORDER BY rj.score DESC) AS rn
                FROM resumes r
                JOIN resume_jobs rj ON r.id = rj.resume_id
                WHERE 1=1
            """
            params = []
            conditions = []

            if skills:
                skills_list = [s.strip().lower() for s in skills.split(',') if s.strip()]
                if skills_list:
                    conditions.append("LOWER(r.skills) LIKE %s")
                    params.append('%' + '%'.join(skills_list) + '%')

            if job_role:
                conditions.append("LOWER(rj.job_role) LIKE %s")
                params.append(f'%{job_role.lower()}%')

            if name:
                conditions.append("LOWER(r.name) LIKE %s")
                params.append(f'%{name.lower()}%')

            if min_score is not None or max_score is not None:
                conditions.append("rj.score BETWEEN %s AND %s")
                params.append(min_score if min_score is not None else 0)
                params.append(max_score if max_score is not None else 100)

            if conditions:
                filtered_query += " AND " + " AND ".join(conditions)

            filtered_query += """
            ) sub
            WHERE sub.rn = 1
            GROUP BY sub.job_role
            """
            cursor.execute(filtered_query, params)
            filtered_job_counts = {row[0]: row[1] for row in cursor.fetchall() if row[0]}

        cursor.close()
        conn.close()
        return jsonify({
            "job_counts": {
                "labels": list(job_counts.keys()),
                "values": list(job_counts.values())
            },
            "filtered_job_counts": {
                "labels": list(filtered_job_counts.keys()),
                "values": list(filtered_job_counts.values())
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@socketio.on('resume_processing')
def handle_resume_processing(data):
    print(f"Received resume_processing: {data}")
    file_path = data['file_path']
    if file_path in file_statuses:
        file_statuses[file_path]['status'] = 'processing'
    emit('upload_status', {
        'file_path': file_path,
        'status': 'processing',
        'filename': file_statuses.get(file_path, {}).get('filename', os.path.basename(file_path))
    }, broadcast=True)

@socketio.on('resume_processed')
def handle_resume_processed(data):
    print(f"Received resume_processed: {data}")
    file_path = data['file_path']
    if file_path in file_statuses:
        file_statuses[file_path]['status'] = data['status']
        if data['status'] == 'completed':
            file_statuses[file_path]['data'] = data.get('data', {})
        else:
            file_statuses[file_path]['error'] = data.get('error', 'Unknown error')
    emit('upload_status', {
        'file_path': file_path,
        'status': data['status'],
        'filename': file_statuses.get(file_path, {}).get('filename', os.path.basename(file_path)),
        'data': data.get('data'),
        'error': data.get('error')
    }, broadcast=True)

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == "__main__":
    print("🚀 Starting Flask app on port 5001...")
    socketio.run(app, debug=True, port=5001)