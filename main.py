from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, current_app, abort
from flask_socketio import SocketIO, emit
import os
from process_video import process_video
import json
from threading import Thread, Lock
import numpy as np
import base64
from vosk import Model, KaldiRecognizer

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a real secret key
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure directories
UPLOAD_FOLDER = 'static/uploads'
OUTPUT_FOLDER = 'static/output'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

progress_dict = {}
progress_lock = Lock()

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Ensure directories exist
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Parameters for audio processing
SAMPLE_RATE = 16000

# Initialize Vosk model
model = Model("model")  # Make sure the 'model' directory contains the Vosk model

# Dictionaries to keep track of recognizers per client
recognizers = {}
recognizers_locks = {}
recognizers_lock = Lock()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = file.filename
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                # Reset progress
                with progress_lock:
                    progress_dict[filename] = 0
                
                # Define a progress callback specific to the file
                def progress_callback(percent):
                    with progress_lock:
                        progress_dict[filename] = percent
                
                # Process the video in a separate thread
                output_folder = os.path.join(app.config['OUTPUT_FOLDER'], filename.rsplit('.', 1)[0])
                thread = Thread(target=process_video, args=(file_path, output_folder, progress_callback))
                thread.start()
                
                return jsonify({'status': 'processing', 'filename': filename}), 202
        except Exception as e:
            app.logger.error(f"Error during file upload: {str(e)}")
            return jsonify({"error": str(e)}), 500
    return render_template('upload.html')

@app.route('/progress')
def get_progress():
    filename = request.args.get('filename')
    with progress_lock:
        progress = progress_dict.get(filename, 0)
    return jsonify({'progress': progress})

@app.route('/processed/<filename>')
def file_processed(filename):
    base_filename = filename.rsplit('.', 1)[0]
    output_folder = os.path.join(app.config['OUTPUT_FOLDER'], base_filename)
    json_file_path = os.path.join(output_folder, "frasi_con_timestamp.json")
    processing_time = float(request.args.get('processing_time', 0))
    
    with open(json_file_path, 'r') as f:
        phrases = json.load(f)
    
    return render_template('video_playback.html', filename=filename, phrases=phrases, processing_time=processing_time)

@app.route('/download/<filename>/<filetype>')
def download_file(filename, filetype):
    base_filename = filename.rsplit('.', 1)[0]
    output_folder = os.path.join(current_app.config['OUTPUT_FOLDER'], base_filename)
    
    if filetype == 'json':
        file_name = "frasi_con_timestamp.json"
    elif filetype == 'txt':
        file_name = "testo_estratto.txt"
    else:
        abort(400, description="Tipo di file non valido")
    
    path = os.path.join(output_folder, file_name)
    
    if not os.path.exists(path):
        abort(404, description=f"File non trovato: {path}")
    
    try:
        return send_file(path, as_attachment=True)
    except Exception as e:
        app.logger.error(f"Errore durante l'invio del file: {str(e)}")
        abort(500, description="Errore interno del server durante l'invio del file")

@app.route('/traduzione-tempo-reale')
def traduzione_tempo_reale():
    return render_template('realtime_translate.html')

# Socket.IO event handlers for real-time translation
@socketio.on('connect')
def handle_connect():
    sid = request.sid
    print(f'Client {sid} connesso')

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    print(f'Client {sid} disconnesso')
    with recognizers_lock:
        if sid in recognizers:
            del recognizers[sid]
        if sid in recognizers_locks:
            del recognizers_locks[sid]

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    sid = request.sid
    # Debugging statements
    print(f"Type of data received: {type(data)}")
    print(f"Length of data received: {len(data)}")

    # Handle different data types
    if isinstance(data, bytes):
        # Data is in bytes
        audio_bytes = data
    elif isinstance(data, str):
        # Data might be base64-encoded
        try:
            audio_bytes = base64.b64decode(data)
        except Exception as e:
            print(f"Error decoding base64 data: {e}")
            return
    elif isinstance(data, list):
        # Data is a list of numbers
        audio_bytes = np.array(data, dtype=np.int16).tobytes()
    else:
        print(f"Unsupported data type: {type(data)}")
        return

    # Ensure data length is a multiple of 2
    if len(audio_bytes) % 2 != 0:
        audio_bytes = audio_bytes[:-1]  # Or pad with b'\x00'

    # Process the audio in a separate thread
    Thread(target=process_audio, args=(sid, audio_bytes)).start()

def process_audio(sid, audio_bytes):
    with recognizers_lock:
        if sid not in recognizers:
            recognizers[sid] = KaldiRecognizer(model, SAMPLE_RATE)
            recognizers_locks[sid] = Lock()
    recognizer = recognizers[sid]
    recognizer_lock = recognizers_locks[sid]
    
    with recognizer_lock:
        if recognizer.AcceptWaveform(audio_bytes):
            result = recognizer.Result()
            text = json.loads(result)["text"]
            socketio.emit('transcription_result', {'text': text}, room=sid)
        else:
            partial_result = recognizer.PartialResult()
            partial_text = json.loads(partial_result)["partial"]
            print(f"Partial result: {partial_text}")
            socketio.emit('transcription_partial', {'text': partial_text}, room=sid)

if __name__ == '__main__':
    socketio.run(app, debug=True)
