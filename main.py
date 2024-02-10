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
# License along with Zegra-server. If not, see                         #
# <http://www.gnu.org/licenses/>.                                      #
#                                                                      #
########################################################################


### IMPORT ###

# Import renault_api
from renault_api.renault_client import RenaultClient
from renault_api.renault_vehicle import RenaultVehicle

# Import asyncio
import aiohttp
import asyncio

# Import arguments
import sys
import getopt

# Import misc
import json
import logging


### CONSTANTS ###

# Project name
PROJECT_NAME = "Zegra"

# Version string
VERSION_STRING = "1.0.0"

# Default JSON config file path
JSON_CONFIG_FILE_PATH = './config/config.json'

# Default HVAC HTTP listener port
HVAC_HTTP_LISTENER_PORT = 47591


### FUNCTIONS ###

def print_help():
   """
   Print a help message
   """

   version_message = (f'{PROJECT_NAME}\n'
                      'A daemon with some basic automatization features for dealing with\n'
                      'Renault and Dacia vehicles\n'
                      '\n'
                      f'Usage: {sys.argv[0]} [options]\n'
                      '\n'
                      'Options:\n'
                      '-h, --help        Output this help list and exit\n'
                      '-v, --version     Output version information and license and exit\n'
                      '-D, --debug       Output the debug log\n'
                      '-c, --config      Set another configuration file than the default\n'
                      f'                  \'{JSON_CONFIG_FILE_PATH}\' configuration file\n'
                      '\n'
                      '-p, --port        Set HVAC HTTP listener port (0-65535)'
                      )

   print(version_message)


def print_version():
   """
   Print version
   """

   version_message = (f'{PROJECT_NAME} version {VERSION_STRING}\n'
                      '\n'
                      'Copyright (C) 2024 TheRealOne78\n'
                      'License AGPLv3+: GNU AGPL version 3 or later <https://gnu.org/licenses/agpl.html>.\n'
                      'This is free software: you are free to change and redistribute it.\n'
                      'There is NO WARRANTY, to the extent permitted by law.'
                      )

   print(version_message)


def get_config(config_file_path=JSON_CONFIG_FILE_PATH):
   """
   Read JSON config file and return it as a dictionary

   'config_file_path' contains the JSON config file path

   RETURN: config dictionary
   """

   with open(config_file_path, 'r') as json_file:
      return json.load(json_file)


async def init_account_info(config_dict):
   """
   Initiate account, verify if VINs from the JSON config file are correct and
   return the account back.

   'config_dict' contains the config data from the JSON config file.

   RETURN: Kamereon account object
   """

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

      ## Verify if VINs from JSON config file are valid
      vehicles     = await account.get_vehicles()
      renault_vins = [] # Will store VINs fetched from RenaultAPI

      # Get and store each VIN from the current account into renault_vins
      for vehicle_link in vehicles.raw_data['vehicleLinks']:
         renault_vins.append(vehicle_link['vin'])

      # Check each VIN and point out all invalid VINs
      invalid_vin = False # If True, at least one of the VINs from the JSON config file is invalid
      for vehicle in config_dict['Cars']:
         if config_dict['Cars'][vehicle]['VIN'] not in renault_vins:
            logging.error(f"`{config_dict['Cars'][vehicle]['VIN']}' is missing in the Renault/Dacia account!")
            invalid_vin = True # Set error and continue logging eventual invalid VINs
      if invalid_vin:
         exit(1)

      # Return Kamereon account object
      return account


async def send_ntfy_notification(uri, username, password, title, message, emoji):
   """
   Send a push notification to a NTFY topic.

   'uri' contains the URI of the NTFY topic (Eg. 'https://ntfy.sh/FooBar')
   'username' and password contain the credentials to access the NTFY topic
   'title' contains the notification title
   'message' contains the notification body message
   'emoji' contains emojies that will appear before the title
   """

   data = {
      'title': title,
      'message': message,
      'tags': emoji
   }

   async with aiohttp.ClientSession() as session:
      auth = aiohttp.BasicAuth(username, password)
      async with session.post(uri, data=data, auth=auth) as response:
         if response.status != 200:
            logging.error(f"Failed to send NTFY notification - HTTP reponse status '{response.status}'")


async def charging_start(vehicle):
   """NOTE:TODO: WIP
   Send a charging-start payload to RenaultAPI

   'vehicle' object should contain a Kamereon vehicle object (account, VIN)
   """

   data = {
      'type': 'ChargingStart',
      'attributes': { 'action': 'start' }
   }

   # set_charge_start()    TODO

async def hvac_start(vehicle):
   """NOTE:TODO: WIP
   Send a hvac-start payload to RenaultAPI

   'vehicle' object should contain a Kamereon vehicle object (account, VIN)
   """

   data = {
      'type': 'HvacStart',
      'attributes': { 'action': 'start' }
   }

   #response = await self.session.set_vehicle_action(
   #    account_id=self.account_id,
   #    vin=self.vin,
   #    endpoint="actions/hvac-start",
   #    attributes=attributes,
   #) TODO


async def create_vehicle(account, config_vehicle, vehicle_nickname):
   """
   Run vehicle checking as a separate asyncio task

   'account' object should contain a Kamereon account object
   'config_vehicle' contains the current vehicle's configuration
   'vehicle_nickname' contains the current vehicle's name (from config file)
   """

   # Prepare vehicle
   vehicle_nickname = config_vehicle
   vehicle          = await account.get_api_vehicle(config_vehicle['VIN'])
   ntfy_uri         = config_vehicle['NTFY_topic']
   ntfy_username    = config_vehicle['NTFY_auth']['username']
   ntfy_password    = config_vehicle['NTFY_auth']['password']

   # Status checkers
   status_checkers = {
      'battery_percentage_checked': [],
      'charge_dict': {
         'count': 0,
         'hvac': False,
         'notified': False,
      },
      'battery_temp_notified': False
   }
   # Run as a daemon
   while True:
      # Get battery status
      battery_status = await vehicle.get_battery_status()

      # Update battery status variables
      battery_percentage  = battery_status.batteryLevel        # Percentage (0:100)
      battery_plugged     = battery_status.plugStatus          # Plug status (True/False)
      battery_temperature = battery_status.batteryTemperature  # Temperature reading depending on locale (°C/°F)
      battery_is_charging = int(battery_status.chargingStatus) # Is the vehicle charging? (True/False)

      ## Check if battery percentage is low
      if battery_percentage <= config_vehicle['warn_battery_percentage'] \
      and not battery_plugged \
      and not "min" in status_checker.battery_percentage_checked:
         # If critical (min) battery level
         if battery_percentage <= config_vehicle['min_battery_percentage']:
            title   = f"[{vehicle_nickname}] NIVEL BATERIE CRITIC!"
            message = f"Nivelul bateriei a '{vehicle_nickname}' este critic - {battery_percentage}"
            emoji   = "red_square"
            await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji)
            battery_percentage_checked.append('min')

         # If low (not critical) battery level
         elif not "warn" in battery_percentage_checked:
            title   = f"[{vehicle_nickname}] Nivel baterie scăzut!"
            message = f"Nivelul bateriei a '{vehicle_nickname}' este scăzut - {battery_percentage}"
            emoji   = "warning"
            await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji)
            battery_percentage_checked.append('warn')

      # Clear out status checker when vehicle's carger is plugged in
      elif battery_plugged:
         battery_percentage_checked.clear()

      ## Check if charging has stopped
      if battery_plugged \
      and battery_percentage < 97 \
      and not battery_is_charging:
         if status_checkers.charge_dict.count <= config_vehicle['max_tries']:
            #TODO: send POST payload to 'await charging_start()' to resume charging
            await charging_start(vehicle) #NOTE: Test this
            status_checkers.charge_dict.count += 1 # Increase check count until equal to config_vehicle['max_tries']
         elif not status_checkers.charge_dict.hvac:
            #TODO: send POST payload to 'await hvac_start()' to start HVAC
            await hvac_start(vehicle)     #NOTE: Test this
            status_checkers.charge_dict.hvac = True
         elif not status_checkers.charge_dict.notified:
            title   = f"[{vehicle_nickname}] EV REFUZĂ SĂ SE ÎNCARCE!"
            message = f"Vehiculul '{vehicle_nickname}' refuză să se încarce - {battery_percentage}"
            emoji   = "electric_plug"
            await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji)
            status_checkers.charge_dict.notified = True
      # Clear out status checker when the vehicle is fully charged
      elif battery_percentage >= 97: # For slight errors on battery level reading, take 97% as fully charged
         status_checkers.charge_dict.count    = 0
         status_checkers.charge_dict.hvac     = False
         status_checkers.charge_dict.notified = False

      # Check if battery is overheating
      if battery_temperature > config_vehicle['max_battery_temperature'] and not battery_temp_notified:
         title   = f"[{vehicle_nickname}] TEMPERATURĂ BATERIE RIDICATĂ!"
         message = f"Vehiculul '{vehicle_nickname}' are temperatura bateriei foarte mare - {battery_temperature}"
         emoji   = "stop_sign"
         await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji)
         battery_temp_notified = True
      else:
         if battery_temperature - 3 > config_vehicle['max_battery_temperature']:
            pass # For safety reasons, let it cool to 'max_battery_temperature - 3' before unchecking battery_temp_notified
         else:
            battery_temp_notified = False

      # Sleep async until the next check
      asyncio.sleep(config_vehicle['check_time'] * 60)

async def http_request_handler(request, config_vehicles):
   """
   Handle POST requests from http_hvac_listener() by sending a HVAC start
   payload to RenaultAPI if current's EV battery level is greater then 20%. If
   EV battery level is less or equal to 20%, send a NTFY notification to the
   client mentioning that HVAC cannot be started due to low battery.

   'request' contains the request data from the client, containing the body
   parameter {Name: "<Name>"}, which will be used to determine which car should
   the HVAC start 'config_vehicle' contains the current vehicle's configuration

   'config_vehicles' contains the config parameters for all vehicles in the JSON
   config file
   """

   vehicle        = await account.get_api_vehicle(config_vehicles[nickname]['VIN'])
   battery_status = await vehicle.get_battery_status()

   if battery_status.batteryLevel <= 30:
      title   = f"[{vehicle_nickname}] AC nu a pornit"
      message = f"Vehiculul '{vehicle_nickname}' nu are suficientă baterie ca să poată porni AC - {battery_status.batteryLevel}"
      emoji   = "battery"
   else:
      try:
         data     = await request.json()
         nickname = data.get('Name')
         if name in cars:
            await hvac_start(config_vehicles[name]['VIN'])
            return aiohttp.web.json_response({'success': True})
         else:
            return aiohttp.web.json_response({'success': False, 'message': 'Car name not found in the JSON config file!'}, status=404)
      except Exception as e:
         logging.exception("An unexpected error occurred while handling the request")
         return aiohttp.web.json_response({'success': False, 'message': str(e)}, status=500)



async def http_hvac_listener(cars, port=HVAC_HTTP_LISTENER_PORT):
   """
   Listen to POST requests and send an HVAC start payload with cars[Name]['VIN']
   through http_request_handler()
   """

   app    = aiohttp.web.Application()
   app.router.add_post('/', lambda request: http_request_handler(request, cars))

   runner = aiohttp.web.AppRunner(app)
   await runner.setup()

   site   = aiohttp.web.TCPSite(runner, 'localhost', port)
   await site.start()
   logging.info(f"HTTP HVAC listener started at http://localhost:{port}")


async def main():
   # Initialize variables
   config_dict=""
   port       = HVAC_HTTP_LISTENER_PORT # Default this

   # Get arguments
   opts, args = getopt.getopt(sys.argv[1:], "hvDc:p:", ['help', 'version', 'debug', 'config=', 'port='])
   has_arg    = {
      config_dict: False, # Determine whether or not using the argument config file
      port: False         # Determine whether or not using the argument HTTP port
   }

   # Handle options
   for opt, arg in opts:
      if opt in   ('-h', '--help'):    # Print a help message and exit gracefully
         print_help()
         exit(0)

      elif opt in ('-v', '--version'): # Print version & licensing and exit gracefully
         print_version()
         exit(0)

      elif opt in ('-D', '--debug'):   # Turn on debug logging
         logging.basicConfig(level=logging.DEBUG)
         logging.debug("Turned on debug logging")

      elif opt in ('-c', '--config'):  # Use another config file path than JSON_CONFIG_FILE_PATH
         print(arg)
         config_dict         = get_config(arg)
         has_arg.config_dict = True

      elif opt in ('-p', '--port'):    # Use another port than the default HVAC_HTTP_LISTENER_PORT or from config file
         port = arg

   # Get config from JSON file
   if not has_arg.config_dict:
      config_dict = get_config()

   # Get account info from JSON config file
   account = await init_account_info(config_dict)

   # asyncio coroutines to gather
   tasks = []

   #Create an asyncio coroutine for each car entry
   #for car_entry in entries: #TODO
   #    task = asyncio.create_task(create_vehicle(account, vehicle))
   #    tasks.append(task)

   ## Create async task for HTTP Listener
   #task = asyncio.create_task(http_hvac_listener(account, cars, port))
   #tasks.append(task)
   #
   # Wait for all coroutines to complete
   await asyncio.gather(*tasks)


### START ###
if __name__ == "__main__":
   asyncio.run(main())
