# © 2017, 2018 published Massachusetts Institute of Technology.
import os
import datetime
import json
import logging
import shlex, subprocess
from twisted.protocols import basic
from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory
from BioharnessClient import BioharnessProtocol
from IntraFaceClient import InrafaceSample
import sys 

###
# Logger Container
# contains all loggers of all active sensor streams
# it provides function for each sensor stream to add an DataLogger
# it provides a function for all loggers to turn on/off and start anew  
class LoggersContainer(object):

	def __init__(self, base_path, data_base_path, lock):
		self.base_path = base_path
		self.data_base_path = data_base_path
		self.output_file_prefix = ""

		self.loggers = {}
		self.is_write_locked = lock
		self.in_session = False
		
		self.openface_p = None
		self.video_device_id = 0
		self.activate_openface = False

		self.video_p = None
		self.record_video = False


	def create_directory_if_does_not_exist(self, folder_path):
		if os.path.exists(folder_path): return
		os.makedirs(folder_path)

	def set_record_video(self, record_video, extension, video_format, codec, loglevel, video_device, audio_device, video_size,  pixel_format, framerate):
		self.record_video = record_video
		self.video_format = video_format
		self.video_device = video_device
		self.audio_device = audio_device
		self.video_codec = codec
		self.video_size = video_size
		self.framerate = framerate
		self.video_loglevel = loglevel
		self.video_pixel_format = pixel_format
		self.video_extension = extension


	def set_openface_recorder(self, activate_openface, device_id):
		self.activate_openface = activate_openface
		self.video_device_id = device_id

	def set_setter_logger_pairs(self, setter_logger_pairs):
		# setter_logger_pair is a tuple (<logger_setting_funtion>, <logger_name>, <logger_update_function_args>)
		self.setter_logger_pairs = setter_logger_pairs
			
	def new_logging_session(self, output_file_prefix):
		# lock log
		if not self.is_write_locked:
			self.lock_writing_to_log_file()

		# close ongoing session 
		if self.in_session:
			self.close_logging_session()

		# Create new folder 
		current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
		self.output_file_prefix = output_file_prefix + "_" + current_time
		self.create_directory_if_does_not_exist(os.path.join(self.data_base_path, self.output_file_prefix))

		# Create loggers for each stream
		for setter, logger, args in self.setter_logger_pairs:
			dispatcher = {"E4_loggers_R": self.create_loggers_for_E4_client,
						  "E4_loggers_L": self.create_loggers_for_E4_client,
						  "bioharness_loggers": self.create_loggers_for_bioharness,
						  "intraface_logger": self.create_logger_for_intraface
						  }
			self.loggers[logger] = dispatcher[logger](args)
			setter(self.loggers[logger])
		self.in_session = True
		
	def close_logging_session(self):
		for loggers in self.loggers:
			self.close_loggers(self.loggers[loggers])
		self.in_session = False

	def create_loggers_for_E4_client(self, args):
		E4_loggers = {}
		client_id, stream_decoder = args
		for stream_type in self.E4_stream_decoder.possible_streams.keys():
			file_prefix = "E4_%s_%s_%s" % (client_id, stream_type, self.output_file_prefix)
			stream_columns =  self.E4_stream_decoder.possible_streams[stream_type].values
			E4_loggers[stream_type] = DataLogger(os.path.join(self.data_base_path, self.output_file_prefix), file_prefix, 
												 stream_columns, self)
		return E4_loggers

	def create_loggers_for_bioharness(self, args=None):
		bioharness_loggers = {}
		for stream_type in BioharnessProtocol.columns_of_streams.keys():
			file_prefix = "BIO_%s_%s" % (stream_type, self.output_file_prefix)
			stream_columns = BioharnessProtocol.columns_of_streams[stream_type]
			bioharness_loggers[stream_type] = DataLogger(os.path.join(self.data_base_path, self.output_file_prefix), file_prefix, 
														 stream_columns, self)
		return bioharness_loggers

	def create_logger_for_intraface(self, args=None):
		intraface_loggers = {}
		file_prefix = "INTRA_%s" % (self.output_file_prefix)
		intraface_columns = InrafaceSample._fields
		intraface_loggers[0] = DataLogger(os.path.join(self.data_base_path, self.output_file_prefix), file_prefix,
										   intraface_columns, self) 
		return intraface_loggers

	def create_video_recorder(self):
		self.stop_video_recorder()
		current_time = datetime.datetime.now().strftime("%H%M%S")
		file_prefix = "VIDEO_%s_%s" % (current_time, self.output_file_prefix)
		file_path = os.path.join(self.data_base_path, self.output_file_prefix, file_prefix)
		command = 'ffmpeg -loglevel %s -f %s -framerate %s -video_size %s -rtbufsize 702000k \
			-i video="%s":audio="%s" -c:v %s -b:v 4M -b:a 192k %s.%s' % \
			(self.video_loglevel, self.video_format, self.framerate, self.video_size, \
			self.video_device, self.audio_device, self.video_codec, file_path, self.video_extension)
		if sys.platform == 'win32':
			args = command
		else:
			args = shlex.split(command)
		self.video_p = subprocess.Popen(args, stdin = subprocess.PIPE, creationflags=subprocess.CREATE_NEW_CONSOLE)

	def create_openface_recorder(self):
		self.stop_openface_recorder()
		folder_prefix = "OPENFACE_%s" % self.output_file_prefix
		folder_path = os.path.join(self.data_base_path, self.output_file_prefix, folder_prefix)
		openface_path = os.path.join(self.base_path, "openface", "FeatureExtraction")
		command = '%s -device %i -out_dir %s' % (openface_path, self.video_device_id, folder_path)
		if sys.platform == 'win32':
			args = command
		else:
			args = shlex.split(command)
		self.openface_p = subprocess.Popen(args, stdin = subprocess.PIPE, creationflags=subprocess.CREATE_NEW_CONSOLE)

		

	def stop_openface_recorder(self):
		if self.openface_p is not None:
			self.openface_p.terminate()
			self.openface_p = None

	def close_loggers(self, loggers):
		for logger in loggers.values():
			logger.close_log_file()

	def unlock_writing_to_log_file(self):
		if self.record_video:
			self.create_video_recorder()
		if self.activate_openface:
			self.create_openface_recorder()
		self.is_write_locked = False

	def lock_writing_to_log_file(self):
		self.stop_video_recorder()
		self.stop_openface_recorder()
		self.is_write_locked = True

###
# Logging Websockt Control
# enables web controll of all loggers in the Logger Container  
class LoggingWebsocketControll(WebSocketServerProtocol):

	def onConnect(self, request):
		logging.debug("LoggingWebsocketControll: Received Contol Connection")

	def onOpen(self):
		logging.debug("LoggingWebsocketControll: WebSocket connection open.")

	def onMessage(self, payload, isBinary):
		logging.debug("LoggingWebsocketControll: Received Command - %s" % (payload))
		command = json.loads(payload)
		self.handle_command(command)
			
	def onClose(self, wasClean, code, reason):
		logging.debug("LoggingWebsocketControll: WebSocket connection closed: {0}".format(reason))
		#self.logger_container.lock_writing_to_log_file()

	def handle_command(self, command):
		dispatcher = {"LOG": self.handle_log_command,
					  "STOP_LOG": self.handle_stop_log_command}
		dispatcher[command["type"]](command)

	def handle_stop_log_command(self,command):
		self.logger_container.lock_writing_to_log_file()
		
	def handle_log_command(self, command): 
		log_files_prefix = "%s_%s" % (command["subject"],command["name"])
		self.logger_container.lock_writing_to_log_file()
		self.logger_container.new_logging_session(log_files_prefix)
		self.logger_container.unlock_writing_to_log_file()

		
	def set_logger_container(self, logger_container):
		self.logger_container = logger_container
	
  
class LoggingWebsocketControlFactory(WebSocketServerFactory):
		def buildProtocol(self, addr):
			proto = LoggingWebsocketControll()
			proto.set_logger_container(self.logger_container) # This part will be set externally by the user.
			proto.factory = self
			return proto

###
# Logging User Control
# enables command line control of all loggers in the Logger Container  
class LoggingUserControl(basic.LineReceiver):
	# This part sets the delimiter to be the one of the OS in which the server is running.
	#from os import linesep as delimiter
	delimiter =  b'\n'

	def connectionMade(self):
		self.transport.write("LoggingConsolControl: Initializing Logging to OFF - Send ON to start Logging \n".encode("utf-8"))
		
	def set_logger_container(self, container):
		self.container = container

	def lineReceived(self, line):
		self.transport.write("LoggingConsolControl: Received user request - ".encode("utf-8") + line + b'\n')
		if "ON" in line.decode(): 
			self.container.unlock_writing_to_log_file()
			self.transport.write("LoggingConsolControl: Logging enabled \n".encode("utf-8"))
		if "OFF" in line.decode(): 
			self.container.lock_writing_to_log_file()
			self.transport.write("LoggingConsolControl: Logging disabled \n".encode("utf-8"))   
		   

###
# Data Logger
# is a gerenal class that facilitates data logging of tuples
# it is created, locked, and unlocked by Logger Container
# it is used by the associated data stream
class DataLogger(object):
	def __init__(self, base_path, file_name, columns_list, container):
		self.path = os.path.join(base_path, file_name)
		self.log_file = open(self.path, "a+")
		self.log_file.write(",".join(columns_list))
		self.log_file.write("\r\n")
		logging.debug("Logging incoming data into %s " % self.path)     
		self.columns_list = columns_list
		self.container = container
				
		
	def write_tuple_to_log_file(self, values_in_tuple, show_on_screen=False):
		tuple_to_list = [str(value) for value in values_in_tuple]
		self.write_list_to_log_file(tuple_to_list, show_on_screen)
		
	def write_dict_to_log_file(self, values_in_dictionary, show_on_screen=False):
		dict_to_list = [values_in_dictionary[key] for key in self.columns_list]
		self.write_list_to_log_file(dict_to_list, show_on_screen)
		
	def write_list_to_log_file(self, values_in_list, show_on_screen=False):
		if self.container.is_write_locked:
			return
		
		line_to_write = ",".join(values_in_list) + "\r\n"

		self.log_file.write(line_to_write)
		
		if show_on_screen:
			logging.debug(line_to_write)
			
	def write_line(self, line):
		if self.container.is_write_locked:
			return
		self.log_file.write(line + "\r\n") 
	
	def close_log_file(self):
		self.log_file.flush()
		self.log_file.close()


