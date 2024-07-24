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
Logger
"""

from .constants cimport C_WINDOWS_LOG_FILE_PATH, C_UNIX_LOG_FILE_PATH
from fastlogging import LogInit, Logger
from fastlogging import EXCEPTION, FATAL, CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET
from datetime import datetime
import os

cdef str log_file_path
cdef str encoding
cdef str log_format
cdef str date_format
cdef int log_level
cdef bint console
cdef bint colors
cdef bint console_lock

cdef object logger

cdef void log_init(str log_file_path = None,
                   str encoding      = 'utf-8',
                   str log_format    = '[%(asctime)s] [%(levelname).1s] %(name)s: %(message)s',
                   str date_format   = '%Y-%m-%d %H:%M:%S',
                   int log_level     = INFO,
                   bint console      = True,
                   bint colors       = True):
                   #bint console_lock = False): # NOTE: commented due to a bug from fastlogging
    """
    Initialize the logger.

    :param log_file_path: Path for log file.
    :type log_file_path: str
    :param encoding: Encoding stream
    :type encoding: str
    :param log_format: Log format
    :type log_format: str
    :param date_format: Date format
    :type date_format: str
    :param log_level: Logging level
    :type log_level: int
    """

    # Extern logger
    global logger

    try:
        # Set default log file path based on the operating system
        if log_file_path is None:
            log_file_path = C_WINDOWS_LOG_FILE_PATH.decode('utf-8') if os.name == 'nt' else C_UNIX_LOG_FILE_PATH.decode('utf-8')

        # Initialize logger
        logger = LogInit(pathName=log_file_path, console=console, colors=colors, level=log_level)

        logger.debug("Initialized logger.")

    except Exception as e:
        print("[%s] ERROR: Couldn't initialize the logger: %s", datetime.today().strftime(date_format), str(e))
