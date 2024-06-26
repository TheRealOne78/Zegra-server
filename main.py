#!python3

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
zegra-server with automatization features for dealing with MyRenault and MyDacia
vehicles
"""

### IMPORT ###

# Import misc
import json
import os
import logging
from datetime import datetime
from types import NoneType

# Import arguments
import sys
import getopt

# Import asyncio
import asyncio
import aiohttp
import aiohttp.web

# Import renault_api
from renault_api.renault_client import RenaultClient
from renault_api.exceptions import *
from renault_api.kamereon.exceptions import *


### CONSTANTS ###

# Project name
PROJECT_NAME = "Zegra"

# Version string
VERSION_STRING = "1.0.0"

# Default JSON config file path
JSON_CONFIG_FILE_PATH = './config/config.json'

# Default HVAC HTTP listener port
HVAC_HTTP_LISTENER_PORT = 47591

# Default NTFY priority
NTFY_DEFAULT_PRIORITY = 'default'

# Log file path
LOG_FILE_PATH = './zegra-server.log'


### FUNCTIONS ###

async def print_help():
   """
   Print a help message
   """

   help_message = ('%s\n'
                   'A daemon with some basic automatization features for dealing with\n'
                   'Renault and Dacia vehicles\n'
                   '\n'
                   'Usage: %s [options]\n'
                   '\n'
                   'Options:\n'
                   '-h, --help        Output this help list and exit\n'
                   '-v, --version     Output version information and license and exit\n'
                   '-D, --debug       Output the debug log\n'
                   '-c, --config      Set another configuration file than the default\n'
                   '                  `%s` configuration file\n'
                   '\n'
                   '-p, --port        Set HVAC HTTP listener port (0-65535)',
                   PROJECT_NAME, sys.argv[0], JSON_CONFIG_FILE_PATH)

   print(help_message)


async def print_version():
   """
   Print version
   """

   version_message = ('%s version %s\n'
                      '\n'
                      'Copyright (C) 2024 TheRealOne78\n'
                      'License AGPLv3+: GNU AGPL version 3 or later <https://gnu.org/licenses/agpl.html>.\n'
                      'This is free software: you are free to change and redistribute it.\n'
                      'There is NO WARRANTY, to the extent permitted by law.',
                      PROJECT_NAME, VERSION_STRING)

   print(version_message)


async def get_config(config_file_path=JSON_CONFIG_FILE_PATH):
   """
   Read JSON config file and return it as a dictionary

   'config_file_path' contains the JSON config file path

   RETURN: config dictionary
   """

   with open(config_file_path, 'r', encoding="utf8") as json_file:
      return json.load(json_file)


async def send_ntfy_notification(uri, username, password, title, message, emoji, priority=NTFY_DEFAULT_PRIORITY):
   """
   Send a push notification to a NTFY topic.

   'uri' contains the URI of the NTFY topic (Eg. 'https://ntfy.sh/FooBar')
   'username' and 'password' contain the credentials to access the NTFY topic
   'title' contains the notification title
   'message' contains the notification body message
   'emoji' contains emojies that will appear before the title
   """

   headers = {
      'Title': title,
      'Tags': emoji,
      'Priority': priority
   }

   # Send NTFY push asynchronously
   try:
      async with aiohttp.ClientSession() as session:
         auth = aiohttp.BasicAuth(username, password)
         async with session.post(uri, headers=headers, data=message, auth=auth) as response:
            if response.status != 200:
               logging.error("[NTFY] Failed to send NTFY notification - HTTP response status `%s`", response.status)
            else:
               logging.debug("[NTFY] NTFY notification sent successfully")

   except aiohttp.ClientError as e:
      logging.error("[NTFY] An error occurred during the HTTP request: %s", e)
   except Exception as e:
      logging.error("[NTFY] An unexpected error occurred: %s", e)


async def charging_start(vehicle):
   """
   Send a charging-start payload to RenaultAPI

   'vehicle' object should contain a Kamereon vehicle object (account, VIN)
   """

   response = await vehicle.set_charge_start()

   logging.debug("[CHARGING_START] Sent charging-start request")

   # Return response from RenaultAPI
   return response


async def hvac_start(vehicle):
   """
   Send a hvac-start payload to RenaultAPI

   'vehicle' object should contain a Kamereon vehicle object (account, VIN)
   """

   # Payload data
   data = {
      'type': 'HvacStart',
      'attributes': { 'action': 'start' }
   }

    # Start HVAC
   response = await vehicle.session.set_vehicle_action(
       account_id=vehicle.account_id,
       vin=vehicle.vin,
       endpoint="actions/hvac-start",
       attributes=data['attributes'],
   )

   logging.debug("[CHARGING_START] Sent charging-start request")

   # Return response from RenaultAPI
   return response


async def create_vehicle(account, config_vehicle, vehicle_nickname):
   """
   Run vehicle checking as a separate asyncio task

   'account' object should contain a Kamereon account object
   'config_vehicle' contains the current vehicle's configuration
   'vehicle_nickname' contains the current vehicle's name (from config file)
   """

   try:
      # Prepare vehicle
      vehicle       = await account.get_api_vehicle(config_vehicle['VIN'])
      ntfy_uri      = config_vehicle['NTFY_topic']
      ntfy_username = config_vehicle['NTFY_auth']['username']
      ntfy_password = config_vehicle['NTFY_auth']['password']

      # Status checkers for NTFY notifications
      status_checkers = {
         'battery_percentage_checked': [],
         'charge_dict': {
            'count': 0,
            'hvac': False,
            'notified': False,
         },
         'battery_temp_notified': False,
         'battery_charged_notified': False
        }

      # Run as a daemon
      while True:
         # Get battery status
         battery_status = await vehicle.get_battery_status()

         # Update battery status variables
         battery_percentage   = battery_status.batteryLevel       # Percentage (0:100)
         battery_plugged      = battery_status.plugStatus         # Plug status (True/False)
         battery_temperature  = battery_status.batteryTemperature # Temperature reading depending on locale (°C/°F)
         battery_not_charging = True if (battery_status.chargingStatus < 1.0) else False # Is the vehicle NOT charging? (True/False)

         logging.debug("[%s] New car loop check:\n"   # vehicle_nickname
                       "battery_percentage - %s%%\n"  # battery_percentage
                       "battery_plugged - %s\n"       # battery_plugged
                       "battery_temperature - %s\n"   # battery_temperature
                       "battery_not_charging - %s\n", # battery_not_charging

                       vehicle_nickname,
                       battery_percentage,
                       battery_plugged,
                       battery_temperature,
                       battery_not_charging
                       )

         # Sanitize values
         has_none = False
         for name, val in (("battery_percentage",   battery_percentage),
                           ("battery_plugged",      battery_plugged),
                           ("battery_not_charging", battery_not_charging)
                           ):
            # Sometimes RenaultAPI returns this as none, see bug report
            # https://github.com/TheRealOne78/Zegra-server/issues/1
            if type(val) is NoneType:
               logging.warning("[%s] Value for `%s' is `%s'",
                            vehicle_nickname,
                            name,
                            type(val))
               await asyncio.sleep(3 * 60) # wait 3 minutes before retrying
               has_none = True
               break

         if has_none:
            has_none = False
            continue

         ## Check if battery percentage is low
         if battery_percentage <= config_vehicle['warn_battery_percentage'] \
            and not(battery_plugged) \
            and 'min' not in status_checkers['battery_percentage_checked']:
            # If critical (min) battery level
            if battery_percentage <= config_vehicle['min_battery_percentage']:
               title    = f"[{vehicle_nickname}] NIVEL BATERIE CRITIC!"
               message  = f"Nivelul bateriei a '{vehicle_nickname}' este critic - {battery_percentage}%"
               emoji    = "red_square"
               priority = "urgent"
               await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji, priority)
               status_checkers['battery_percentage_checked'].append('min')
               logging.debug("[%s] NTFY alerted for very low battery - %s%%", vehicle_nickname, battery_percentage)

            # If low (not critical) battery level
            elif 'warn' not in status_checkers['battery_percentage_checked']:
               title    = f"[{vehicle_nickname}] Nivel baterie scăzut!"
               message  = f"Nivelul bateriei a '{vehicle_nickname}' este scăzut - {battery_percentage}%"
               emoji    = "warning"
               priority = "high"
               await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji, priority)
               status_checkers['battery_percentage_checked'].append('warn')
               logging.debug("[%s] NTFY warned for low battery - %s%%", vehicle_nickname, battery_percentage)

            # Clear out status checker when vehicle's carger is plugged in
            elif battery_plugged:
               status_checkers['battery_percentage_checked'].clear()
               logging.debug("[%s] Cleared 'battery_percentage_checked' status checker", vehicle_nickname)


         ## Check if charging has stopped
         if battery_plugged and (battery_percentage < 98):
            # Clear out battery charged notified status checker
            status_checkers['battery_charged_notified'] = False
            if battery_not_charging:
               # Try to resume charging
               if status_checkers['charge_dict']['count'] <= config_vehicle['max_tries']:
                  await charging_start(vehicle)
                  status_checkers['charge_dict']['count'] += 1 # Increase check count until equal to config_vehicle['max_tries']
                  logging.debug("[%s] Executed chargin_start(), start count at %s - %s%%", vehicle_nickname, status_checkers['charge_dict']['count'], battery_percentage)

                  # Try to start charging by starting an HVAC cycle
               elif not(status_checkers['charge_dict']['hvac']):
                  await hvac_start(vehicle)
                  status_checkers['charge_dict']['hvac'] = True
                  logging.debug("[%s] HVAC started because charging_start() failed for %s times - %s%%", vehicle_nickname, status_checkers['charge_dict']['count'], battery_percentage)

                  # If HVAC fails, notify the user via NTFY
               elif not(status_checkers['charge_dict']['notified']):
                  title    = f"[{vehicle_nickname}] EV REFUZĂ SĂ SE ÎNCARCE!"
                  message  = f"Vehiculul '{vehicle_nickname}' refuză să se încarce - {battery_percentage}%"
                  emoji    = "electric_plug"
                  priority = "urgent"
                  await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji, priority)
                  status_checkers['charge_dict']['notified'] = True
                  logging.debug("[%s] NTFY alerted for car refusing to charge - %s%%", vehicle_nickname, battery_percentage)

         # Clear out status checker when the vehicle is fully charged
         elif battery_percentage >= 98: # For slight errors on battery level reading, take 98% as fully charged
            status_checkers['charge_dict']['count']    = 0
            status_checkers['charge_dict']['hvac']     = False
            status_checkers['charge_dict']['notified'] = False
            logging.debug("[%s] Cleared 'status_checkers['charge_dict'][*]' status checkers", vehicle_nickname)

            # Send a NTFY push notification when the car is fully charged
            if battery_plugged and not(status_checkers['battery_charged_notified']):
               title    = f"[{vehicle_nickname}] EV s-a încărcat"
               message  = f"Vehiculul '{vehicle_nickname}' este încărcat - {battery_percentage}%"
               emoji    = "white_check_mark"
               priority = "default"
               await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji, priority)
               status_checkers['battery_charged_notified'] = True
               logging.debug("[%s] NTFY notified for fully charged car - %s%%", vehicle_nickname, battery_percentage)


         ## Check if battery is overheating
         if type(battery_temperature) is not NoneType:
            if battery_temperature > config_vehicle['max_battery_temperature'] and not(status_checkers['battery_temp_notified']):
               title    = f"[{vehicle_nickname}] TEMPERATURĂ BATERIE RIDICATĂ!"
               message  = f"Vehiculul '{vehicle_nickname}' are temperatura bateriei foarte mare - {battery_temperature} °"
               emoji    = "stop_sign"
               priority = "urgent"
               await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji, priority)
               status_checkers['battery_temp_notified'] = True
               logging.debug("[%s] NTFY alerted for battery temperature too high - %s°", vehicle_nickname, battery_temperature)

               # For safety reasons, let it cool to 'max_battery_temperature - 3' before unchecking battery_temp_notified
            elif battery_temperature - 3 <= config_vehicle['max_battery_temperature']:
               status_checkers['battery_temp_notified'] = False
               logging.debug("[%s] Cleared 'battery_temp_notified' temperature status checkers", vehicle_nickname)

         # Sleep async until the next check
         await asyncio.sleep(config_vehicle['check_time'] * 60)

   except asyncio.CancelledError:
      logging.warning("[%s] This asyncio process is being cancelled due to asyncio.CancelledError being raised", vehicle_nickname)
      return


async def http_request_handler(request, account, config_dict):
   """
   Handle POST requests from http_hvac_listener() by sending a HVAC start
   payload to RenaultAPI if current's EV battery level is greater then 20%. If
   EV battery level is less or equal to 20%, send a NTFY notification to the
   client mentioning that HVAC cannot be started due to low battery.

   'request' contains the request data from the client, containing the body
   parameter {Name: "<Name>"}, which will be used to determine which car should
   the HVAC start 'config_vehicle' contains the current vehicle's configuration

   'config_dict' contains the config parameters for all vehicles in the JSON
   config file
   """

   try:
      # Retreive vehicle name from POST request
      data             = await request.json()
      vehicle_nickname = data.get('Name')

      # Check if nickname can be found in the JSON config file
      if vehicle_nickname not in config_dict['Cars']:
         return aiohttp.web.json_response({'success': False, 'message': 'Vehicle name not found in the JSON config file!'}, status=404)

      # Fetch vehicle and battery status
      vehicle          = await account.get_api_vehicle(config_dict['Cars'][vehicle_nickname]['VIN'])
      battery_status   = await vehicle.get_battery_status()

      # Start HVAC only if the battery level is higher than 30%
      if battery_status.batteryLevel > 30:
         await hvac_start(vehicle)
         return aiohttp.web.json_response({'success': True})

      # If battery level is less-or-equal than 30%, the car can't start, so send a NTFY alert
      ntfy_uri      = config_dict['Cars'][vehicle_nickname]['NTFY_topic']
      ntfy_username = config_dict['Cars'][vehicle_nickname]['NTFY_auth']['username']
      ntfy_password = config_dict['Cars'][vehicle_nickname]['NTFY_auth']['password']
      title         = f"[{vehicle_nickname}] AC nu a pornit"
      message       = f"Vehiculul '{vehicle_nickname}' nu are suficientă baterie (sub 30%) ca să poată porni AC - {battery_status.batteryLevel}%"
      emoji         = "battery"
      priority      = "default"
      await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji, priority)
      return aiohttp.web.json_response({'success': False, 'message': 'Vehicle does not have enough battery level (less than 30%) to start AC'}, status=403)

   except asyncio.CancelledError:
      logging.warning("This asyncio process is being cancelled, shutting down HVAC listener")
      return

   except Exception as e:
      logging.exception("An unexpected error occurred while handling the request: `%s`", e)
      return aiohttp.web.json_response({'success': False, 'message': str(e)}, status=500)


async def http_hvac_listener(account, config_dict, port=HVAC_HTTP_LISTENER_PORT):
   """
   Listen to POST requests and send an HVAC start payload with config_dicconfig_dict[Name]['VIN']
   through http_request_handler()
   """

   try:
      app    = aiohttp.web.Application()
      app.router.add_post('/', lambda request: http_request_handler(request, account, config_dict))

      # Set up a web runner
      runner = aiohttp.web.AppRunner(app)
      await runner.setup()

      # Start TCP socket
      site   = aiohttp.web.TCPSite(runner, 'localhost', port)
      await site.start()

      logging.info("HTTP HVAC listener started at http://localhost:%s", port)

      # Wait for GET requests
      await asyncio.Event().wait()

   except asyncio.CancelledError:
      logging.info("HTTP HVAC listener cancelled due to this asyncio process being cancelled")

      await site.stop()
      await runner.cleanup()
      return

async def init_logger():
   # Create a file handler
   file_handler = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
   file_handler.setLevel(logging.DEBUG)    # Set the file handler to log all levels

   # Create a console handler
   console_handler = logging.StreamHandler()
   console_handler.setLevel(logging.INFO)  # Set the console handler to log INFO

   # Create a formatter
   formatter = logging.Formatter('[%(asctime)s] [%(levelname).1s] %(funcName)s(): %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

   # Set formatter for both handlers
   file_handler.setFormatter(formatter)
   console_handler.setFormatter(formatter)

   # Add handlers to the root logger
   logging.root.addHandler(file_handler)
   logging.root.addHandler(console_handler)

   # If log file already exists, rename it to 'LOG_FILE_PATH'.old
   if os.path.isfile(LOG_FILE_PATH):
      os.rename(LOG_FILE_PATH, LOG_FILE_PATH + '.old')

   # Set the default logging level to INFO
   logging.root.setLevel(logging.INFO)


async def main():
   """
   Create an asyncio task for each vehicle in the JSON config file to monitor
   battery status.

   Also create an asyncio task for listening for HTTP requests to start HVAC for
   a specific vehicle in the JSON config file.

   Optional arguments are also available, with them printing help or vesion,
   turn on debug logging, use a custom JSON config file and a custom port for
   the HTTP HVAC listener
   """

   # Turn on info logging by default
   if os.path.isfile(LOG_FILE_PATH):
      os.rename(LOG_FILE_PATH, LOG_FILE_PATH + '.old')
   logging.basicConfig(filename=LOG_FILE_PATH,
                       encoding='utf-8',
                       format='[%(asctime)s] [%(levelname).1s] %(name)s: %(message)s',
                       datefmt='%Y-%m-%d %H:%M:%S',
                       level=logging.INFO)

   # Initialize variables
   config_dict = ""
   port        = HVAC_HTTP_LISTENER_PORT # Default this

   # Get arguments
   opts, args = getopt.getopt(sys.argv[1:], "hvDc:p:", ['help', 'version', 'debug', 'config=', 'port='])
   has_arg    = {
      'config_dict': False, # Determine whether or not using the argument config file
      'port': False         # Determine whether or not using the argument HTTP port
   }

   # Handle options
   for opt, arg in opts:
      if opt in   ('-h', '--help'):    # Print a help message and exit gracefully
         await print_help()
         sys.exit(0)

      elif opt in ('-v', '--version'): # Print version & licensing and exit gracefully
         await print_version()
         sys.exit(0)

      elif opt in ('-D', '--debug'):   # Turn on debug logging
         logging.root.setLevel(logging.DEBUG)
         logging.debug("Turned on debug logging")

      elif opt in ('-c', '--config'):  # Use another config file path than JSON_CONFIG_FILE_PATH
         config_dict            = await get_config(arg)
         has_arg['config_dict'] = True

      elif opt in ('-p', '--port'):    # Use another port than the default HVAC_HTTP_LISTENER_PORT or from config file
         port = arg
         has_arg['port'] = True

   # Get config from JSON file
   if not has_arg['config_dict']:
      config_dict = await get_config()

   # Enable debugging if it's enabled in the config file
   if config_dict['debug']:
      logging.root.setLevel(logging.DEBUG)
      logging.debug("Turned on debug logging")

   # Get port from config if available and if not has_arg['config_dict']
   if 'http_hvac_listener_port' in config_dict and not has_arg['port']:
      port = config_dict['http_hvac_listener_port']

   # asyncio coroutines to gather
   tasks = []

   # Store admin NTFY info
   admin_ntfy_uri      = config_dict['NTFY_admin']['NTFY_topic']
   admin_ntfy_username = config_dict['NTFY_admin']['NTFY_auth']['username']
   admin_ntfy_password = config_dict['NTFY_admin']['NTFY_auth']['password']

   # Send a low priority NTFY notification to the admin about the starting of the server
   title    = f"[Server starting] Starting {PROJECT_NAME} server ..."
   message  = f"[{datetime.today().strftime('%Y/%m/%d  - %H:%M:%S')}] The {PROJECT_NAME} server is starting ..."
   emoji    = "checkered_flag"
   priority = "min"
   await send_ntfy_notification(admin_ntfy_uri,
                                admin_ntfy_username,
                                admin_ntfy_password,
                                title,
                                message,
                                emoji,
                                priority)

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
               logging.debug("Got vehicle error:\n%s", vehicles.errors)
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
                  logging.error("[main] `%s` is missing in the Renault/Dacia account!", config_dict['Cars'][vehicle]['VIN'])
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


         logging.warning("Got exception: %s", e)

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
         logging.error("[SERVER SHUTDOWN] An unexpected error occurred: %s", e)

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


### START ###
if __name__ == "__main__":
   asyncio.run(main())
