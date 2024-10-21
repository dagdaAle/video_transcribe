import os
import json
from moviepy.editor import VideoFileClip # type: ignore
import speech_recognition as sr # type: ignore
import concurrent.futures
from pydub import AudioSegment
from pydub.silence import split_on_silence
import time
import math

def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def extract_audio_from_video(video_path, audio_path):
    video = VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path, verbose=False, logger=None)
    video.close()

def transcribe_audio_chunk(chunk_path, start_time, end_time, recognizer, language="it-IT"):
    with sr.AudioFile(chunk_path) as source:
        audio = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio, language=language)
        return {
            "text": text,
            "start_time": format_timestamp(start_time),
            "end_time": format_timestamp(end_time)
        }
    except sr.UnknownValueError:
        return {
            "text": "",
            "start_time": format_timestamp(start_time),
            "end_time": format_timestamp(end_time)
        }
    except sr.RequestError as e:
        print(f"Errore nella richiesta al servizio Google Speech Recognition; {e}")
        return {
            "text": "",
            "start_time": format_timestamp(start_time),
            "end_time": format_timestamp(end_time)
        }

def process_audio_file(audio_path, min_silence_len=500, silence_thresh=-40):
    audio = AudioSegment.from_wav(audio_path)
    chunks = split_on_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
    
    chunk_info = []
    start_time = 0
    for i, chunk in enumerate(chunks):
        chunk_path = f"temp_chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")
        end_time = start_time + len(chunk) / 1000.0  # pydub works in milliseconds
        chunk_info.append((chunk_path, start_time, end_time))
        start_time = end_time
    
    return chunk_info

def extract_text_from_video(video_path, segment_duration=10):
    if not os.path.exists("audio_partials"):
        os.makedirs("audio_partials")
    
    video = VideoFileClip(video_path)
    duration = video.duration
    r = sr.Recognizer()
    
    full_text = ""
    phrases_with_timestamps = []
    
    for start_time in range(0, math.ceil(duration), segment_duration):
        end_time = min(start_time + segment_duration, duration)
        
        segment = video.subclip(start_time, end_time)
        audio_file_path = os.path.join("audio_partials", f"temp_audio_{start_time}.wav")
        segment.audio.write_audiofile(audio_file_path, verbose=False, logger=None)
        
        with sr.AudioFile(audio_file_path) as source:
            audio_data = r.record(source)
        
        try:
            segment_text = r.recognize_google(audio_data, language="it-IT")
            full_text += segment_text + " "
        except sr.UnknownValueError:
            segment_text = ""
        except sr.RequestError as e:
            print(f"Errore nella richiesta al servizio Google Speech Recognition; {e}")
            segment_text = ""
        
        phrases_with_timestamps.append({
            "text": segment_text,
            "start_time": format_timestamp(start_time),
            "end_time": format_timestamp(end_time)
        })
        
        print(f"Testo estratto da {format_timestamp(start_time)} a {format_timestamp(end_time)}")
    
    video.close()
    return full_text.strip(), phrases_with_timestamps

def process_video(video_path, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    start_time = time.time()  # Sposta questa linea qui

    testo_completo, frasi_con_timestamp = extract_text_from_video(video_path)

    processing_time = time.time() - start_time  # Calcola il tempo di elaborazione qui

    txt_path = os.path.join(output_folder, "testo_estratto.txt")
    with open(txt_path, "w", encoding="utf-8") as file:
        file.write(testo_completo)

    json_file_path = os.path.join(output_folder, "frasi_con_timestamp.json")
    with open(json_file_path, "w", encoding="utf-8") as file:
        json.dump(frasi_con_timestamp, file, ensure_ascii=False, indent=2)

    return json_file_path, testo_completo, processing_time

# Uso della funzione
# video_path = "percorso/del/tuo/video.mp4"
# output_folder = "percorso/della/cartella/di/output"
# json_file_path, testo_completo, processing_time = process_video(video_path, output_folder)
# print(f"Elaborazione completata in {processing_time:.2f} secondi. JSON salvato in: {json_file_path}")
# print(f"Testo completo estratto:\n{testo_completo[:500]}...")  # Mostra i primi 500 caratteri