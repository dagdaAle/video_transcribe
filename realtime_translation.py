from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import speech_recognition as sr
import numpy as np
import threading
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a real secret key
socketio = SocketIO(app, cors_allowed_origins="*")

recognizer = sr.Recognizer()
SAMPLE_RATE = 16000

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    try:
        # Log the size and type of incoming data
        logger.debug(f"Received audio chunk. Type: {type(data)}, Size: {len(data)} bytes")
        
        # Ensure data is bytes
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Check if data size is valid
        if len(data) % 2 != 0:
            logger.warning(f"Invalid data size: {len(data)}. Padding with zero.")
            data += b'\0'
        
        audio_data = np.frombuffer(data, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        threading.Thread(target=process_audio, args=(audio_bytes,)).start()
    except Exception as e:
        logger.error(f"Error in handle_audio_chunk: {str(e)}")
        emit('error', {'message': str(e)})

def process_audio(audio_bytes):
    try:
        audio_data = sr.AudioData(audio_bytes, SAMPLE_RATE, 2)
        logger.debug(f"Processing audio. Size: {len(audio_bytes)} bytes")
        text = recognizer.recognize_google(audio_data, language="it-IT")
        logger.info(f"Transcription result: {text}")
        socketio.emit('transcription_result', {'text': text})
    except sr.UnknownValueError:
        logger.warning("Speech recognition could not understand the audio")
        socketio.emit('transcription_result', {'text': "Could not understand audio"})
    except sr.RequestError as e:
        logger.error(f"Could not request results from speech recognition service; {e}")
        socketio.emit('error', {'message': f"Speech recognition service error: {str(e)}"})
    except Exception as e:
        logger.error(f"Unexpected error in process_audio: {str(e)}")
        socketio.emit('error', {'message': f"Unexpected error: {str(e)}"})

if __name__ == '__main__':
    socketio.run(app, debug=True)