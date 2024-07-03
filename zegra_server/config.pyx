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

"""
Read JSON and YAML files
"""

from .constants cimport CONFIG_FILE_PATH
import json
import yaml
import os

cdef dict CONFIG_DICT

cdef init_config(str config_file_path = CONFIG_FILE_PATH):
    """
    Read JSON/YAML config file and return it as a dictionary.

    @param config_file_path Contains the config file path
    """

    global CONFIG_DICT

    # Determine the file extension
    cdef str ext
    _, ext = os.path.splitext(config_file_path)

    with open(config_file_path, 'r', encoding="utf8") as config_file:
        if ext.lower() in ['.json']:
            CONFIG_DICT = json.load(config_file)
        elif ext.lower() in ['.yaml', '.yml']:
            CONFIG_DICT = yaml.safe_load(config_file)
        else:
            raise ValueError("Unsupported file extension: {}".format(ext))
