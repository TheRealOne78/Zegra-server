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
Logger
"""

from .constants cimport LOG_FILE_PATH
import logging
import os

cdef class Logger:
    cdef str log_file_path
    cdef str encoding
    cdef str log_format
    cdef str date_format
    cdef int log_level

    def __cinit__(self,
                  str log_file_path = LOG_FILE_PATH,
                  str encoding      = 'utf-8',
                  str log_format    = '[%(asctime)s] [%(levelname).1s] %(name)s: %(message)s',
                  str date_format   = '%Y-%m-%d %H:%M:%S',
                  int log_level     = logging.INFO):
        """
        Initialize the logger.
        """

        self.log_file_path = log_file_path
        self.encoding      = encoding
        self.log_format    = log_format
        self.date_format   = date_format
        self.log_level     = log_level

        """
        Set up the logging configuration.
        """
        logging.basicConfig(
            filename = self.log_file_path,
            encoding = self.encoding,
            format   = self.log_format,
            datefmt  = self.date_format,
            level    = self.log_level
        )

        # Create a console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)

        # Create a formatter
        formatter = logging.Formatter(self.log_format,
                                      datefmt = self.date_format)

        # Set formatter for the console handler
        console_handler.setFormatter(formatter)

        # Add the console handler to the root logger
        logging.root.addHandler(console_handler)

        # If log file already exists, rename it to 'log_file_path.old'
        if os.path.isfile(self.log_file_path):
            os.rename(self.log_file_path, self.log_file_path + '.old')
