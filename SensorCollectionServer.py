# © 2017, 2018 published Massachusetts Institute of Technology.
import argparse
import os
import subprocess
import logging
import json 
import sys
import datetime
from twisted.internet import reactor
from twisted.internet.serialport import SerialPort
from twisted.internet import stdio
from twisted.internet.protocol import ReconnectingClientFactory, Protocol
from twisted.web.static import File
from twisted.web.server import Site
from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory
from Logger import LoggersContainer, DataLogger, LoggingUserControl, LoggingWebsocketControlFactory
from E4BLEClient import E4ClientFactory
from BioharnessClient import BioharnessProtocol
from E4Commands import StreamMessagesDecoder
from IntraFaceClient import InrafaceSample, IntraFaceClientFactory

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
elif __file__:
    application_path = os.path.dirname(__file__)
    
base_path = application_path
CONFIG_FILE_PATH = os.path.join(base_path, 'main.conf')
UI_PATH = os.path.join(base_path, 'webfiles/ui')

def parse_commandline_arguments():
    parser = argparse.ArgumentParser(description='Sensor Collection Server')
    parser.add_argument("-o", dest="output_file_prefix", default="UNNAMED",
                        help="A prefix for the output files generated")
    return parser.parse_args()


class SensorProxyProtocol(WebSocketServerProtocol):
    def onConnect(self, request):
        self.peer = request.peer
        logging.info("Proxy - Received Connection from {}".format(request.peer))

    def onOpen(self):
        logging.info("Proxy - Connection open.")
        self.factory.client_list.append(self)
        
    def onMessage(self, payload, isBinary):
        logging.debug("Proxy - Received - %s" % (payload))
            
    def onClose(self, wasClean, code, reason):
        logging.info("Proxy - Connection closed: {0}".format(reason))
        if self in self.factory.client_list:
            self.factory.client_list.remove(self)

class SensorProxyFactory(WebSocketServerFactory):
    def __init__(self, url):
        WebSocketServerFactory.__init__(self, url)
        logging.info("Proxy - Real-time processing proxy server started")
        self.client_list = []
          
    def buildProtocol(self, addr):
        proto = SensorProxyProtocol()
        proto.factory = self
        return proto

    def notifyAll(self, data_obj):
        data = json.dumps(data_obj, ensure_ascii = False).encode('utf8')
        for cli in self.client_list:
            #logging.debug("Proxy - Send Data to %s - %s" % (cli.peer, data))
            cli.sendMessage(data)

        
def main(command_args, start_logging = False):
    # Setup logging
    #
    #
    current_time = datetime.datetime.now().strftime("%Y%m%d_%I%M%S")
    logfilename = "log/SenCol_log_"+current_time+".log"
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M')

    # load configuration
    #
    #
    try:
        configfile = open(CONFIG_FILE_PATH, "rb")
        config = json.load(configfile)
        configfile.close()
    except Exception as e:
        logging.critical("SensorCollectionServer - Failed to load configuration: %s" % str(e))
        sys.exit(1)
    
    # Edit here what sensors are used
    use_E4_L = "e4l" in config and config["e4l"]["active"]
    use_E4_R = "e4r" in config and config["e4r"]["active"]
    use_Bioharness = "bioharness" in config and config["bioharness"]["active"]
    use_Intraface = "intraface" in config and config["intraface"]["active"]
    use_video_recorder = "recordvideo" in config and config["recordvideo"]["active"]
    use_Muse = "muse" in config and config["muse"]["active"]
    use_Openface = "openface" in config and config["openface"]["active"]
    # Edit here whether to use real-time processing
    use_real_time_processing = "processing" in config
    use_stereo_recorder = "stereovideo" in config and config["stereovideo"]["active"]
    use_optris_ir_camera = "optris" in config and config["optris"]["active"]
    
    # Edit here E4 Server information 
    E4_SERVER_IP = "" 
    E4_SERVER_PORT = 
    
    # Edit here Intraface Server information 
    INTRAFACE_SERVER_IP = ""
    INTRAFACE_SERVER_PORT = 
    
    # Edit here port of the websocket for logging command
    LOGGING_WEB_CONTROL_PORT = 
    
    # Edit here the pather where the collected data is store
    DATA_BASE_PATH = os.path.join(base_path, config["database"]["path"])

    # Setting up data loggers (Note that these are not associated with a client yet)
    loggers_container = LoggersContainer(base_path, DATA_BASE_PATH, lock = not start_logging)
    setter_logger_pairs = []

    # Setup real-time processing
    real_time_processing_proxy_factory = None
    if use_real_time_processing:
        # Edit here the port for signal processing server
        PROCESSING_SERVER_IP = ""
        PROCESSING_SERVER_PORT = config["processing"]["port"]
        real_time_processing_proxy_factory = SensorProxyFactory(u"" % PROCESSING_SERVER_PORT)
        reactor.listenTCP(PROCESSING_SERVER_PORT, real_time_processing_proxy_factory)

    # Setup E4
    if use_E4_L or use_E4_R:
        # Setting up the E4 stream decoder
        E4_stream_decoder = StreamMessagesDecoder()
    
        if use_E4_R:
            # Initializing one E4 for the Right Hand 
            client_factory_R = E4ClientFactory()
            client_factory_R.set_client_id("R")
            client_factory_R.set_stream_decoder(E4_stream_decoder)
            # Connecting to the E4 Right Hand
            E4_client_R = reactor.connectTCP(E4_SERVER_IP, E4_SERVER_PORT , client_factory_R)
            # Add logger
            setter_logger_pairs.append((client_factory_R.update_data_loggers,"E4_loggers_R",lambda: loggers_container.add_E4("E4_loggers_R", "R", E4_stream_decoder)))

        if use_E4_L:
            # Initializing one E4 for the Left Hand 
            client_factory_L = E4ClientFactory()
            client_factory_L.set_client_id("L")
            client_factory_L.set_stream_decoder(E4_stream_decoder)
            # Connecting to the E4 Left Hand
            E4_client_L = reactor.connectTCP(E4_SERVER_IP, E4_SERVER_PORT , client_factory_L)  
            # Add logger
            setter_logger_pairs.append((client_factory_L.update_data_loggers,"E4_loggers_L", ["L", E4_stream_decoder]))

    # Setup Bioharness
    if use_Bioharness:
        # Edit here Bioharness Bluetooth port information 
        # pair device with you computer, code 1234
        # ls /dev/cu.* find out with port it is connected to
        BIOHARNESS_COM_PORT = config["bioharness"]["port"]
        # Initializing the Bioharness
        bioharness_protocol = BioharnessProtocol(BIOHARNESS_COM_PORT, reactor)
        bioharness_protocol.set_event_callbacks() # Note: that would be the default callback, writing the sample to the appropriate logger
        bioharness_protocol.set_waveform_callbacks() # Note: that would be the default callback, writing the sample to the appropriate logger
        bioharness_protocol.set_proxy(real_time_processing_proxy_factory)
        # Add logger
        setter_logger_pairs.append((bioharness_protocol.set_data_loggers,"bioharness_loggers", None))
        # Connecting to the Bioharness
        bioharness_protocol.reconnect()

    # Setup Intraface (depreciated)
    if use_Intraface:   
        # Initializing the Intraface
        intraface_factory = IntraFaceClientFactory()
        intraface_factory.set_proxy(real_time_processing_proxy_factory)
        # Add logger
        setter_logger_pairs.append((intraface_factory.update_data_logger,"intraface_logger", None))
        # Connecting to the Intraface Server
        intraface_factory.run_server()
        intraface_cliet = reactor.connectTCP(INTRAFACE_SERVER_IP, INTRAFACE_SERVER_PORT, intraface_factory)
    
    # Setup Openface Recorder
    elif use_Openface:
        loggers_container.set_openface_recorder(True, config["openface"]["video_device_id"])

    # Setup Video Recorder
    elif use_video_recorder:
        loggers_container.set_record_video(True,config["recordvideo"]["extension"], config["recordvideo"]["format"], config["recordvideo"]["codec"], config["recordvideo"]["loglevel"], config["recordvideo"]["camera"], config["recordvideo"]["mic"], config["recordvideo"]["video_size"], config["recordvideo"]["pixel_format"], config["recordvideo"]["framerate"])
    
    # Setup Muse
    if use_Muse:
        eeg_path = os.path.abspath(os.path.join(os.path.dirname(base_path), '..', 'Documents', 'EEGAnalysis'))
        subprocess.Popen(["python3 " + eeg_path + "/__init__.py "], shell=True) 
    
    # Setup Stereo video recording
    if use_stereo_recorder:
        loggers_container.set_stereo_video(True, config["stereovideo"]["camera"])
    
    # Setup Optris Camera
    if use_optris_ir_camera:
        loggers_container.set_optris_recorder(True)

    # Start logger
    loggers_container.set_setter_logger_pairs(setter_logger_pairs)
    loggers_container.new_logging_session(command_args.output_file_prefix)

    # Initializing the LoggingUserControl (Controlling logging from the terminal)
    user_control_protocol = LoggingUserControl()
    user_control_protocol.set_logger_container(loggers_container)
    stdio.StandardIO(user_control_protocol)
    
    # Initializing the LoggingWebsocketControl (Controllign logging from the a Webserver for computerized tests)
    factory = LoggingWebsocketControlFactory(u"ws://127.0.0.1:%s" % LOGGING_WEB_CONTROL_PORT)
    factory.logger_container = loggers_container
    reactor.listenTCP(LOGGING_WEB_CONTROL_PORT, factory)

    # HTTP server
    #
    #
    HTTP_port = 
    root = File(UI_PATH)
    HTTP_factory = Site(root)
    logging.debug("SensorCollectionServer - Starting HTTP Server on port %i" % HTTP_port)
    reactor.listenTCP(HTTP_port, HTTP_factory)
    

    try:
        logging.debug("SensorCollectionServer - Reactor running")
        reactor.run()
    
    except Exception as e:
        Logging.error(e)
        loggers_container.close_logging_session()
    
if __name__ == '__main__':
    command_args = parse_commandline_arguments()
    main(command_args)
