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

from ..logger cimport logger
from types import NoneType
import asyncio
import aiohttp
from ..ntfy import send_ntfy_notification
from .actions import hvac_start_notemp, charging_start

async def create_vehicle(account, config_vehicle, vehicle_nickname):
   """
   Run vehicle checking as a separate asyncio task

   'account' object should contain a Kamereon account object
   'config_vehicle' contains the current vehicle's configuration
   'vehicle_nickname' contains the current vehicle's name (from config file)
   """

   # Account vehicle
   cdef dict vehicle = {}

   # Status checkers for NTFY notifications
   cdef dict status_checkers = {
      'battery_percentage_checked': [],
      'charge_dict': {
         'count': 0,
         'hvac': False,
         'notified': False,
      },
      'battery_temp_notified': False,
      'battery_charged_notified': False
     }

   # Battery status
   cdef dict battery_status       = None
   cdef int  battery_percentage
   cdef int  battery_plugged
   cdef int  battery_temperature
   cdef bint battery_not_charging
   cdef bint tmp_bool_has_none    = False

   # NTFY - TODO: DEPRECATED
   cdef str ntfy_uri      = config_vehicle['NTFY_topic']
   cdef str ntfy_username = config_vehicle['NTFY_auth']['username']
   cdef str ntfy_password = config_vehicle['NTFY_auth']['password']
   cdef str title
   cdef str message
   cdef str emoji
   cdef str priority

   try:
      # Prepare vehicle
      vehicle = await account.get_api_vehicle(config_vehicle['VIN'])
      
      # Run as a daemon
      while True:
         # Get battery status
         battery_status = await vehicle.get_battery_status()

         # Update battery status variables
         battery_percentage   = battery_status.batteryLevel       # Percentage (0:100)
         battery_plugged      = battery_status.plugStatus         # Plug status (True/False)
         battery_temperature  = battery_status.batteryTemperature # Temperature reading depending on locale (°C/°F)
         battery_not_charging = True if (battery_status.chargingStatus < 1.0) else False # Is the vehicle NOT charging? (True/False)

         logger.debug("[%s] New car loop check:\n"    # vehicle_nickname
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
         tmp_bool_has_none = False
         for name, val in (("battery_percentage",   battery_percentage),
                           ("battery_plugged",      battery_plugged),
                           ("battery_not_charging", battery_not_charging)
                           ):
            # Sometimes RenaultAPI returns this as None, see bug report
            # https://github.com/TheRealOne78/Zegra-server/issues/1
            if type(val) is NoneType:
               logger.warning("[%s] Value for `%s' is `%s'",
                            vehicle_nickname,
                            name,
                            type(val))
               await asyncio.sleep(3 * 60) # wait 3 minutes before retrying
               tmp_bool_has_none = True
               break

         if tmp_bool_has_none:
            tmp_bool_has_none = False
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
               logger.debug("[%s] NTFY alerted for very low battery - %s%%", vehicle_nickname, battery_percentage)

            # If low (not critical) battery level
            elif 'warn' not in status_checkers['battery_percentage_checked']:
               title    = f"[{vehicle_nickname}] Nivel baterie scăzut!"
               message  = f"Nivelul bateriei a '{vehicle_nickname}' este scăzut - {battery_percentage}%"
               emoji    = "warning"
               priority = "high"
               await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji, priority)
               status_checkers['battery_percentage_checked'].append('warn')
               logger.debug("[%s] NTFY warned for low battery - %s%%", vehicle_nickname, battery_percentage)

            # Clear out status checker when vehicle's carger is plugged in
            elif battery_plugged:
               status_checkers['battery_percentage_checked'].clear()
               logger.debug("[%s] Cleared 'battery_percentage_checked' status checker", vehicle_nickname)


         ## Check if charging has stopped
         if battery_plugged and (battery_percentage < 98):
            # Clear out battery charged notified status checker
            status_checkers['battery_charged_notified'] = False
            if battery_not_charging:
               # Try to resume charging
               if status_checkers['charge_dict']['count'] <= config_vehicle['max_tries']:
                  await charging_start(vehicle)
                  status_checkers['charge_dict']['count'] += 1 # Increase check count until equal to config_vehicle['max_tries']
                  logger.debug("[%s] Executed charging_start(), start count at %s - %s%%", vehicle_nickname, status_checkers['charge_dict']['count'], battery_percentage)

                  # Try to start charging by starting an HVAC cycle
               elif not(status_checkers['charge_dict']['hvac']):
                  await hvac_start_notemp(vehicle)
                  status_checkers['charge_dict']['hvac'] = True
                  logger.debug("[%s] HVAC started because charging_start() failed for %s times - %s%%", vehicle_nickname, status_checkers['charge_dict']['count'], battery_percentage)

                  # If HVAC fails, notify the user via NTFY
               elif not(status_checkers['charge_dict']['notified']):
                  title    = f"[{vehicle_nickname}] EV REFUZĂ SĂ SE ÎNCARCE!"
                  message  = f"Vehiculul '{vehicle_nickname}' refuză să se încarce - {battery_percentage}%"
                  emoji    = "electric_plug"
                  priority = "urgent"
                  await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji, priority)
                  status_checkers['charge_dict']['notified'] = True
                  logger.debug("[%s] NTFY alerted for car refusing to charge - %s%%", vehicle_nickname, battery_percentage)

         # Clear out status checker when the vehicle is fully charged
         elif battery_percentage >= 98: # For slight errors on battery level reading, take 98% as fully charged
            status_checkers['charge_dict']['count']    = 0
            status_checkers['charge_dict']['hvac']     = False
            status_checkers['charge_dict']['notified'] = False
            logger.debug("[%s] Cleared 'status_checkers['charge_dict'][*]' status checkers", vehicle_nickname)

            # Send a NTFY push notification when the car is fully charged
            if battery_plugged and not(status_checkers['battery_charged_notified']):
               title    = f"[{vehicle_nickname}] EV s-a încărcat"
               message  = f"Vehiculul '{vehicle_nickname}' este încărcat - {battery_percentage}%"
               emoji    = "white_check_mark"
               priority = "default"
               await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji, priority)
               status_checkers['battery_charged_notified'] = True
               logger.debug("[%s] NTFY notified for fully charged car - %s%%", vehicle_nickname, battery_percentage)


         ## Check if battery is overheating
         if type(battery_temperature) is not NoneType:
            if battery_temperature > config_vehicle['max_battery_temperature'] and not(status_checkers['battery_temp_notified']):
               title    = f"[{vehicle_nickname}] TEMPERATURĂ BATERIE RIDICATĂ!"
               message  = f"Vehiculul '{vehicle_nickname}' are temperatura bateriei foarte mare - {battery_temperature} °"
               emoji    = "stop_sign"
               priority = "urgent"
               await send_ntfy_notification(ntfy_uri, ntfy_username, ntfy_password, title, message, emoji, priority)
               status_checkers['battery_temp_notified'] = True
               logger.debug("[%s] NTFY alerted for battery temperature too high - %s°", vehicle_nickname, battery_temperature)

               # For safety reasons, let it cool to 'max_battery_temperature - 3' before unchecking battery_temp_notified
            elif battery_temperature - 3 <= config_vehicle['max_battery_temperature']:
               status_checkers['battery_temp_notified'] = False
               logger.debug("[%s] Cleared 'battery_temp_notified' temperature status checkers", vehicle_nickname)

         # Sleep async until the next check
         await asyncio.sleep(config_vehicle['check_time'] * 60)

   except asyncio.CancelledError:
      logger.warning("[%s] This asyncio process is being cancelled due to asyncio.CancelledError being raised", vehicle_nickname)
      return
