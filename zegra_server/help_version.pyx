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
Print help and version on the screen
"""

from .constants import *

cdef void print_help():
   """
   Print a help message
   """

   print('%s\n'
         'A daemon with some basic automatization features for dealing with\n'
         'Renault and Dacia vehicles\n'
         '\n'
         'Usage: %s [options]\n'
         '\n'
         'Options:\n'
         '-h, --help        Output this help list and exit\n'
         '-v, --version     Output version information and license and exit\n'
         '-D, --debug       Output the debug log\n'
         '-c, --config      Set another configuration file than the default\n'
         '                  `%s` configuration file\n'
         '\n'
         '-p, --port        Set HVAC HTTP listener port (0-65535)',
         PROJECT_NAME, sys.argv[0], JSON_CONFIG_FILE_PATH)

cdef void print_version():
   """
   Print version
   """

   print('%s version %s\n'
         '\n'
         'Copyright (C) 2024 TheRealOne78\n'
         'License AGPLv3+: GNU AGPL version 3 or later <https://gnu.org/licenses/agpl.html>.\n'
         'This is free software: you are free to change and redistribute it.\n'
         'There is NO WARRANTY, to the extent permitted by law.',
         PROJECT_NAME, VERSION_STRING)
