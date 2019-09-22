# © 2017, 2018 published Massachusetts Institute of Technology.
from twisted.protocols.basic import LineReceiver
from twisted.internet.protocol import ReconnectingClientFactory
from E4Commands import COMMAND_server_status, COMMAND_device_list, COMMAND_device_connect, COMMAND_device_subscribe, COMMAND_pause, StreamMessagesDecoder
from functools import partial
from Logger import DataLogger
import logging

class StartUpCommandSequence(object):
    def __init__(self, protocol):
        self.protocol = protocol
        self.commands_list = [
                              (self.get_server_status, self.handle_server_status),
                              (self.get_device_list, self.handle_device_list),
                              (self.connect_to_device, self.handle_connect_to_device),
                              
                              # Set here the list of streams you would like to register for
                              (partial(self.pause, state="ON"), self.handle_pause),
                              #(partial(self.subscibe_to_stream, stream="acc"), self.handle_subscribe_to_stream),
                              (partial(self.subscibe_to_stream, stream="bvp"), self.handle_subscribe_to_stream),
                              (partial(self.subscibe_to_stream, stream="gsr"), self.handle_subscribe_to_stream),
                              (partial(self.subscibe_to_stream, stream="tmp"), self.handle_subscribe_to_stream),
                              (partial(self.subscibe_to_stream, stream="ibi"), self.handle_subscribe_to_stream),
                              #(partial(self.subscibe_to_stream, stream="bat"), self.handle_subscribe_to_stream),
                              #(partial(self.subscibe_to_stream, stream="tag"), self.handle_subscribe_to_stream),
                              (partial(self.pause, state="OFF"), self.handle_pause),
                              ]
        
        self.current_command = self.commands_list.pop(0)
        
    def startup_finished(self):
        return len(self.commands_list) == 0
    
    def execute_next_command(self):
        self.current_command[0]()
    
    def handle_command_response(self, line):
        self.current_command[1](line)
        self.current_command = self.commands_list.pop(0)

    # SERVER STATUS
    def get_server_status(self):
        self.protocol.transport.write(COMMAND_server_status.encode_arguments())
        
    def handle_server_status(self, line):
        response = COMMAND_server_status.decode_response(line)
        logging.debug("E4BLEClient - Server Status: %s" % response["RC"])

    # DEVICE LIST
    def get_device_list(self):
        self.protocol.transport.write(COMMAND_device_list.encode_arguments())
    
    def handle_device_list(self, line):
        devices = COMMAND_device_list.decode_response(line)
        self.device = devices[self.protocol.client_index]
            
        assert self.device["AVAILABILITY"] == "available", "Device is not available to connect to: %s" % line
        logging.debug("E4BLEClient - Device list received. Connecting to device %s with name %s" % (self.device["DEVICE_ID"],self.device["DEVICE_NAME"]))
        
    # CONNECTING TO DEVICE
    def connect_to_device(self):
        self.protocol.transport.write(COMMAND_device_connect.encode_arguments(DEVICE_ID=self.device["DEVICE_ID"]))
    
    def handle_connect_to_device(self, line):
        response = COMMAND_device_connect.decode_response(line)
        logging.debug("E4BLEClient - Connected to device successfully")
    
    # PAUSING AND RESUMING    
    def pause(self, state):
        self.protocol.transport.write(COMMAND_pause.encode_arguments(STATE=state))
        
    def handle_pause(self, line):
        response = COMMAND_pause.decode_response(line)
        logging.debug("E4BLEClient - Streams Paused/Resumed")
    
    # SUBSCRIBE TO STREAMS
    
    def subscibe_to_stream(self, stream):
        self.protocol.transport.write(COMMAND_device_subscribe.encode_arguments(STREAM=stream,STATE="ON"))
        self.protocol.stream_decoder.subscribe_to_stream(stream)
        
    def handle_subscribe_to_stream(self, line):
        response = COMMAND_device_subscribe.decode_response(line)
        logging.debug("E4BLEClient - Subscribed to stream %s successfully" % response["STREAM"])
        
    def dummy_handler(self, line):
        return

        
class E4Protocol(LineReceiver):
    delimiter = "\n"    
    
    def set_data_loggers(self, logger_of_stream):
        self.logger_of_stream = logger_of_stream
        
    def set_instance_index(self, index):
        self.client_index = index
        
    def set_stream_decoder(self, stream_decoder):
        self.stream_decoder = stream_decoder
            
    def connectionMade(self):
        self.startup_sequence = StartUpCommandSequence(self)
        self.startup_sequence.execute_next_command()
        
    def lineReceived(self, line):
        if not line: return
        
        if not self.startup_sequence.startup_finished():
            self.startup_sequence.handle_command_response(line)
            self.startup_sequence.execute_next_command()
            return
        
        message_type, message_values = self.stream_decoder.decode_message_by_stream_prefix(line)
        if message_type is None: return
        
        self.logger_of_stream[message_type].write_tuple_to_log_file(message_values)
            
class E4ClientFactory(ReconnectingClientFactory):
    id_of_client = {"L":0, "R":1}

    def set_client_id(self, client):
        self.client_id = self.id_of_client[client]
        
    def set_stream_decoder(self, stream_decoder):
        self.stream_decoder = stream_decoder
        
    def set_data_loggers(self, logger_of_stream):
        self.logger_of_stream = logger_of_stream
        
    def update_data_loggers(self, logger_of_stream):
        self.logger_of_stream = logger_of_stream
        if hasattr(self, "current_instance"):
            self.current_instance.set_data_loggers(logger_of_stream)
    
    def buildProtocol(self, addr):
        self.resetDelay()
        
        protocol = E4Protocol()
        protocol.set_instance_index(self.client_id)
        protocol.set_stream_decoder(self.stream_decoder)
        protocol.set_data_loggers(self.logger_of_stream)
        self.current_instance = protocol
        logging.debug("E4BLEClient - Protocol built for client %s" % self.client_id)        

        return protocol
    
    def clientConnectionLost(self, connector, reason):
        logging.debug('E4BLEClient - E4Client %s Lost connection.  Reason: %s' % (self.client_id, reason))
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        logging.debug('E4BLEClient - E4Client %s Connection failed.  Reason: %s' % (self.client_id, reason))
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)
        
        

    