# © 2017, 2018 published Massachusetts Institute of Technology.
# TODO: handle a problem with the fact that REASON has spaces in it 

class E4CommandExeption(Exception):pass

class E4Command(object):
    def __init__(self, command_format, response_format):
        self.set_command_format(command_format)
        self.set_response_format(response_format)
        
    def set_command_format(self, command_format):
        self.command = command_format.split(" ")[0]
        
        self.arguments = []
        arguments = command_format.split(" ")[1:]
        for argument in arguments:
            if (argument[0]=="<" and argument[-1]==">"):
                self.arguments.append(argument[1:-1])
            else:
                raise E4CommandExeption("Command initiated with invalid argument format")

    def set_response_format(self, response_format):
        self.response_command = response_format.split(" ")[1]

        self.res_items = []
        res_items = response_format.split(" ")[2:]
        for item in res_items:
            if (item[0]=="<" and item[-1]==">"):
                self.res_items.append(item[1:-1])
            else:
                raise E4CommandExeption("Command initiated with invalid response format")
        
            
    def encode_arguments(self, **kw):
        return " ".join([self.command] + [kw[key] for key in self.arguments]) + "\r\n"
    
    def decode_response(self, response_string):
        if response_string.split(" ")[0] != "R":
            raise E4CommandExeption("Received a command response that does not begin with R: %s" % response_string)
        
        if response_string.split(" ")[1] != self.response_command:
            raise E4CommandExeption("Received a command response that does not match the sent command: %s" % response_string)
            
        response = {key:item for key, item in zip(self.res_items,response_string.split(" ")[2:])}
        # Note: Zip will return a list with a length of the shortest list ignoring excess items. In our case it will ignore REASON if it does not exist. 
        
        if response["RC"] == "ERR":
            raise E4CommandExeption("Server returned error for command %s with reason %s" % (self.command,response["REASON"]))
        
        return response
    
class E4DeviceListCommand(E4Command):
    def decode_response(self, response_string):
        response_header = response_string.split("|")[0]
        devices_strings = response_string.split("|")[1:]
        
        if response_header.split(" ")[0] != "R":
            raise E4CommandExeption("Received a command response that does not begin with R: %s" % response_string)
        
        if response_header.split(" ")[1] != self.command:
            raise E4CommandExeption("Received a command response that does not match the sent command: %s" % response_string)
        
        if int(response_header.split(" ")[2]) != (len(devices_strings)):
            raise E4CommandExeption("Received device_list command response with inconsistent number of devices: %s" % response_string)
        
        devices = []
        for device_string in devices_strings:
            device_items = [item for item in device_string.split(" ") if item != '']
            device =  {key:item for key, item in zip(self.res_items,device_items)}
            devices.append(device)
            
        return devices


class DataStreamException(Exception): pass
class DataStream(object):
    def __init__(self, stream_format):
        self.set_stream_format(stream_format)
        
    def set_stream_format(self, stream_format):
        self.stream_type = stream_format.split(" ")[0]

        self.values = []
        stream_values = stream_format.split(" ")[1:]
        for value in stream_values:
            if (value[0]=="<" and value[-1]==">"):
                self.values.append(value[1:-1])
            else:
                raise DataStreamException("Stream initiated with invalid parameter format")
    
    def decode_stream_message(self, stream_message):
        if stream_message.split(" ")[0] != self.stream_type:
            raise DataStreamException("Attempting to decode stream message with the wrong decoder: stream type %s, decoder %s" % (stream_message.split(" ")[0], self.stream_type))
                
        formatted_message_type = self.stream_type[3:].lower()
        if formatted_message_type == "temperature": formatted_message_type = "tmp"

                    
        message_values = (item for key, item in zip(self.values, stream_message.split(" ")[1:]))
                
        return (formatted_message_type, message_values)
    
    
class StreamMessagesDecoder(object):
    def __init__(self):
        self.open_streams = {
                             "hr":  DataStream("E4_Hr <TIMESTAMP> <HR>"),
                             "tag": DataStream("E4_Tag <TIMESTAMP> <X> <Y> <Z>"),
                             }
        
        self.possible_streams = {
                                 "acc": DataStream("E4_Acc <TIMESTAMP> <X> <Y> <Z>"), 
                                 "bvp": DataStream("E4_Bvp <TIMESTAMP> <BVP>"),
                                 "gsr": DataStream("E4_Gsr <TIMESTAMP> <GSR>"),
                                 "tmp": DataStream("E4_Temperature <TIMESTAMP> <TEMP>"),
                                 "ibi": DataStream("E4_Ibi <TIMESTAMP> <IBI>"),
                                 "hr":  DataStream("E4_Hr <TIMESTAMP> <HR>"),
                                 "bat": DataStream("E4_Battery <TIMESTAMP> <LEVEL>"),
                                 "tag": DataStream("E4_Tag <TIMESTAMP>"),                            
                                 }
        
    def subscribe_to_stream(self, stream_type):
        self.open_streams[stream_type] = self.possible_streams[stream_type]
    
    def unsunscribe_from_stream(self, stream_type):
        del self.open_streams[stream_type] 
    
    def decode_message_by_stream_prefix(self, message_string):
        message_type = message_string.split(" ")[0] 
        if message_type == "R":
            return None, None
        
        if not message_type.startswith("E4_"):
            raise DataStreamException("Received message with unknown stream type")
        
        message_type = message_type[3:].lower()
        
        # This is a hack to handle the inconsistent responses from the server
        if message_type == "temperature": message_type = "tmp"
                
        if message_type not in self.open_streams.keys():
            #return None, None
            raise DataStreamException("Received a data stream message that though server is not subscribed to such stream: %s, string : %s" % (message_type, message_string))
        
        return self.open_streams[message_type].decode_stream_message(message_string)
    
          
# These are all possible commands
COMMAND_server_status = E4Command("server_status", "R system_status <RC> <REASON>")     
COMMAND_device_connect = E4Command("device_connect <DEVICE_ID>", "R device_connect <RC> <REASON>")         
COMMAND_device_disconnect = E4Command("device_disconnect", "R device_disconnect <RC> <REASON>")         
COMMAND_device_subscribe = E4Command("device_subscribe <STREAM> <STATE>", "R device_subscribe <STREAM> <RC> <REASON>")
COMMAND_pause = E4Command("pause <STATE>", "R pause <RC> <REASON>")
COMMAND_device_list = E4DeviceListCommand("device_list", "R device_list <DEVICE_ID> <DEVICE_NAME> <DEVICE_NAME_2> <AVAILABILITY>")
                 
