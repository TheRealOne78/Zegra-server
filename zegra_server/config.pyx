## Copyright_notice ####################################################
#                                                                      #
# SPDX-License-Identifier: AGPL-3.0-or-later                           #
#                                                                      #
# Copyright (C) 2024 TheRealOne78 <bajcsielias78@gmail.com>            #
# This file is part of the Zegra-server project                        #
#                                                                      #
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
Read JSON and YAML files
"""

from .constants cimport C_CONFIG_FILE_PATH
import yaml
import os

cdef dict init_config(bytes config_file_path = C_CONFIG_FILE_PATH):
    """
    Read JSON/YAML config file and return it as a dictionary.

    :param config_file_path: config_file_path Contains the config file path.
    :type config_file_path: str
    :return: Populated config dictionary.
    :rtype: dict
    """

    # Determine the file extension
    cdef str ext
    _, ext = os.path.splitext(config_file_path.decode('utf-8'))
    ext = ext.lower()

    # Check file extension
    if ext != '.yaml' and ext != '.yml' and ext != '.json':
        raise ValueError("Unsupported file extension: {}".format(ext))

    cdef dict config_dict = {}

    # Populate config_dict
    with open(config_file_path.decode('utf-8'), 'r', encoding="utf8") as config_file:
        config_dict = yaml.safe_load(config_file)

    return config_dict
