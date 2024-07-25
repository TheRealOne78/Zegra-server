#!/usr/bin/env python

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
Zegra-server with automatization features for dealing with MyRenault and MyDacia
vehicles
"""

from .args cimport init_args
from .config cimport init_config
from .logger cimport log_init
from fastlogging import INFO

cpdef void main():
    print("Hello world!")

    cdef dict args_dict, config_dict

    args_dict = init_args()
    config_dict = init_config(args_dict['config_path'])

    cdef int log_level = INFO
    if args_dict['debug'] or config_dict['debug']:
        from fastlogging import DEBUG
        log_level = DEBUG
        log_init(log_file_path = None,
                 encoding = 'utf-8',
                 log_format = '[%(asctime)s] [%(levelname).1s] %(name)s: %(message)s',
                 date_format = '%Y-%m-%d %H:%M:%S',
                 log_level = log_level)
