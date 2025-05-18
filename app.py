from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import cv2
import numpy as np
from threading import Thread
import time
import shutil

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///security.db'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Global variables for video streaming
camera = None
motion_detector = None
is_recording = False
last_motion_time = None
motion_status = {'motion': False, 'last_motion': None}

class MotionDetector:
    def __init__(self):
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(history=100, varThreshold=50, detectShadows=False)
        self.recording = False
        self.output_video = None
        self.motion_detected = False
        self.last_motion_time = 0
        self.alert_cooldown = 5  # seconds between alerts
        self.motion_start_time = None
        self.current_recording_filename = None
        self.frame_written = False
        
        # Create directories if they don't exist
        if not os.path.exists('recordings'):
            os.makedirs('recordings')
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        # Initialize log files
        self.log_file = 'logs/motion_log.txt'
        self.excel_file = 'logs/motion_log.xlsx'
        self.initialize_logs()
    
    def initialize_logs(self):
        # Initialize text log file with header
        with open(self.log_file, 'w') as f:
            f.write("Motion Detection Log\n")
            f.write("===================\n\n")
    
    def log_motion_event(self, start_time=None, end_time=None):
        timestamp = datetime.now()
        date_str = timestamp.strftime("%Y-%m-%d")
        time_str = timestamp.strftime("%H:%M:%S")
        
        with open(self.log_file, 'a') as f:
            if start_time:
                f.write(f"Motion Detected - {date_str} {time_str}\n")
            if end_time:
                duration_seconds = (end_time - start_time).total_seconds()
                f.write(f"Motion Ended - Duration: {duration_seconds:.2f} seconds\n")
                f.write("-" * 50 + "\n")
    
    def start_recording(self):
        if not self.recording:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"motion_{timestamp}.mp4"
            filepath = os.path.join('recordings', filename)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = 20.0
            frame_size = (640, 480)  # Adjust based on your camera
            self.output_video = cv2.VideoWriter(filepath, fourcc, fps, frame_size)
            self.recording = True
            self.motion_start_time = datetime.now()
            self.log_motion_event(start_time=self.motion_start_time)
            global motion_status
            motion_status['motion'] = True
            motion_status['last_motion'] = self.motion_start_time.strftime('%Y-%m-%d %H:%M:%S')
            self.current_recording_filename = filename
            self.frame_written = False
    
    def stop_recording(self):
        if self.recording:
            self.output_video.release()
            self.recording = False
            self.output_video = None
            self.log_motion_event(end_time=datetime.now(), start_time=self.motion_start_time)
            global motion_status
            motion_status['motion'] = False
            # Delete file if no frames were written or file is too small
            filepath = os.path.join('recordings', self.current_recording_filename)
            try:
                if not self.frame_written or os.path.getsize(filepath) < 100*1024:  # less than 100KB
                    os.remove(filepath)
            except Exception:
                pass
            self.current_recording_filename = None
            self.frame_written = False
    
    def process_frame(self, frame):
        # Apply background subtraction
        fg_mask = self.background_subtractor.apply(frame)
        
        # Apply noise reduction
        kernel = np.ones((5,5), np.uint8)
        fg_mask = cv2.erode(fg_mask, kernel, iterations=1)
        fg_mask = cv2.dilate(fg_mask, kernel, iterations=2)
        
        # Find contours of moving objects
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Check for significant motion
        motion_detected = False
        for contour in contours:
            if cv2.contourArea(contour) > 500:  # Filter small contours
                motion_detected = True
                (x, y, w, h) = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        # Handle motion detection events
        current_time = time.time()
        if motion_detected:
            if not self.motion_detected:
                self.motion_detected = True
                self.start_recording()
        else:
            if self.motion_detected:
                self.motion_detected = False
                self.stop_recording()
        
        return frame, fg_mask

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_frames():
    global camera, motion_detector
    if camera is None:
        camera = cv2.VideoCapture(0)
    if motion_detector is None:
        motion_detector = MotionDetector()
    
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Process frame for motion detection
            processed_frame, fg_mask = motion_detector.process_frame(frame)
            
            # Add status information
            status = "RECORDING" if motion_detector.recording else "Monitoring"
            cv2.putText(processed_frame, f'Status: {status}', (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            # Record if motion is detected
            if motion_detector.recording and motion_detector.output_video is not None:
                motion_detector.output_video.write(processed_frame)
                motion_detector.frame_written = True
            
            # Create a combined display
            height = 480
            width = int(height * processed_frame.shape[1] / processed_frame.shape[0])
            processed_frame_resized = cv2.resize(processed_frame, (width, height))
            fg_mask_resized = cv2.resize(fg_mask, (width, height))
            
            # Convert mask to BGR for display
            fg_mask_color = cv2.cvtColor(fg_mask_resized, cv2.COLOR_GRAY2BGR)
            
            # Combine frames horizontally
            combined_frame = np.hstack((processed_frame_resized, fg_mask_color))
            
            ret, buffer = cv2.imencode('.jpg', combined_frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
@login_required
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
            
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
            
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Get list of recordings and logs
    recordings = []
    logs = []
    
    # Read recordings directory
    if os.path.exists('recordings'):
        recordings = [f for f in os.listdir('recordings') if f.endswith('.mp4')]
    
    # Read logs
    if os.path.exists('logs/motion_log.txt'):
        with open('logs/motion_log.txt', 'r') as f:
            logs = f.readlines()
    
    return render_template('dashboard.html', 
                         recordings=recordings, 
                         logs=logs,
                         is_admin=current_user.role == 'admin')

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    return render_template('admin.html', users=users)

@app.route('/update_role', methods=['POST'])
@login_required
def update_role():
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403
        
    user_id = request.form.get('user_id')
    new_role = request.form.get('role')
    
    user = User.query.get(user_id)
    if user:
        user.role = new_role
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'User not found'}), 404

@app.route('/logout')
@login_required
def logout():
    global camera
    if camera is not None:
        camera.release()
        camera = None
    logout_user()
    return redirect(url_for('login'))

@app.route('/recordings/<path:filename>')
@login_required
def play_recording(filename):
    # Render a template with an HTML5 video player
    return render_template('play_recording.html', filename=filename)

@app.route('/recordings/raw/<path:filename>')
@login_required
def serve_recording(filename):
    return send_from_directory('recordings', filename, mimetype='video/mp4')

@app.route('/motion_status')
@login_required
def motion_status_api():
    return jsonify(motion_status)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@example.com', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True, host='0.0.0.0', port=5000) 