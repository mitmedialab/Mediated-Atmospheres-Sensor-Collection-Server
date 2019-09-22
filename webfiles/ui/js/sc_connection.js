// © 2017, 2018 published Massachusetts Institute of Technology.

// WebSocket sensor collector
var sc_addr = "";
var sc_ws = new WebSocket(sc_addr);
var sc_ws_connected = false;

/**
 * Connect to sensor collector WebSocket server
 */
sc_ws.onopen = function () {
    sc_ws_connected = true;
    console.info("SensorCollector - Connection established...");
};

/**
 * Receive message from sensor collector WebSocket server
 */
sc_ws.onmessage = function (evt) {
    var received_msg = JSON.parse(evt.data);
    console.info("SensorCollector - Message received: ");
    console.info(received_msg);

    switch(received_msg.type) {
    case "bioharness":
        handel_data(received_msg);
        break;
    default:
        console.warn("could not parse message")
}
    
};

/**
 * Close connection with sensor collector WebSocket server
 */
sc_ws.onclose = function () {
    sc_ws_connected = false;
    console.log("SensorCollector - Connection is closed...");
};

/**
 * Send message to sensor collector WebSocket server
 * 
 */
function sendJSONMessageToServer(msg) {
    if (sc_ws_connected) {
        sc_ws.send(JSON.stringify(msg))
    }
};


/**
 * Send message to scene controller WebSocket server
 * control parameters
 */
function sendControlMessageToServer(msg_type, msg_value) {
    sendJSONMessageToServer({
        type: msg_type, value: msg_value
    })
};
