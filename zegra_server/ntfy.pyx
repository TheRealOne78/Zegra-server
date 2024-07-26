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

from .constants cimport C_NTFY_DEFAULT_PRIORITY
from .logger cimport logger
import aiohttp

async def send_ntfy_notification(uri,
                                 username,
                                 password,
                                 title,
                                 message,
                                 emoji,
                                 priority = C_NTFY_DEFAULT_PRIORITY):
   """
   Send a push notification to a NTFY topic.

   'uri' contains the URI of the NTFY topic (Eg. 'https://ntfy.sh/FooBar')
   'username' and 'password' contain the credentials to access the NTFY topic
   'title' contains the notification title
   'message' contains the notification body message
   'emoji' contains emojies that will appear before the title
   """

   # Send NTFY push asynchronously
   try:
      async with aiohttp.ClientSession() as session:
         auth = aiohttp.BasicAuth(username, password)
         async with session.post(uri,
                                 headers = {
                                    'Title': title,
                                    'Tags': emoji,
                                    'Priority': priority },
                                 data = message,
                                 auth = auth) as response:
            if response.status != 200:
               logger.error("Failed to send NTFY notification - HTTP response status `%s`", response.status)
            else:
               logger.debug("NTFY notification sent successfully")

   except aiohttp.ClientError as e:
      logger.error("An error occurred during the HTTP request: %s", e)
   except Exception as e:
      logger.error("An unexpected error occurred: %s", e)
