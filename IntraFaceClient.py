# © 2017, 2018 published Massachusetts Institute of Technology.
import collections
import ast
import subprocess
import logging

from twisted.protocols.basic import LineReceiver
from twisted.internet.protocol import ReconnectingClientFactory
import numpy as np
import os

base_path = os.getcwd()

facial_features = ["X_feature_%s" % index for index in range(1,50)] + ["Y_feature_%s" % index for index in range(1,50)] 

list_of_features = ["timestamp", 
                                                           "neutral", "angry", "disgust", "happy", "sad", "surprised",
                                                           "head_translation_x", "head_translation_y", "head_translation_z", 
                                                           "head_rotation_pitch", "head_rotation_yaw", "head_rotation_roll",
                                                           "left_iris_x_position", "left_iris_y_position", "left_iris_is_closed", 
                                                           "right_iris_x_position", "right_iris_y_position", "right_iris_is_closed",
                                                           "left_pupil_head_relative_x", "left_pupil_head_relative_y", "left_pupil_head_relative_z",
                                                           "left_pupil_head_relative_pitch", "left_pupil_head_relative_yaw", "left_pupil_head_relative_roll", 
                                                           "right_pupil_head_relative_x", "right_pupil_head_relative_y", "right_pupil_head_relative_z",
                                                           "right_pupil_head_relative_pitch", "right_pupil_head_relative_yaw", "right_pupil_head_relative_roll",
                                                           "frame_rate"] + facial_features
                                                           
InrafaceSample = collections.namedtuple("InrafaceSample", list_of_features)   
                                                            
class IntraFaceServerProtocol(LineReceiver):
    delimiter = "\n"
    
    def set_logger(self, logger):
        self.logger = logger[0]

    def connectionMade(self):
        logging.info("IntraFace - Connected to Server")
        
    def lineReceived(self, line):
        if not line: return  
        line_as_tuple = ast.literal_eval(line)
        
        if len(line_as_tuple) != 130:
            return

        intraface_sample = InrafaceSample(*line_as_tuple)
        self.logger.write_tuple_to_log_file(intraface_sample)
        
        head_pitch_rotated = -intraface_sample.head_rotation_pitch+intraface_sample.head_rotation_pitch/np.absolute(intraface_sample.head_rotation_pitch)*180
        self.factory.send_data_for_processing("facial_features",[intraface_sample.neutral, head_pitch_rotated], intraface_sample.timestamp/1000.0)

class IntraFaceClientFactory(ReconnectingClientFactory):
    
    def __init__(self):
        self.processing_proxy = None
    
    def set_proxy(self, proxy):
        self.processing_proxy = proxy

    def send_data_for_processing(self, type, value, timestamp):
        if self.processing_proxy is not None:
            data = {"type":type, "value": value, "timestamp": timestamp}
            self.processing_proxy.notifyAll(data)
            
    def run_server(self):
        subprocess.Popen([base_path + "/Intraface/demo SERVER CAM2"], shell=True)
    def run_recorder(self):
        subprocess.Popen(["python " + base_path + "/VideoRecorder.py"], shell=True)
        
    def set_data_logger(self, logger):
        logging.debug( "IntraFace - Setting intraface logger" )
        self.logger = logger
        
    def update_data_logger(self, logger):
        self.logger = logger
        if hasattr(self, "current_instance"):
            self.current_instance.set_logger(logger)
    
    def buildProtocol(self, addr):
        self.resetDelay()
        
        protocol = IntraFaceServerProtocol()
        protocol.factory = self
        protocol.set_logger(self.logger)
        
        self.current_instance = protocol
        
        logging.debug( "IntraFace - Protocol built for Intraface client" )
        return protocol
    
    def clientConnectionLost(self, connector, reason):
        logging.error( 'IntraFace - IntrafaceClient Lost connection.  Reason: %s' % (reason) )
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        logging.error( 'IntraFace - IntrafaceClient Connection failed.  Reason: %s' % (reason) )
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

