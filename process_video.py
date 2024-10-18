import os
import json
from moviepy.editor import VideoFileClip
import speech_recognition as sr
import math


def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def split_into_phrases(text, min_words=15, max_words=30):
    words = text.split()
    phrases = []
    current_phrase = []
    
    for word in words:
        current_phrase.append(word)
        if len(current_phrase) >= min_words and (len(current_phrase) >= max_words or word.endswith(('.', '!', '?'))):
            phrases.append(' '.join(current_phrase))
            current_phrase = []
    
    if current_phrase:
        if len(current_phrase) < min_words and phrases:
            phrases[-1] += ' ' + ' '.join(current_phrase)
        else:
            phrases.append(' '.join(current_phrase))
    
    return phrases

def extract_text_from_video(video_path, segment_duration=10):  # Ridotto a 10 secondi per una maggiore granularità
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
            segment_text = ""  # Testo vuoto per i silenzi
        except sr.RequestError as e:
            print(f"Errore nella richiesta al servizio Google Speech Recognition; {e}")
            segment_text = ""
        
        # Aggiungi sempre un'entrata, anche se il testo è vuoto
        phrases_with_timestamps.append({
            "text": segment_text,
            "start_time": format_timestamp(start_time),
            "end_time": format_timestamp(end_time)
        })
        
        print(f"Testo estratto da {format_timestamp(start_time)} a {format_timestamp(end_time)}")
    
    video.close()
    return full_text.strip(), phrases_with_timestamps

def reconstruct_text_from_json(json_file_path):
    with open(json_file_path, 'r', encoding='utf-8') as file:
        phrases_with_timestamps = json.load(file)
    
    phrases_with_timestamps.sort(key=lambda x: x['start_time'])
    full_text = ' '.join(phrase['text'] for phrase in phrases_with_timestamps if phrase['text'])
    
    return full_text

# Funzione principale per processare il video
def process_video(video_path):
    testo_completo, frasi_con_timestamp = extract_text_from_video(video_path)

    # Salva il testo estratto in un file txt
    with open("testo_estratto.txt", "w", encoding="utf-8") as file:
        file.write(testo_completo)

    # Salva le frasi con i timestamp in un file JSON
    json_file_path = "frasi_con_timestamp.json"
    with open(json_file_path, "w", encoding="utf-8") as file:
        json.dump(frasi_con_timestamp, file, ensure_ascii=False, indent=2)

    print("\nTesto completo estratto dal video e salvato in 'testo_estratto.txt'")
    print("Frasi con timestamp salvate in 'frasi_con_timestamp.json'")

    # Ricostruisci il testo dal JSON
    testo_ricostruito = reconstruct_text_from_json(json_file_path)

    # Salva il testo ricostruito in un nuovo file
    with open('testo_ricostruito.txt', 'w', encoding='utf-8') as file:
        file.write(testo_ricostruito)

    print("\nTesto ricostruito salvato in 'testo_ricostruito.txt'")

    return json_file_path, testo_ricostruito

# Modifica la funzione process_video per accettare un percorso di output
def process_video(video_path, output_folder):
    testo_completo, frasi_con_timestamp = extract_text_from_video(video_path)

    # Crea la cartella di output se non esiste
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Salva il testo estratto in un file txt
    txt_path = os.path.join(output_folder, "testo_estratto.txt")
    with open(txt_path, "w", encoding="utf-8") as file:
        file.write(testo_completo)

    # Salva le frasi con i timestamp in un file JSON
    json_file_path = os.path.join(output_folder, "frasi_con_timestamp.json")
    with open(json_file_path, "w", encoding="utf-8") as file:
        json.dump(frasi_con_timestamp, file, ensure_ascii=False, indent=2)

    # Ricostruisci il testo dal JSON
    testo_ricostruito = reconstruct_text_from_json(json_file_path)

    # Salva il testo ricostruito in un nuovo file
    ricostruito_path = os.path.join(output_folder, "testo_ricostruito.txt")
    with open(ricostruito_path, "w", encoding="utf-8") as file:
        file.write(testo_ricostruito)

    return json_file_path, testo_ricostruito