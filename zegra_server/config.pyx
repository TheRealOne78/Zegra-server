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
import json
import yaml
import os

cdef dict init_config(str config_file_path = C_CONFIG_FILE_PATH.decode('utf-8')):
    """
    Read JSON/YAML config file and return it as a dictionary.

    :param config_file_path: config_file_path Contains the config file path.
    :type config_file_path: str
    :return: Populated config dictionary.
    :rtype: dict
    """

    cdef dict config_dict

    # Determine the file extension
    cdef str ext
    _, ext = os.path.splitext(config_file_path)

    with open(config_file_path, 'r', encoding="utf8") as config_file:
        if ext.lower() == '.json':
            config_dict = json.load(config_file)
        elif ext.lower() == '.yaml' or ext.lower() == '.yml':
            config_dict = yaml.safe_load(config_file)
        else:
            raise ValueError("Unsupported file extension: {}".format(ext))

    return config_dict
