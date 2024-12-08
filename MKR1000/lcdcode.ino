#include <ArduinoJson.h>

#include <WiFi101.h>

#include <Wire.h>
#include <hd44780.h>           // Main hd44780 header
#include <hd44780ioClass/hd44780_I2Cexp.h> // I2C expander i/o class header
// WiFi Credentials
const char* ssid = "BT-SNCJWW";
const char* pass = "hVLdKuDXhG4tMG";

// LCD Setup
hd44780_I2Cexp lcd;                   // Declare lcd object: auto locates & configures I2C address
const int LCD_COLS = 16;              // Number of columns on the LCD
const int LCD_ROWS = 2;               // Number of rows on the LCD

// People Count
int t_count = 0;                        // Out count

// Server setup
WiFiServer server(5000);

void setup() {
  // Initialize SerialUSB
  SerialUSB.begin(9600);
  while (!SerialUSB); // Wait for SerialUSB connection
  SerialUSB.println("Serial working!");

  // Initialize the LCD
  int status = lcd.begin(LCD_COLS, LCD_ROWS);
  if (status) {
    Serial.print("LCD Error: ");
    Serial.println(status);
    while (true); // Stop here if LCD initialization fails
  }

  lcd.clear();
  lcd.print("People Present:");
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");

 
  // Start the server
  server.begin();
  Serial.println("Server started");



  // Connect to WiFi
  SerialUSB.print("Connecting to WiFi");
  IPAddress local_IP(192, 168, 1, 150); // Replace with a valid unused IP on your network
  IPAddress gateway(192, 168, 1, 1);    // Default gateway (router IP)
  IPAddress subnet(255, 255, 255, 0);   // Subnet mask
  
  WiFi.config(local_IP, gateway, subnet);

  WiFi.begin(ssid, pass);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    SerialUSB.print(".");
  }
  SerialUSB.println("\nConnected to WiFi");
  SerialUSB.print("IP Address: ");
  SerialUSB.println(WiFi.localIP());

  // Start the server
  server.begin();
  SerialUSB.println("Server started on port 5000");

 
}

void loop() {
  // Listen for incoming clients
  WiFiClient client = server.available();
  if (client) {
    SerialUSB.println("Client connected.");

    String currentLine = "";
    String postData = "";
    bool isPostRequest = false;

    while (client.connected()) {
      if (client.available()) {
        char c = client.read();
        
        SerialUSB.write(c); // Echo to Serial Monitor for debugging

        // Detect the start of a POST request
        if (currentLine.startsWith("POST")) {
          isPostRequest = true;
        }
        int contentLength = 0;
        if (currentLine.startsWith("Content-Length: ")) {
           contentLength = currentLine.substring(16).toInt();
        }

        // Read headers and payload
        if (c == '\n' && currentLine.length() == 0 && isPostRequest) {
          // Read the JSON payload
          while (client.available() && postData.length() < contentLength)  {
            postData += (char)client.read();
          }
          break;
        }

        if (c == '\n') {
          currentLine = "";
        } else {
          currentLine += c;
        }
      }
    }

    // Process the POST data
    if (isPostRequest) {
      SerialUSB.println("Received POST data:");
      SerialUSB.println(postData);
      postData.trim();
        // Parse JSON to extract t_count
      StaticJsonDocument<200> jsonDoc;
      DeserializationError error = deserializeJson(jsonDoc, postData);
    
      if (!error) {
        t_count = jsonDoc["t_count"];  // Extract t_count value
        SerialUSB.print("Parsed t_count: ");
        SerialUSB.println(t_count);
      
    
                  // Update LCD
    lcd.clear();
    lcd.print("People Present:");
    lcd.setCursor(0, 1);
        
    lcd.print(t_count);
    }
        

    // Send response to the client
    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: text/plain");
    client.println();
    client.println("Data received!");

    // Close the client connection
    client.stop();
    SerialUSB.println("Client disconnected.");
      }
}
}
