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

"""
Setup file for zegra-server PyPA packaging
"""

from setuptools import setup, find_packages
from Cython.Build import cythonize

from zegra_server.info import *

setup(
    name        = PROJECT_NAME,
    version     = VERSION_STRING,
    packages    = find_packages(),
    ext_modules = cythonize("zegra_server/*.pyx"),
    entry_points= {
        'console_scripts': [
            'my_script = bin.zegra_server:main',
        ],
    },
)
