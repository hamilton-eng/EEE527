import cv2
import pandas as pd
from ultralytics import YOLO
from tracker import*  #module made to track people
import cvzone
import numpy as np
import asyncio
import websockets
import json
import requests

from flask import Flask, render_template, Response, jsonify, request
from flask_socketio import SocketIO, emit


# Initialize Flask app and SocketIO
app = Flask(__name__)
socketio = SocketIO(app)


alert_number = 0
t_count = 0 


@app.route("/")
def index():
    """Render the main page."""
    return render_template("index.html", number= alert_number)

#the model from ultralytics
model=YOLO('yolov8s.pt')

# Initialize WebSocket clients
connected_clients = set()


#mouse event to display coordinates
def RGB(event, x, y, flags, param):
    if event == cv2.EVENT_MOUSEMOVE :  
        point = [x, y]
        print(point)
  
        

#cv2.namedWindow('RGB')
#cv2.setMouseCallback('RGB', RGB)
esp32_url = "http://172.20.10.4" 

mkr1000_ip = "http://192.168.1.150:5000"  

# Open a connection to the video stream
cap = cv2.VideoCapture('video/p.mp4')
#cap = cv2.VideoCapture(esp32_url)

#print(class_list)

count=0

tracker= Tracker() # calling tracker class

#coordintes of area to count -----------------------------these are to be updated for room exit/entry
area1=[(494,289),(505,499),(578,496),(530,292)]
area2=[(548,290),(600,496),(637,493),(574,288)]

going_out= {}
going_in= {}
counter1= []
counter2= []

#--------------------------------------------------------------Main logic here
def generate_frames():
    warning_sent = False  # Initialize locally
    global t_count
    while True:    
        ret,frame = cap.read()
        if not ret:
            break


        frame=cv2.resize(frame,(1020,500))
    

        results=model.predict(frame, classes=[0], conf=0.4, iou=0.6)

        a=results[0].boxes.data
                
        px=pd.DataFrame(a).astype("float")

        
        list= []
        for index,row in px.iterrows():

            #referencing the coordinates of rectangle
            x1=int(row[0])
            y1=int(row[1])
            x2=int(row[2])
            y2=int(row[3])
            d=int(row[5])
            

            list.append([x1, y1, x2, y2])
        bbox_idx= tracker.update(list)
        for bbox in bbox_idx:
            x3,y3,x4,y4,id=bbox
            result= cv2.pointPolygonTest(np.array(area2, np.int32), ((x4, y4)), False)#region of interest when y4, x4 enter
            if result>0:
                going_out[id]= (x4, y4) #adding to dictionary id and coordinates
            if id in going_out: # if student passes area two count them
                result1= cv2.pointPolygonTest(np.array(area1, np.int32), ((x4, y4)), False)
                if result1>0:

                    cv2.circle(frame, (x4, y4), 4, (255, 0, 255), 1)    
                    cv2.rectangle(frame, (x3,y3), (x4,y4), (255, 255, 255), 2) # rectangle from class
                    cvzone.putTextRect(frame, f'{id}', (x3, y3), 1,1)  #adding text from class
                    if counter1.count(id)==0:
                        counter1.append(id)

            result2= cv2.pointPolygonTest(np.array(area1, np.int32), ((x4, y4)), False)#region of interest when y4, x4 enter
            if result2>0:
                going_in[id]= (x4, y4) #adding to dictionary id and coordinates
            if id in going_in: # if student passes area two count them
                result3= cv2.pointPolygonTest(np.array(area2, np.int32), ((x4, y4)), False)
                if result3>0:

                    cv2.circle(frame, (x4, y4), 4, (255, 0, 255), 1)    
                    cv2.rectangle(frame, (x3,y3), (x4,y4), (255, 0, 0), 2) # rectangle from class
                    cvzone.putTextRect(frame, f'{id}', (x3, y3), 1,1)  #adding text from class
                    if counter2.count(id)==0: #dont count same id as it takes time to leave the area
                        counter2.append(id)
            

    
        out_c= len(counter1)
        in_c= len(counter2)
        t_count= in_c- out_c
        
        # Check if t_count equals alert_number
        if t_count == alert_number:
            print(f"Warning: t_count ({t_count}) reached alert_number ({alert_number})")
            socketio.emit('warning', {'message': f"Warning: Limit of People in Room Reached> {alert_number}"})
            warning_sent = True
        elif t_count != alert_number and warning_sent:
            print(f"Clearing Warning: ({t_count}) no longer equals alert_number ({alert_number})")
            socketio.emit('clear_warning', {})
            warning_sent = False

        # Encode frame for streaming
        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

#--------------------Communication section ------------------------------------------------------------------------



def send_counts_to_mkr(t_count):
    data = {
        "t_count": t_count,
        
    }
    
    try:
        response = requests.post(
                mkr1000_ip,  # MKR1000 IP
                json=data,
                headers={
                    "Content-Type": "application/json",
                    "Connection": "close"  # Ensure connection is closed after request
                },
                timeout=10  # Set a longer timeout
            )
        print(f"Sent counts to MKR1000: {data}, Response: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send counts to MKR1000: {e}")
        return False
    return True

# Update Flask WebSocket event to include the call
@socketio.on('request_update')
def handle_request_update():
    

    emit('update_counters', {'t_count': t_count})
    if not send_counts_to_mkr(t_count):
        print("Skipping further actions as MKR1000 POST failed.")
    

@app.route("/video_feed")
def video_feed():
    """Video feed route."""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/update_number", methods=["POST"])
def update_number():
    """Update the number based on user interaction."""
    global alert_number
    data = request.get_json()
    print('from web', data)
    change = data.get("change", 0)
    alert_number += change
    print({"number": alert_number})
    return jsonify({"number": alert_number})

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    emit('update_counters', {'t_count': t_count})
    print('connect',t_count)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
