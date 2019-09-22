# © 2017, 2018 published Massachusetts Institute of Technology.
import json
import logging 
from twisted.protocols.basic import LineReceiver
from twisted.internet import task
from zephyr.collector import SignalPacketIterator
from zephyr.bioharness import BioHarnessPacketHandler
from zephyr.message import MessagePayloadParser, SummaryMessage, SignalSample, AccelerationSignalSample
from zephyr.protocol import MessageFrameParser, create_message_frame
from collections import deque
from twisted.internet.serialport import SerialPort
import sys

class BioharnessProtocol(LineReceiver):    
    message_ids = {
                   "ecg": 0x16,
                   "breathing": 0x15,
                   "acceleration": 0x1E,               
                   "rr": 0x19,
                   "summary": 0xBD,
                   "life_sign" : 0xA4,
                   }
    
    stream_states = {"ON":1, "OFF":0}
    
    columns_of_streams = {
                      "summary" : SummaryMessage._fields,
                      "breathing" : SignalSample._fields,
                      "ecg" : SignalSample._fields,
                      "rr" : SignalSample._fields,                   
                      "acceleration": AccelerationSignalSample._fields,                      
                      }

    def __init__(self, port, reactor):
        self.buffers = {}
        self.buffers["rr"] = deque(maxlen=18)
        self.buffers["ecg"] = deque(maxlen=250)
        self.buffers["breathing"] = deque(maxlen=25)
        self.buffers["acceleration_x"] = deque(maxlen=100)
        self.buffers["acceleration_y"] = deque(maxlen=100)
        self.buffers["acceleration_z"] = deque(maxlen=100)
        self.hr_last_val = 0
        self.br_last_val = 0
        self.ecg_conf_last_val = 0
        self.loop = task.LoopingCall(self.send_data_for_processing_multiple)

        self.processing_proxy = None
        self.port = port
        self.reactor = reactor
        self.serial = None

    def send_device_command(self, message_id, payload):
        message_frame = create_message_frame(message_id, payload)
        logging.info("Bioharness - sending a command to the device: msg_id : %s, Payload : %s" % (message_id, payload))
        self.transport.write(message_frame)

    def set_stream_state(self, stream_id, state):
        self.send_device_command(self.message_ids[stream_id], [self.stream_states[state]])

    def disable_lifesign_timeout(self):
        self.send_device_command(self.message_ids["life_sign"], [0,0,0,0])    

    def set_summary_packet_transmit_interval_to_one_second(self):
        self.send_device_command(self.message_ids["summary"], [1, 0])
        
    def send_initialization_commands(self):
        self.set_stream_state("ecg", "ON")
        self.set_stream_state("breathing", "ON")
        self.set_stream_state("acceleration", "ON")
        self.set_stream_state("rr", "ON")
        self.disable_lifesign_timeout()
        self.set_summary_packet_transmit_interval_to_one_second()
        
    def default_signal_waveform_handler(self, signal_packet, start_new_stream):
        samples_iterator = SignalPacketIterator(signal_packet).iterate_timed_samples()
        for signal_sample in samples_iterator:
            self.logger_of_stream[signal_sample.type].write_tuple_to_log_file(signal_sample)
            
            # buffer samples
            if signal_sample.type is not "acceleration":
                self.buffers[signal_sample.type].append(signal_sample.sample)
            else:
                self.buffers["acceleration_x"].append(signal_sample.sample_x)   
                self.buffers["acceleration_y"].append(signal_sample.sample_y)   
                self.buffers["acceleration_z"].append(signal_sample.sample_z)   
                
    def display_status_flags(self, summary_packet):
        if (summary_packet.heart_rate_unreliable or summary_packet.respiration_rate_unreliable) or (summary_packet.hrv_unreliable or summary_packet.button_pressed):
            #logging.warn("Bioharness - Heart Rate:%s ; Breathing Rate:%s ; HRV:%s" % ((not summary_packet.heart_rate_unreliable), (not summary_packet.respiration_rate_unreliable), (not summary_packet.hrv_unreliable)))
            pass
            
    def default_event_callback(self, summary_packet):
        self.display_status_flags(summary_packet)
        self.logger_of_stream["summary"].write_tuple_to_log_file(summary_packet)

        # buffer samples
        self.hr_last_val = summary_packet.heart_rate
        self.br_last_val = summary_packet.respiration_rate
        self.ecg_conf_last_val = summary_packet.ecg_wave_confidence

    
    def set_proxy(self, proxy):
        self.processing_proxy = proxy
        self.loop.start(1.0)
            
  
    def send_data_for_processing(self, type, value, timestamp):
        if self.processing_proxy is not None:
            data = {"type":type, "timestamp":timestamp, "value": value}
            self.processing_proxy.notifyAll(data)
           
    def set_event_callbacks(self, callbacks= None):
        if callbacks is None: callbacks=[self.default_event_callback]
        self.event_callbacks = callbacks
        
    def set_waveform_callbacks(self, callbacks= None):
        if callbacks is None: callbacks=[self.default_signal_waveform_handler]
        self.waveform_callbacks = callbacks
        
        
    def set_data_loggers(self, logger_of_stream):
        self.logger_of_stream = logger_of_stream
        
    def connectionMade(self):
        # Setting the protocol to handle raw data rather than just lines
        self.setRawMode()
        
        # Sending commands to enable relevant streams and summary messages
        self.send_initialization_commands()
        
        self.signal_packet_handler_bh = BioHarnessPacketHandler(self.waveform_callbacks, self.event_callbacks)
        self.payload_parser = MessagePayloadParser([self.signal_packet_handler_bh.handle_packet])
        self.message_parser = MessageFrameParser(self.payload_parser.handle_message)

    def rawDataReceived(self, data):
        if not data: return  
        for byte in data:
            self.message_parser.parse_data(byte)
    
    def set_serial(self, serial):
        self.serial = serial
        
    def connectionLost(self, reason):
        logging.error("Bioharness - Lost connection (%s)" % reason)
        logging.info("Bioharness - Reconnecting in 5 seconds...")
        self.serial._serial.close()
        self.retry = self.reactor.callLater(5, self.reconnect)
 
    def reconnect(self):
        try:
            if self.serial is None:
                self.serial = SerialPort(self, self.port, self.reactor, baudrate=115200)
            else:
                self.serial.__init__(self, self.port, self.reactor, baudrate=115200)
            logging.info("Bioharness - Reconnected")
           
        except:
            logging.error("Bioharness - Error opening serial port %s (%s)" % (self.port, sys.exc_info()[1]))
            logging.info("Bioharness - Reconnecting in 5 seconds...")
            self.retry = self.reactor.callLater(5, self.reconnect)
            