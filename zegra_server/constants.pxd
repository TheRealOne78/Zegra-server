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

"""Constants"""

cdef char* C_PROJECT_NAME

# Version string
cdef char* C_VERSION_STRING

# Project author name
cdef char* C_PROJECT_AUTHOR_NAME

# Project author E-Mail
cdef char* C_PROJECT_AUTHOR_EMAIL

# Default JSON config file path
cdef char* C_CONFIG_FILE_PATH

# Default HVAC HTTP listener port
cdef int C_HVAC_HTTP_LISTENER_PORT

# Default NTFY priority
cdef char* C_NTFY_DEFAULT_PRIORITY

# Log file path
cdef char* C_WINDOWS_LOG_FILE_PATH
cdef char* C_UNIX_LOG_FILE_PATH
