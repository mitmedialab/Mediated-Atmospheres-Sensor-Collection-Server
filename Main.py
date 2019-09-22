# © 2017, 2018 published Massachusetts Institute of Technology.
import argparse
import os
from SensorCollectionServer import main, parse_commandline_arguments
 
if __name__ == '__main__':

    command_args = parse_commandline_arguments()
    main(command_args)
