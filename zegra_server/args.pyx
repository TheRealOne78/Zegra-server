## Copyright_notice ####################################################
#                                                                      #
# SPDX-License-Identifier: AGPL-3.0-or-later                           #
#                                                                      #
# Copyright (C) 2024 TheRealOne78 <bajcsielias78@gmail.com>            #
# This file is part of the Zegra-server project                        #
#                                                                      #
# Zegra-server is free software: you can redistribute it and/or modify #
# it under the terms of the GNU Affero General Public License as       #
# published by the Free Software Foundation, either version 3 of the   #
# License, or (at your option) any later version.                      #
#                                                                      #
# Zegra-server is distributed in the hope that it will be useful,      #
# but WITHOUT ANY WARRANTY; without even the implied warranty of       #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the        #
# GNU Affero General Public License for more details.                  #
#                                                                      #
# You should have received a copy of the GNU Affero General Public     #
# License along with Zegra-server. if not, see                         #
# <http://www.gnu.org/licenses/>.                                      #
#                                                                      #
########################################################################

# cython: language_level=3

"""
Argument handling
"""

from .config cimport *
from .help_version cimport print_help, print_version
from .constants cimport C_HVAC_HTTP_LISTENER_PORT, C_CONFIG_FILE_PATH
from .pycstr cimport py_str_to_c_str
import sys
import getopt
import logging

cdef dict init_args():

    cdef dict args_dict = {
        'port':        C_HVAC_HTTP_LISTENER_PORT,
        'debug':       False,
        'config_path': C_CONFIG_FILE_PATH
    }

    # TODO: remove these
    ## Initialize variables
    #cdef int port = C_HVAC_HTTP_LISTENER_PORT # Default this

    # Get arguments
    cdef list opts
    opts, _ = getopt.getopt(sys.argv[1:], "hvDc:p:", ['help', 'version', 'debug', 'config=', 'port='])
    # TODO: remove these
    #cdef dict has_arg    = {
    #   'config_dict': False, # Determine whether or not using the argument config file
    #   'port': False         # Determine whether or not using the argument HTTP port
    #   }

    # Handle options
    cdef str opt, arg

    cdef char* tmp_c_str

    for opt, arg in opts:
        if opt == '-h' or opt == '--help':
            print_help()
            sys.exit(0)

        elif opt == '-v' or opt == '--version':
            print_version()
            sys.exit(0)

        elif opt == '-D' or opt == '--debug':
            args_dict['debug'] = True
            # TODO: Remove these
            #logging.root.setLevel(logging.DEBUG)
            #logging.debug("Turned on debug logging")

        elif opt == '-c' or opt == '--config':
            tmp_c_str = py_str_to_c_str(arg)

            args_dict['config_path'] = tmp_c_str

        elif opt == '-p' or opt == '--port':
            try:
                args_dict['port'] = int(arg)  # Convert port to an integer
            except ValueError:
                print("Invalid port value: must be an integer")
                sys.exit(1)

    # TODO: move these
    ## Get config from JSON file
    #if not has_arg['config_dict']:
    #   config_dict = init_config()
    #
    ## Enable debugging if it's enabled in the config file
    #if config_dict['debug']:
    #   logging.root.setLevel(logging.DEBUG)
    #   logging.debug("Turned on debug logging")

    ## Get port from config if available and if not has_arg['config_dict']
    #if 'http_hvac_listener_port' in config_dict and not has_arg['port']:
    #    try:
    #        port = int(config_dict['http_hvac_listener_port'])  # Convert config port to an integer
    #    except ValueError:
    #        logging.error("Invalid port value in config: must be an integer")
    #        sys.exit(1)

    return args_dict
