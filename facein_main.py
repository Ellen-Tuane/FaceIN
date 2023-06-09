import numpy as np
import os
import cv2
import csv
import tkinter as tk
from tkinter import *
from tkinter import messagebox
from PIL import Image
from PIL import ImageTk
import face_recognition
from os import listdir
from os.path import isfile, join
from datetime import datetime, timedelta
import serial

# Set up GUI
window = tk.Tk()  # Makes main window
window.wm_title("FaceIn - for Access Control")
window.config(background="#080303")

# Load and resize background image
background_image = Image.open("./Portal/images/background.png")

# Get image dimensions
largura_da_janela, altura_da_janela = background_image.size
#window.geometry(f"{largura_da_janela}x{altura_da_janela}")

# Create PhotoImage from background image
background_photo = ImageTk.PhotoImage(background_image)

# Create label for background image
background_label = tk.Label(window, image=background_photo)
background_label.place(x=0, y=0, relwidth=1, relheight=1)

# Load and display logo image
logo_image = Image.open("./Portal/images/logo-horizontal.png")
logo_photo = ImageTk.PhotoImage(logo_image)
logo_label = tk.Label(window, image=logo_photo)
logo_label.pack()

font = cv2.FONT_HERSHEY_SIMPLEX
small_font = cv2.FONT_HERSHEY_COMPLEX_SMALL
known_face_encodings = []
known_face_names = []

face_names = []
registration = False

mypath = "./people"

for f in listdir(mypath):
    if isfile(join(mypath, f)):
        image = face_recognition.load_image_file(join(mypath, f))
        face_encoding = face_recognition.face_encodings(image)[0]
        known_face_encodings.append(face_encoding)
        known_face_names.append(f[:-4])

file_name = "./logs/accessLog"
if not os.path.exists(file_name):
    f = open(file_name, 'a+')
    f.close()

# Open serial connection with ESP32
ser = serial.Serial('/dev/ttyUSB0', 115200)  # Change '/dev/ttyUSB0' to the correct port

def send_access_signal(a):
    if a == 1:
        ser.write(b'1')
    else:
        ser.write(b'0')

# Graphics window
imageFrame = tk.Frame(window, width=largura_da_janela, height=altura_da_janela, bg="black")
imageFrame.pack(pady=20)

# Capture video frames
cap = cv2.VideoCapture(2)

last_access_time = datetime.now() - timedelta(seconds=31)  # Initialize last access time

def close_window():
    window.quit()

def register(face_names):
    for name in face_names:
        if name != "Unknown":
            now = datetime.now()
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
            with open(file_name, 'r') as file:
                lines = file.readlines()
                last_line = lines[-1] if lines else ""
                if not last_line.startswith(timestamp) and now - last_access_time > timedelta(seconds=5):
                    f = open(file_name, 'a+')
                    f.write(timestamp + "\t" + name + "\n")
                    f.close()

def is_face_new(face_encoding, last_face_encodings):
    if not last_face_encodings:
        return True
    return not any(np.all(face_encoding == encoding) for encoding in last_face_encodings)

def show_frame():
    # Initialize some variables
    face_locations = []
    face_encodings = []
    process_this_frame = True
    global face_names
    face_names = []
    global last_face_encodings
    last_face_encodings = []
    global last_access_time

    _, frame = cap.read()
    small_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)

    cv2.putText(frame, str(datetime.now().strftime("%H:%M %d/%m/%Y")), (20, 20), font, .5, (8, 3, 3), 2, cv2.LINE_AA)
    # Resize frame of video to 1/4 size for faster face recognition processing
    small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
    # Only process every other frame of video to save time
    if process_this_frame:
        # Find all the faces and face encodings in the current frame of video
        face_locations = face_recognition.face_locations(small_frame)
        face_encodings = face_recognition.face_encodings(small_frame, face_locations)
        face_names = []

        for face_encoding in face_encodings:
            # See if the face is a match for the known face(s)
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
            # If a match was found in known_face_encodings, just use the first one.
            if sum(matches) == 1 and True in matches:
                first_match_index = matches.index(True)
                name = known_face_names[first_match_index]
                face_names.append(name)
            elif sum(matches) > 1:
                # Or instead, use the known face with the smallest distance to the new face
                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                best_match_index = np.argmin(face_distances)
                if face_distances[best_match_index]:
                    name = known_face_names[best_match_index]
                face_names.append(name)
            else:
                # If no match was found, mark it as "Não Reconhecido"
                face_names.append("Não Reconhecido")

        # Check if any recognized faces exist
        if len(face_names) > 0:
            # Register the face in the access log
            register(face_names)

            # Update last access time and last face encodings
            last_access_time = datetime.now()
            last_face_encodings = face_encodings

    process_this_frame = not process_this_frame

    # Display the results
    for (top, right, bottom, left), name in zip(face_locations, face_names):
        # Scale back up face locations since the frame we detected in was scaled to 1/2 size
        top *= 2
        right *= 2
        bottom *= 2
        left *= 2

        # Draw a box around the face
        if name == "Não Reconhecido":
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)  # Changed box color to red
        else:
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)  # Changed box color to green

        # Check if face is recognized and display "Liberado" or "Acesso Negado"
        if name == "Não Reconhecido":
            cv2.putText(frame, "", (left + 6, bottom - 6), font, 1.0, (255, 0, 0), 1)  # Leave the label blank
            cv2.putText(frame, "Acesso Negado", (int((left + right) / 2) - 75, bottom + 25), font, 1.0, (0, 0, 255), 2, cv2.LINE_AA)  # Changed text color to red
            send_access_signal(0)
        else:
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)  # Changed label box color to green
            cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 2)
            cv2.putText(frame, "Liberado", (int((left + right) / 2) - 60, bottom + 25), font, 1.0, (0, 255, 0), 2, cv2.LINE_AA)  # Changed text color to green
            # Send "Liberado" signal to ESP32
            send_access_signal(1)

    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
    img = Image.fromarray(frame)
    imgtk = ImageTk.PhotoImage(image=img)
    lmain.imgtk = imgtk
    lmain.configure(image=imgtk)
    lmain.after(10, show_frame)

lmain = tk.Label(imageFrame)
lmain.grid(row=0, column=0)

# Create exit button
button = Button(window, text="Exit", command=close_window)
send_access_signal(0)
button.pack()

show_frame()  # Display
window.mainloop()
