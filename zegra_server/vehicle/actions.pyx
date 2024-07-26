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
from ..logger cimport logger

async def charging_start(vehicle):
    """
    Send a charging-start payload to RenaultAPI

    'vehicle' object should contain a Kamereon vehicle object (account, VIN)
    """

    response = await vehicle.set_charge_start()

    logger.debug("[CHARGING_START] Sent charging-start request")

    # Return response from RenaultAPI
    return response


async def hvac_start_notemp(vehicle,
                            schedule = None):
    """
    Send a hvac-start payload to RenaultAPI

    'vehicle' object should contain a Kamereon vehicle object (account, VIN)
    """

     # Start HVAC
    response = await vehicle.session.set_vehicle_action(
        account_id = vehicle.account_id,
        vin        = vehicle.vin,
        endpoint   = "actions/hvac-start",
        attributes = { 'action': 'start' },
    )

    logger.debug("[HVAC_START_NOTEMP] Sent hvac-start request")

    # Return response from RenaultAPI
    return response

async def hvac_start_temp(vehicle,
                          temp = 14, # That's the minimum renault allows
                          schedule = None):
    """
    Send a hvac-start payload to RenaultAPI

    'vehicle' object should contain a Kamereon vehicle object (account, VIN)
    """

     # Start HVAC
    response = await vehicle.set_ac_start(temp=temp, schedule=schedule)

    logger.debug("[HVAC_START_TEMP] Sent hvac-start request with temperature")

    # Return response from RenaultAPI
    return response


async def hvac_cancel(vehicle):
    response = await vehicle.set_ac_stop()

    logger.debug("[HVAC_CANCEL] Sent hvac-cancel request")

    # Return response from RenaultAPI
    return response
