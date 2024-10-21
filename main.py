from flask import Flask, render_template, request, redirect, url_for, send_file
import os
from process_video import process_video
import json

app = Flask(__name__)

# Configura le cartelle
UPLOAD_FOLDER = 'static/uploads'
OUTPUT_FOLDER = 'static/output'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Assicurati che le cartelle esistano
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = file.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Processa il video
            output_folder = os.path.join(app.config['OUTPUT_FOLDER'], filename.rsplit('.', 1)[0])
            json_file_path, testo_completo, processing_time = process_video(file_path, output_folder)
            
            return redirect(url_for('file_processed', filename=filename, processing_time=processing_time))
    return render_template('upload.html')

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
    output_folder = os.path.join(app.config['OUTPUT_FOLDER'], base_filename)
    if filetype == 'json':
        path = os.path.join(output_folder, "frasi_con_timestamp.json")
    elif filetype == 'txt':
        path = os.path.join(output_folder, "testo_ricostruito.txt")
    else:
        return "File non valido"
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)