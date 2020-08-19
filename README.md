# Mediated-Atmospheres 2.0

## Sensor Collection Server
The *Sensor Cellection Server* is the Mediated Atmospheres 2.0 sensor system building on the [Twisted](https://twistedmatrix.com) event-based networking engine. It handles the connection, the incoming datastream, and the storage of the data of vairous sensors including Zyphir Bioharness 3 (requires [zephyr-bt library](https://github.com/jpaalasm/zephyr-bt/tree/master/src/zephyr)), Empatica E4, and Intraface Facial Feature Tracking Software.

### Config File
Use the *Config File* main.conf to customize the system. This is an exmaple Config File: 
```
{
	"name": "system_0",
	"database": {
		"path": "./data"
	},
	"bioharness": {
		"port":"/dev/cu.BHBHT015621-iSerialPort1"
	},
	"processing": {
		"port": 12345
	}
}
```
**name** is the name of the system.
**database** is the database for data collection. **path** is the local path where you want to store the collected data. The system creates data folders and files for each data stream using this path. The names of the folders and files are a combination of the type of data and the time it was created. 
**bioharness** needs to be included in this file if you want to use the bioharness, otherwise remove this key. **port** is the name of the serial port for the bluetooth connection. To find out which port your Bioharness device is using, you can type ```ls /dev/cu.*``` in a terminal.
To pair the device with you computer use code 1234. 
**processing** needs to be included in this file if you want to do real-time monitoring or data processing, otherwise remove this key. **port** is the associated websocekt port
       

### Real-time Processing Interface
Using the *Real-time Processing Interface* you can monitor incoming sensor data in real-time in a browswer ([localhost:9090](localhost:9090)). You can also connect any real-time *Sensor Processing Software* via Websocket.  

**Port: 12345** (as defined above in the Config File)
Subscribers to real-time processing receive data packages in JSON format at 1Hz (default) update rate. The data package contains all sensor data since the last update. Data that are sampled at a higher rate than 1Hz are packed in an array. For example the data package for the Bioharness is:

```
{
	"type":"bioharness", 
	"rr":[<list of the last second, length 18>], 
	"breathing": [<list of the last second, length 25>],
	"acceleration_x": [<list of the last second, length 100>],
	"acceleration_y": [<list of the last second, length 100>],
	"acceleration_z": [<list of the last second, length 100>],
	"ecg": [<list of the last second, length 250>],
	"respiration_rate": <last value>,
	"heart_rate": <last value>,
	"ecg_conf": <last value>,
	"breathing_conf": <last value>
}
```

### Logging Interface
Using the *Logging Interface* you can remotely command the Sensor Collection Server to start or stop logging data to file via Websocket. 

**Port: 55556**

Commands are in JSON format.
Start logging command:
```
{
	"type": "LOG",
	"name": <scene_name>,
	"subject": <subject_name>
}
```

Stop logging command:
```
{
	"type": "STOP_LOG",
}
```