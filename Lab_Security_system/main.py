import cv2
import pandas as pd
from ultralytics import YOLO
from tracker import*  #module made to track people
import cvzone
import numpy as np
import asyncio
import websockets
import json

#the model from ultralytics
model=YOLO('yolov8s.pt')

# Initialize WebSocket clients
connected_clients = set()
#mouse event to display coordinates
def RGB(event, x, y, flags, param):
    if event == cv2.EVENT_MOUSEMOVE :  
        point = [x, y]
        print(point)
  
        

cv2.namedWindow('RGB')
cv2.setMouseCallback('RGB', RGB)
esp32_url = "http://192.168.1.177"
# Open a connection to the video stream
#cap = cv2.VideoCapture('video/p.mp4')
cap = cv2.VideoCapture(esp32_url)
my_file = open("coco.txt", "r")
data = my_file.read()
class_list = data.split("\n") 
#print(class_list)

count=0
tracker= Tracker() # calling tracker class

#coordintes of area to count
area1=[(494,289),(505,499),(578,496),(530,292)]
area2=[(548,290),(600,496),(637,493),(574,288)]

going_out= {}
going_in= {}
counter1= []
counter2= []
async def generate_and_send_frames(websocket):
    while True:    
        ret,frame = cap.read()
        if not ret:
            break


    #    count += 1
    #    if count % 3 != 0:
    #        continue
        frame=cv2.resize(frame,(1020,500))
    

        results=model.predict(frame)
    #   print(results)
        a=results[0].boxes.data
        px=pd.DataFrame(a).astype("float")
    #    print(px)
        
        list= []
        for index,row in px.iterrows():
    #        print(row)
            #referencing the coordinates of rectangle
            x1=int(row[0])
            y1=int(row[1])
            x2=int(row[2])
            y2=int(row[3])
            d=int(row[5])
            
            c=class_list[d]
            if 'person' in c:
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
            

    #two areas for direction of movement
        out_c= len(counter1)
        in_c= len(counter2)

                # Send the counters to WebSocket clients
        try:
            await websocket.send(json.dumps({"out_c": out_c, "in_c": in_c}))
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
            break

'''    
    cvzone.putTextRect(frame, f'OUT_C: {out_c}', (50, 60), 2,2) 
    cvzone.putTextRect(frame, f'in_C: {in_c}', (50, 160), 2,2) 
    cv2.polylines(frame, [np.array(area1, np.int32)], True, (0, 255, 0), 1) #drawing lines of area of interest
    cv2.polylines(frame, [np.array(area2, np.int32)], True, (0, 255, 0), 1) #drawing lines of area of interest
    cv2.imshow("RGB", frame)
    if cv2.waitKey(1)&0xFF==27:
        break
cap.release()
cv2.destroyAllWindows()'''

# Handle WebSocket connections
async def handle_connection(websocket, path):
    connected_clients.add(websocket)
    try:
        await generate_and_send_frames(websocket)
    finally:
        connected_clients.remove(websocket)

# Start WebSocket server
start_server = websockets.serve(handle_connection, "0.0.0.0", 8765)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()