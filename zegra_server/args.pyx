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

"""
Argument handling
"""

from .config cimport *
from .help_version cimport *
from .constants cimport HVAC_HTTP_LISTENER_PORT
import sys
import getopt
import logging

# Initialize variables
port        = HVAC_HTTP_LISTENER_PORT # Default this

# Get arguments
opts, args = getopt.getopt(sys.argv[1:], "hvDc:p:", ['help', 'version', 'debug', 'config=', 'port='])
has_arg    = {
   'config_dict': False, # Determine whether or not using the argument config file
   'port': False         # Determine whether or not using the argument HTTP port
}

# Handle options
for opt, arg in opts:
   if opt in   ('-h', '--help'):    # Print a help message and exit gracefully
      print_help()
      sys.exit(0)

   elif opt in ('-v', '--version'): # Print version & licensing and exit gracefully
      print_version()
      sys.exit(0)

   elif opt in ('-D', '--debug'):   # Turn on debug logging
      logging.root.setLevel(logging.DEBUG)
      logging.debug("Turned on debug logging")

   elif opt in ('-c', '--config'):  # Use another config file path than JSON_CONFIG_FILE_PATH
      config_dict            = init_config(arg)
      has_arg['config_dict'] = True

   elif opt in ('-p', '--port'):    # Use another port than the default HVAC_HTTP_LISTENER_PORT or from config file
      port = arg
      has_arg['port'] = True

# Get config from JSON file
if not has_arg['config_dict']:
   config_dict = init_config()

# Enable debugging if it's enabled in the config file
if config_dict['debug']:
   logging.root.setLevel(logging.DEBUG)
   logging.debug("Turned on debug logging")

# Get port from config if available and if not has_arg['config_dict']
if 'http_hvac_listener_port' in config_dict and not has_arg['port']:
   port = config_dict['http_hvac_listener_port']
