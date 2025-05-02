# Resume-job-Matching-Application

A web application that analyzes resumes, predicts suitable job roles, and provides a dashboard for insights. Built with Flask, MySQL, Apache Kafka, and Bootstrap, this tool leverages Kafka for real-time resume processing, enabling recruiters to efficiently match candidates to job opportunities.

## Features

- **Resume Upload**: Upload PDF resumes for analysis.
- **Real-Time Processing with Kafka**: Resumes are processed asynchronously using Apache Kafka, ensuring scalability and real-time updates.
- **Job Role Prediction**: Predicts job roles based on skills and resume content.
- **Interactive Dashboard**: Visualize job predictions with a bar chart.
- **Filtering and Sorting**: Filter resumes by skills, job role, and score; sort by name or top score.
- **Real-Time Updates**: Automatically updates the dashboard with new resume uploads using WebSocket and Kafka.
- **Downloadable Results**: Export resume data as a CSV file.
- **Resume Viewer**: View resume PDFs and job predictions in a modal.

## Prerequisites

- Python 3.8+
- MySQL 8.0+
- Apache Kafka 2.8+ (with ZooKeeper)
- Node.js (for Socket.io client)
- Git

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/Resume-job-Matching-Application.git
cd Resume-job-Matching-Application
```

### 2. Set Up a Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
# source venv/bin/activate  # On macOS/Linux
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

Ensure you have the following in `requirements.txt`:
```
Flask==2.0.1
mysql-connector-python==8.0.33
confluent-kafka==2.3.0
PyPDF2==3.0.1
python-dotenv==1.0.1
flask-socketio==5.3.6
```

### 4. Configure MySQL Database
- Install MySQL if not already installed.
- Create a database named `resume_db`:
  ```sql
  mysql -u root -p
  CREATE DATABASE resume_db;
  ```
- Update the database credentials in `.env`:
  ```plaintext
  DB_HOST=localhost
  DB_USER=root
  DB_PASSWORD=yourpassword
  DB_NAME=resume_db
  ```
- Create the required tables:
  ```sql
  USE resume_db;
  CREATE TABLE resumes (
      id INT AUTO_INCREMENT PRIMARY KEY,
      name VARCHAR(255),
      phone VARCHAR(50),
      email VARCHAR(255),
      skills TEXT,
      uploaded_at DATETIME,
      file_path VARCHAR(255)
  );
  CREATE TABLE resume_jobs (
      id INT AUTO_INCREMENT PRIMARY KEY,
      resume_id INT,
      job_role VARCHAR(255),
      score FLOAT,
      job_skills TEXT,
      FOREIGN KEY (resume_id) REFERENCES resumes(id)
  );
  ```

### 5. Set Up Apache Kafka
- Install Kafka and ZooKeeper (Kafka 2.8+ recommended). Download from [Apache Kafka](https://kafka.apache.org/downloads).
- Start ZooKeeper and Kafka servers:
  ```bash
  # Start ZooKeeper (in a new terminal)
  zookeeper-server-start.bat config/zookeeper.properties
  # Start Kafka (in a new terminal)
  kafka-server-start.bat config/server.properties
  ```
- Ensure Kafka is running on `localhost:9092`.
- The application uses Kafka to process uploaded resumes asynchronously. A Kafka topic (`resume_topic`) is created automatically to handle resume data for job prediction.

### 6. Start the Application
- Run the Flask app, which includes Kafka producer and consumer for resume processing:
  ```bash
  python app.py
  ```
- The app will be available at `http://localhost:5001`.

## Usage

1. **Upload Resumes**:
   - Navigate to `http://localhost:5001/`.
   - Upload a PDF resume using the upload form.
   - The resume is sent to a Kafka topic (`resume_topic`) for asynchronous processing, which extracts details and predicts job roles.

2. **View Dashboard**:
   - Go to `http://localhost:5001/results`.
   - Explore the dashboard with a bar chart showing job predictions.
   - Use filters (skills, job role, score) and sorting options (name, top score).
   - Toggle "Show All Job Predictions" to see all predicted roles per resume.
   - New resumes processed via Kafka will automatically update the dashboard in real-time.

3. **View Resumes**:
   - Click on a table row to view the resume PDF and job predictions in a modal.

4. **Download Data**:
   - Click "Download CSV" to export the resume data.

## Technologies Used

- **Backend**: Flask, Python
- **Database**: MySQL
- **Message Queue**: Apache Kafka (for real-time resume processing)
- **Frontend**: Bootstrap, Chart.js, Socket.io
- **File Processing**: PyPDF2

## Project Structure

```
Resume-job-Matching-Application/
├── app.py              # Main Flask application with Kafka integration
├── requirements.txt    # Python dependencies
├── .env                # Environment variables
├── templates/          # HTML templates
│   ├── index.html      # Upload page
│   └── results.html    # Dashboard page
├── static/             # Static files (CSS, JS)
└── Uploads/            # Directory for uploaded resumes
```

## Contributing

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Make your changes and commit (`git commit -m "Add your feature"`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

For any inquiries, please contact [your.email@example.com](mailto:your.email@example.com).