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
zegra-server with automatization features for dealing with MyRenault and MyDacia
vehicles
"""

### IMPORT ###

from zegra_server import *
from .logger cimport logger

# Import misc
from datetime import datetime

# Import asyncio
from types import NoneType
import asyncio
import aiohttp

# Import renault_api
from renault_api.renault_client import RenaultClient
from renault_api.exceptions import *
from renault_api.kamereon.exceptions import *

### FUNCTIONS ###

async def _main():
   """
   Create an asyncio task for each vehicle in the JSON config file to monitor
   battery status.

   Also create an asyncio task for listening for HTTP requests to start HVAC for
   a specific vehicle in the JSON config file.

   Optional arguments are also available, with them printing help or vesion,
   turn on debug logging, use a custom JSON config file and a custom port for
   the HTTP HVAC listener
   """

   # asyncio coroutines to gather
   tasks = []

   # Initiate monitoring of the vehicles and listening for HVAC HTTP requests
   while True:
      try:
         async with aiohttp.ClientSession() as websession:
            # Connect to RenaultAPI with credentials
            client = RenaultClient(websession=websession, locale=config_dict['locale'])
            await client.session.login(config_dict['renault_auth']['email'], config_dict['renault_auth']['password'])

            # Get the Kamereon account_id object
            account_person_data = await client.get_person()
            account_id          = account_person_data.accounts[0].accountId
            #TODO:FIXME: Implement accounts for both MyDacia and MyRenault instead of whatever comes first

            # Get the Kameron account object
            account = await client.get_api_account(account_id)

            # Get vehicles Kamereon object
            vehicles = await account.get_vehicles()

            # Check if there are any errors in vehicles object
            if str(vehicles.errors) != 'None':
               # wait a minute before re-logging
               logger.debug("Got vehicle error:\n%s", vehicles.errors)
               await asyncio.sleep(60)

               # clear up variables
               del client
               del account_person_data
               del account_id
               del account
               del vehicles

               continue

            ## Verify if VINs from JSON config file are valid
            renault_vins = [] # Will store VINs fetched from RenaultAPI

            # Get and store each VIN from the current account into renault_vins
            for vehicle_link in vehicles.raw_data['vehicleLinks']:
               renault_vins.append(vehicle_link['vin'])

            # Check each VIN and point out all invalid VINs
            invalid_vin = False # If True, at least one of the VINs from the JSON config file is invalid
            for vehicle in config_dict['Cars']:
               if config_dict['Cars'][vehicle]['VIN'] not in renault_vins:
                  logger.error("[main] `%s` is missing in the Renault/Dacia account!", config_dict['Cars'][vehicle]['VIN'])
                  invalid_vin = True # Set error and continue logging eventual invalid VINs
            if invalid_vin:
               sys.exit(1)


            # Create an asyncio coroutine task for each car entry
            for vehicle_entry in config_dict['Cars']:
                task = asyncio.create_task(create_vehicle(account, config_dict['Cars'][vehicle_entry], vehicle_entry))
                tasks.append(task)

            # Create an asyncio coroutine task for the HTTP HVAC listener
            task = asyncio.create_task(http_hvac_listener(account, config_dict, port))
            tasks.append(task)

            # Wait for all coroutines to complete
            await asyncio.gather(*tasks)

      # Connection errors
      except (aiohttp.ClientConnectionError,
              aiohttp.ClientResponseError,
              aiohttp.ClientPayloadError,
              aiohttp.ClientError,
              asyncio.TimeoutError,
              FailedForwardException,
              QuotaLimitException) as e:


         logger.warning("Got exception: %s", e)

         # Cancel ongoing asyncio tasks
         for task in tasks:
            task.cancel()

         # Wait for all asyncio tasks to finish
         try:
            await asyncio.gather(*tasks, return_exceptions=True)

         # Handle asyncio.CancelledError to ensure it doesn't propagate to the outer exception handler
         except asyncio.CancelledError:
            pass

         # Wait before re-logging
         if type(e) is QuotaLimitException:
            # if quoata limit exhaustion, wait more than normal connection errors
            await asyncio.sleep(300) # 5 minutes
         else:
            # Normal connection errors
            await asyncio.sleep(60) # 1 minute

         continue

      except Exception as e:
         logger.error("[SERVER SHUTDOWN] An unexpected error occurred: %s", e)

         # Send an urgent NTFY to admin
         title    = "[SERVER SHUTDOWN] Unexpected error - SHUTTING DOWN"
         message  = ("[SERVER SHUTDOWN] An unexpected error occurred\n"
                     "\n"
                     "**********************\n"
                     "{}\n"
                     "**********************\n"
                     "\n"
                     "[{}] Shutting down the server!").format(str(e), datetime.today().strftime('%Y/%m/%d  - %H:%M:%S'))
         emoji    = "computer"
         priority = "urgent"
         await send_ntfy_notification(admin_ntfy_uri,
                                      admin_ntfy_username,
                                      admin_ntfy_password,
                                      title,
                                      message,
                                      emoji,
                                      priority)

         # Cancel ongoing tasks
         for task in tasks:
            task.cancel()

         # Wait for tasks to be cancelled
         await asyncio.gather(*tasks)

         # Shut down the server ungracefully
         sys.exit(1)
