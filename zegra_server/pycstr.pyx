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

from libc.stdlib cimport malloc, free
from libc.string cimport strcpy

cdef char* py_str_to_c_str(str py_str):
    cdef char* c_str
    cdef int length

    length = len(py_str) + 1  # +1 for null terminator
    c_str = <char*> malloc(length)
    if c_str == NULL:
        raise MemoryError("Unable to allocate memory for C string.")

    strcpy(c_str, py_str.encode('utf-8'))
    return c_str

cdef void free_c_str(char* c_str):
    if c_str != NULL:
        free(c_str)
