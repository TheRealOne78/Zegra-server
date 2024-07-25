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

import asyncio
import aiohttp
import aiohttp.web
from .todo import * # TODO: Remove this after restructuring everything
from .logger cimport logger

async def http_request_handler(request, account, config_dict):
    """
    Handle POST requests from http_hvac_listener() by sending a HVAC start
    payload to RenaultAPI if current's EV battery level is greater then 30%. If
    EV battery level is less or equal to 30%, send a NTFY notification to the
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
        vehicle        = await account.get_api_vehicle(config_dict['Cars'][vehicle_nickname]['VIN'])
        battery_status = await vehicle.get_battery_status()

        # Start HVAC only if the battery level is higher than 30%
        if battery_status.batteryLevel > 30:
            await hvac_start(vehicle)
            return aiohttp.web.json_response({'success': True})

        # If battery level is less-or-equal than 30%, the car can't start, so send a NTFY alert
        await send_ntfy_notification(config_dict['Cars'][vehicle_nickname]['NTFY_topic'],
                                     config_dict['Cars'][vehicle_nickname]['NTFY_auth']['username'],
                                     config_dict['Cars'][vehicle_nickname]['NTFY_auth']['password'],
                                     f"[{vehicle_nickname}] AC nu a pornit",
                                     f"Vehiculul '{vehicle_nickname}' nu are suficientă baterie (sub 30%) ca să poată porni AC - {battery_status.batteryLevel}%",
                                     "battery",
                                     "default")
        return aiohttp.web.json_response({'success': False, 'message': 'Vehicle does not have enough battery level (less than 30%) to start AC'}, status=403)

    except asyncio.CancelledError:
        logger.warning("This asyncio process is being cancelled, shutting down HVAC listener")
        return

    except Exception as e:
        logger.exception("An unexpected error occurred while handling the request: `%s`", e)
        return aiohttp.web.json_response({'success': False, 'message': str(e)}, status=500)


async def http_hvac_listener(account, config_dict, port=HVAC_HTTP_LISTENER_PORT):
    """
    Listen to POST requests and send an HVAC start payload with config_dicconfig_dict[Name]['VIN']
    through http_request_handler()
    """

    runner = None
    site = None

    try:
        app = aiohttp.web.Application()
        app.router.add_post('/', lambda request: http_request_handler(request, account, config_dict))

        # Set up a web runner
        runner = aiohttp.web.AppRunner(app)
        await runner.setup()

        # Start TCP socket
        site = aiohttp.web.TCPSite(runner, 'localhost', port)
        await site.start()

        logger.info("HTTP HVAC listener started at http://localhost:%s", port)

        # Wait for GET requests
        await asyncio.Event().wait()

    except asyncio.CancelledError:
        logger.info("HTTP HVAC listener cancelled due to this asyncio process being cancelled")

        if site != None:
            await site.stop()
        if runner != None:
            await runner.cleanup()
