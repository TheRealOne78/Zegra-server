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


### IMPORT ###

import gc
import json
import os
import logging
import signal
from datetime import datetime
from types import NoneType

import sys
import getopt

import asyncio
import aiohttp
import aiohttp.web

from renault_api.renault_client import RenaultClient
from renault_api.credential_store import FileCredentialStore

# Base exceptions
from renault_api.exceptions import (
    NotAuthenticatedException,
    EndpointNotAvailableError,
)

# Gigya (auth layer) exceptions
from renault_api.gigya.exceptions import (
    GigyaException,
    InvalidCredentialsException,
)

# Kamereon (vehicle API layer) exceptions
from renault_api.kamereon.exceptions import (
    AccessDeniedException,
    ChargeModeInProgressException,
    FailedForwardException,
    ForbiddenException,
    InvalidUpstreamException,
    NotSupportedException,
    PrivacyModeOnException,
    QuotaLimitException,
    ResourceNotFoundException,
)


### CONSTANTS ###

PROJECT_NAME            = "Zegra"
VERSION_STRING          = "1.0.0"
JSON_CONFIG_FILE_PATH   = './config/config.json'
CREDENTIAL_STORE_PATH   = './config/credentials.json'  # Persisted Gigya/Kamereon tokens
HVAC_HTTP_LISTENER_PORT = 47591
NTFY_DEFAULT_PRIORITY   = 'default'
LOG_FILE_PATH           = './zegra-server.log'

# Retry wait times (in seconds)
WAIT_TRANSIENT = 60      # Generic connection / upstream errors
WAIT_QUOTA     = 5 * 60  # Quota exhausted — wait longer to avoid hammering
WAIT_FORBIDDEN = 2 * 60  # 403 / access denied — slightly more conservative
WAIT_AUTH      = 5 * 60  # Gigya credential issues — avoid triggering rate-limits


### HELPERS ###

async def cancel_tasks(tasks: list):
    """Cancel all running tasks and wait for them to finish cleanly."""
    for task in tasks:
        task.cancel()
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    gc.collect()  # Help reclaim memory from cancelled task closures promptly


### FUNCTIONS ###

async def print_help():
    """Print a help message."""
    print('%s\n'
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
          '-p, --port        Set HVAC HTTP listener port (0-65535)'
          % (PROJECT_NAME, sys.argv[0], JSON_CONFIG_FILE_PATH))


async def print_version():
    """Print version."""
    print('%s version %s\n'
          '\n'
          'Copyright (C) 2024 TheRealOne78\n'
          'License AGPLv3+: GNU AGPL version 3 or later <https://gnu.org/licenses/agpl.html>.\n'
          'This is free software: you are free to change and redistribute it.\n'
          'There is NO WARRANTY, to the extent permitted by law.'
          % (PROJECT_NAME, VERSION_STRING))


async def get_config(config_file_path=JSON_CONFIG_FILE_PATH):
    """Read JSON config file and return it as a dictionary."""
    with open(config_file_path, 'r', encoding="utf8") as json_file:
        return json.load(json_file)


async def send_ntfy_notification(ntfy_session, uri, username, password,
                                 title, message, emoji,
                                 priority=NTFY_DEFAULT_PRIORITY):
    """
    Send a push notification to a NTFY topic.

    'ntfy_session' is a long-lived aiohttp.ClientSession shared across all
    calls. Using a shared session avoids creating and tearing down a new
    TCPConnector on every notification, which was the primary source of the
    memory growth seen in production (each ClientSession allocates an SSL
    context and a connection pool that the asyncio GC is slow to reclaim).

    'uri'      -- NTFY topic URI (e.g. 'https://ntfy.sh/FooBar')
    'title'    -- Notification title
    'message'  -- Notification body
    'emoji'    -- Tag emoji(s)
    'priority' -- NTFY priority string
    """
    headers = {
        'Title':    title,
        'Tags':     emoji,
        'Priority': priority,
    }
    try:
        auth = aiohttp.BasicAuth(username, password)
        async with ntfy_session.post(uri, headers=headers, data=message, auth=auth) as response:
            if response.status != 200:
                logging.error("[NTFY] Failed to send notification -- HTTP status `%s`", response.status)
            else:
                logging.debug("[NTFY] Notification sent successfully")
    except aiohttp.ClientError as e:
        logging.error("[NTFY] HTTP request error: %s", e)
    except Exception as e:
        logging.error("[NTFY] Unexpected error: %s", e)


async def charging_start(vehicle):
    """
    Send a charging-start payload to RenaultAPI.

    Soft vehicle-state exceptions (ChargeModeInProgressException,
    PrivacyModeOnException, NotSupportedException) are handled here so
    callers don't need to duplicate that logic. All other exceptions
    (network errors, auth errors) propagate upward to the main loop.
    """
    try:
        response = await vehicle.set_charge_start()
        logging.debug("[CHARGING_START] Sent charging-start request")
        return response

    except ChargeModeInProgressException:
        # A charge mode change is already underway -- not an error, just wait
        logging.debug("[CHARGING_START] Charge mode change already in progress, skipping")

    except PrivacyModeOnException:
        logging.warning("[CHARGING_START] Cannot start charging: privacy mode is ON")

    except NotSupportedException:
        logging.error("[CHARGING_START] Charging start is not supported for this vehicle model")

    except (AccessDeniedException, ForbiddenException) as e:
        # These can be transient on Renault's side
        logging.warning("[CHARGING_START] Access issue (may be transient): %s", e)

    # NotAuthenticatedException, network errors, etc. propagate to the main loop


async def hvac_start(vehicle):
    """
    Send a hvac-start payload to RenaultAPI.

    Same soft-exception handling policy as charging_start().
    """
    try:
        response = await vehicle.session.set_vehicle_action(
            account_id=vehicle.account_id,
            vin=vehicle.vin,
            endpoint="actions/hvac-start",
            attributes={'action': 'start'},
        )
        logging.debug("[HVAC_START] Sent hvac-start request")
        return response

    except ChargeModeInProgressException:
        logging.debug("[HVAC_START] Charge mode change in progress, skipping HVAC start")

    except PrivacyModeOnException:
        logging.warning("[HVAC_START] Cannot start HVAC: privacy mode is ON")

    except NotSupportedException:
        logging.error("[HVAC_START] HVAC start not supported for this vehicle model")

    except (AccessDeniedException, ForbiddenException) as e:
        logging.warning("[HVAC_START] Access issue (may be transient): %s", e)

    # All other exceptions propagate upward


async def create_vehicle(ntfy_session, account, config_vehicle, vehicle_nickname):
    """
    Run vehicle monitoring as a long-lived asyncio task.

    Transient API errors (privacy mode, quota, upstream issues) are caught
    inside the polling loop and cause a short sleep + retry instead of
    crashing the task. Hard errors (EndpointNotAvailableError) stop the
    task for this vehicle. Auth errors propagate up to main() so it can
    trigger a re-login.

    'ntfy_session'     -- Shared aiohttp.ClientSession for NTFY calls
    'account'          -- Kamereon account object
    'config_vehicle'   -- Per-vehicle config dictionary
    'vehicle_nickname' -- Human-readable name from config file
    """
    try:
        vehicle       = await account.get_api_vehicle(config_vehicle['VIN'])
        ntfy_uri      = config_vehicle['NTFY_topic']
        ntfy_username = config_vehicle['NTFY_auth']['username']
        ntfy_password = config_vehicle['NTFY_auth']['password']

        status_checkers = {
            'battery_percentage_checked': [],
            'charge_dict': {
                'count':    0,
                'hvac':     False,
                'notified': False,
            },
            'battery_temp_notified':    False,
            'battery_charged_notified': False,
        }

        while True:
            # --- Fetch battery status with per-exception retry logic ---
            try:
                battery_status = await vehicle.get_battery_status()

            except PrivacyModeOnException:
                # Privacy mode prevents data retrieval -- not a crash, just wait
                logging.warning("[%s] Privacy mode is ON -- cannot retrieve battery status, "
                                "retrying in 5 min", vehicle_nickname)
                await asyncio.sleep(5 * 60)
                continue

            except (AccessDeniedException, ForbiddenException,
                    InvalidUpstreamException, ResourceNotFoundException) as e:
                logging.warning("[%s] Transient API error getting battery status: %s "
                                "-- retrying in %ds", vehicle_nickname, e, WAIT_TRANSIENT)
                await asyncio.sleep(WAIT_TRANSIENT)
                continue

            except QuotaLimitException:
                logging.warning("[%s] Quota limit hit -- retrying in %ds",
                                vehicle_nickname, WAIT_QUOTA)
                await asyncio.sleep(WAIT_QUOTA)
                continue

            except EndpointNotAvailableError as e:
                # The battery status endpoint is not supported for this vehicle model.
                # No point retrying -- stop monitoring this vehicle.
                logging.error("[%s] Battery status endpoint unavailable for this model: %s "
                              "-- stopping task", vehicle_nickname, e)
                return

            # NotAuthenticatedException, GigyaException, and network errors
            # intentionally propagate upward so main() can trigger a re-login.

            # --- Parse battery values ---
            battery_percentage   = battery_status.batteryLevel
            battery_plugged      = battery_status.plugStatus
            battery_temperature  = battery_status.batteryTemperature
            battery_not_charging = battery_status.chargingStatus < 1.0

            logging.debug("[%s] New car loop check:\n"
                          "battery_percentage   - %s%%\n"
                          "battery_plugged      - %s\n"
                          "battery_temperature  - %s\n"
                          "battery_not_charging - %s\n",
                          vehicle_nickname,
                          battery_percentage,
                          battery_plugged,
                          battery_temperature,
                          battery_not_charging)

            # Renault API can return None for these -- see bug report
            # https://github.com/TheRealOne78/Zegra-server/issues/1
            has_none = False
            for name, val in (("battery_percentage",   battery_percentage),
                              ("battery_plugged",      battery_plugged),
                              ("battery_not_charging", battery_not_charging)):
                if type(val) is NoneType:
                    logging.warning("[%s] Value for `%s' is `%s', retrying in 3 min",
                                    vehicle_nickname, name, type(val))
                    await asyncio.sleep(3 * 60)
                    has_none = True
                    break

            if has_none:
                del battery_status
                continue

            ## --- Low battery check ---
            if battery_percentage <= config_vehicle['warn_battery_percentage'] \
               and not battery_plugged \
               and 'min' not in status_checkers['battery_percentage_checked']:

                if battery_percentage <= config_vehicle['min_battery_percentage']:
                    title    = f"[{vehicle_nickname}] NIVEL BATERIE CRITIC!"
                    message  = f"Nivelul bateriei a '{vehicle_nickname}' este critic - {battery_percentage}%"
                    emoji    = "red_square"
                    priority = "urgent"
                    await send_ntfy_notification(ntfy_session, ntfy_uri, ntfy_username, ntfy_password,
                                                 title, message, emoji, priority)
                    status_checkers['battery_percentage_checked'].append('min')
                    logging.debug("[%s] NTFY alerted for very low battery - %s%%",
                                  vehicle_nickname, battery_percentage)

                elif 'warn' not in status_checkers['battery_percentage_checked']:
                    title    = f"[{vehicle_nickname}] Nivel baterie scazut!"
                    message  = f"Nivelul bateriei a '{vehicle_nickname}' este scazut - {battery_percentage}%"
                    emoji    = "warning"
                    priority = "high"
                    await send_ntfy_notification(ntfy_session, ntfy_uri, ntfy_username, ntfy_password,
                                                 title, message, emoji, priority)
                    status_checkers['battery_percentage_checked'].append('warn')
                    logging.debug("[%s] NTFY warned for low battery - %s%%",
                                  vehicle_nickname, battery_percentage)

            elif battery_plugged:
                # Charger plugged in -- reset low-battery alerts regardless of level
                status_checkers['battery_percentage_checked'].clear()
                logging.debug("[%s] Cleared 'battery_percentage_checked' status checker",
                              vehicle_nickname)

            ## --- Charging stopped check ---
            if battery_plugged and battery_percentage < 98:
                status_checkers['battery_charged_notified'] = False

                if battery_not_charging:
                    if status_checkers['charge_dict']['count'] <= config_vehicle['max_tries']:
                        await charging_start(vehicle)
                        status_checkers['charge_dict']['count'] += 1
                        logging.debug("[%s] Executed charging_start(), count at %s - %s%%",
                                      vehicle_nickname,
                                      status_checkers['charge_dict']['count'],
                                      battery_percentage)

                    elif not status_checkers['charge_dict']['hvac']:
                        await hvac_start(vehicle)
                        status_checkers['charge_dict']['hvac'] = True
                        logging.debug("[%s] HVAC started because charging_start() failed %s times - %s%%",
                                      vehicle_nickname,
                                      status_checkers['charge_dict']['count'],
                                      battery_percentage)

                    elif not status_checkers['charge_dict']['notified']:
                        title    = f"[{vehicle_nickname}] EV REFUZA SA SE INCARCE!"
                        message  = f"Vehiculul '{vehicle_nickname}' refuza sa se incarce - {battery_percentage}%"
                        emoji    = "electric_plug"
                        priority = "min"
                        await send_ntfy_notification(ntfy_session, ntfy_uri, ntfy_username, ntfy_password,
                                                     title, message, emoji, priority)
                        status_checkers['charge_dict']['notified'] = True
                        logging.debug("[%s] NTFY alerted for car refusing to charge - %s%%",
                                      vehicle_nickname, battery_percentage)

            elif battery_percentage >= 98:
                # Fully charged -- reset all charging state
                status_checkers['charge_dict']['count']    = 0
                status_checkers['charge_dict']['hvac']     = False
                status_checkers['charge_dict']['notified'] = False
                logging.debug("[%s] Cleared charge_dict status checkers", vehicle_nickname)

                if battery_plugged and not status_checkers['battery_charged_notified']:
                    title    = f"[{vehicle_nickname}] EV s-a incarcat"
                    message  = f"Vehiculul '{vehicle_nickname}' este incarcat - {battery_percentage}%"
                    emoji    = "white_check_mark"
                    priority = "default"
                    await send_ntfy_notification(ntfy_session, ntfy_uri, ntfy_username, ntfy_password,
                                                 title, message, emoji, priority)
                    status_checkers['battery_charged_notified'] = True
                    logging.debug("[%s] NTFY notified for fully charged car - %s%%",
                                  vehicle_nickname, battery_percentage)

            ## --- Battery temperature check ---
            if type(battery_temperature) is not NoneType:
                if battery_temperature > config_vehicle['max_battery_temperature'] \
                   and not status_checkers['battery_temp_notified']:
                    title    = f"[{vehicle_nickname}] TEMPERATURA BATERIE RIDICATA!"
                    message  = (f"Vehiculul '{vehicle_nickname}' are temperatura bateriei "
                                f"foarte mare - {battery_temperature} deg")
                    emoji    = "stop_sign"
                    priority = "urgent"
                    await send_ntfy_notification(ntfy_session, ntfy_uri, ntfy_username, ntfy_password,
                                                 title, message, emoji, priority)
                    status_checkers['battery_temp_notified'] = True
                    logging.debug("[%s] NTFY alerted for battery temperature too high - %s deg",
                                  vehicle_nickname, battery_temperature)

                # Only clear after temperature drops to max - 3 deg to avoid flapping
                elif battery_temperature - 3 <= config_vehicle['max_battery_temperature']:
                    status_checkers['battery_temp_notified'] = False
                    logging.debug("[%s] Cleared battery_temp_notified status checker",
                                  vehicle_nickname)

            # Explicitly release the response object so the GC can reclaim it
            # before the next sleep interval, rather than waiting for the next
            # loop assignment to drop the reference.
            del battery_status

            await asyncio.sleep(config_vehicle['check_time'] * 60)

    except asyncio.CancelledError:
        logging.warning("[%s] Task cancelled", vehicle_nickname)
        raise


async def http_request_handler(request, ntfy_session, account, config_dict):
    """
    Handle POST requests from http_hvac_listener().

    Starts HVAC for the named vehicle if battery > 30%, otherwise sends a
    NTFY alert explaining why it was skipped.
    """
    try:
        data             = await request.json()
        vehicle_nickname = data.get('Name')

        if vehicle_nickname not in config_dict['Cars']:
            return aiohttp.web.json_response(
                {'success': False, 'message': 'Vehicle name not found in the JSON config file!'},
                status=404)

        vehicle        = await account.get_api_vehicle(config_dict['Cars'][vehicle_nickname]['VIN'])
        battery_status = await vehicle.get_battery_status()

        if battery_status.batteryLevel > 30:
            await hvac_start(vehicle)
            return aiohttp.web.json_response({'success': True})

        # Battery too low to start HVAC -- notify via NTFY
        ntfy_uri      = config_dict['Cars'][vehicle_nickname]['NTFY_topic']
        ntfy_username = config_dict['Cars'][vehicle_nickname]['NTFY_auth']['username']
        ntfy_password = config_dict['Cars'][vehicle_nickname]['NTFY_auth']['password']
        title         = f"[{vehicle_nickname}] AC nu a pornit"
        message       = (f"Vehiculul '{vehicle_nickname}' nu are suficienta baterie (sub 30%) "
                         f"ca sa poata porni AC - {battery_status.batteryLevel}%")
        await send_ntfy_notification(ntfy_session, ntfy_uri, ntfy_username, ntfy_password,
                                     title, message, "battery", "default")
        return aiohttp.web.json_response(
            {'success': False, 'message': 'Not enough battery to start AC (< 30%)'},
            status=403)

    except asyncio.CancelledError:
        logging.warning("HTTP request handler cancelled")
        raise

    except PrivacyModeOnException as e:
        logging.warning("HVAC request rejected -- privacy mode is ON: %s", e)
        return aiohttp.web.json_response(
            {'success': False, 'message': 'Privacy mode is ON'}, status=503)

    except (AccessDeniedException, ForbiddenException) as e:
        logging.warning("HVAC request rejected -- access denied (may be transient): %s", e)
        return aiohttp.web.json_response(
            {'success': False, 'message': str(e)}, status=503)

    except NotSupportedException as e:
        logging.error("HVAC not supported for this vehicle model: %s", e)
        return aiohttp.web.json_response(
            {'success': False, 'message': str(e)}, status=501)

    except Exception as e:
        logging.exception("Unexpected error handling HTTP request: %s", e)
        return aiohttp.web.json_response(
            {'success': False, 'message': str(e)}, status=500)


async def http_hvac_listener(ntfy_session, account, config_dict, port=HVAC_HTTP_LISTENER_PORT):
    """Listen for POST requests and forward them to http_request_handler()."""
    runner = None
    site   = None
    try:
        app = aiohttp.web.Application()
        app.router.add_post('/', lambda request: http_request_handler(
            request, ntfy_session, account, config_dict))

        runner = aiohttp.web.AppRunner(app)
        await runner.setup()

        site = aiohttp.web.TCPSite(runner, 'localhost', port)
        await site.start()

        logging.info("HTTP HVAC listener started at http://localhost:%s", port)
        await asyncio.Event().wait()

    except asyncio.CancelledError:
        logging.info("HTTP HVAC listener cancelled")
        raise
        # Always clean up, even if site.start() raised before completing
        if site is not None:
            await site.stop()
        if runner is not None:
            await runner.cleanup()


async def init_logger(debug=False):
    """
    Set up file + console logging handlers.

    The existing log file is renamed to .old *before* the new handler
    opens it, so the rename is never a no-op.
    """
    if os.path.isfile(LOG_FILE_PATH):
        os.rename(LOG_FILE_PATH, LOG_FILE_PATH + '.old')

    file_handler    = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
    console_handler = logging.StreamHandler()

    file_handler.setLevel(logging.DEBUG)
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname).1s] %(funcName)s(): %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logging.root.addHandler(file_handler)
    logging.root.addHandler(console_handler)
    logging.root.setLevel(logging.DEBUG if debug else logging.INFO)


async def do_login(client, config_dict):
    """
    Authenticate with Gigya using credentials from the config file.

    With FileCredentialStore, if the stored JWT is still valid the library
    skips the actual Gigya network call automatically. A round-trip to
    Gigya only happens when the token is absent or expired.
    """
    await client.session.login(
        config_dict['renault_auth']['email'],
        config_dict['renault_auth']['password'],
    )


async def main():
    """
    Entry point. Parses arguments, sets up logging, and runs the main loop.

    Architecture overview
    ---------------------
    Two long-lived aiohttp sessions are created once and reused for the
    entire process lifetime:

      ntfy_session    -- for all NTFY push notification POSTs
      renault_session -- for all Kamereon / Gigya API calls

    Previously, send_ntfy_notification created a brand-new ClientSession
    (and therefore a new TCPConnector + SSL context) on *every single call*.
    With one vehicle checking every few minutes plus occasional reconnects,
    these dead connectors accumulated faster than the asyncio GC reclaimed
    them, causing the multi-GB memory growth observed in production.

    Login tokens are persisted to CREDENTIAL_STORE_PATH via
    FileCredentialStore. On a systemd midnight restart, valid tokens are
    reloaded from disk and the Gigya login round-trip is skipped entirely,
    reducing startup latency and avoiding unnecessary load on Renault's
    auth servers.

    Re-login within a running session only occurs when the main loop
    receives NotAuthenticatedException or GigyaException -- not on every
    transient connection hiccup.

    Signal handling
    ---------------
    SIGINT and SIGTERM are caught via loop.add_signal_handler(). Both
    signals cancel all running tasks, which causes asyncio.gather() to
    raise CancelledError. That propagates out of the while loop and is
    caught at the top level, logging a clean shutdown message instead of
    printing a traceback.
    """

    config_dict = ""
    port        = HVAC_HTTP_LISTENER_PORT
    debug       = False

    opts, args = getopt.getopt(sys.argv[1:], "hvDc:p:",
                               ['help', 'version', 'debug', 'config=', 'port='])
    has_arg = {'config_dict': False, 'port': False}

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            await print_help()
            sys.exit(0)
        elif opt in ('-v', '--version'):
            await print_version()
            sys.exit(0)
        elif opt in ('-D', '--debug'):
            debug = True
        elif opt in ('-c', '--config'):
            config_dict = await get_config(arg)
            has_arg['config_dict'] = True
        elif opt in ('-p', '--port'):
            port = int(arg)
            has_arg['port'] = True

    if not has_arg['config_dict']:
        config_dict = await get_config()

    if config_dict.get('debug'):
        debug = True

    if 'http_hvac_listener_port' in config_dict and not has_arg['port']:
        port = config_dict['http_hvac_listener_port']

    await init_logger(debug=debug)

    admin_ntfy_uri      = config_dict['NTFY_admin']['NTFY_topic']
    admin_ntfy_username = config_dict['NTFY_admin']['NTFY_auth']['username']
    admin_ntfy_password = config_dict['NTFY_admin']['NTFY_auth']['password']

    # Ensure the config directory exists for the credential store file
    os.makedirs(os.path.dirname(os.path.abspath(CREDENTIAL_STORE_PATH)), exist_ok=True)

    # --- Long-lived sessions (one allocation, used for the entire process) ---
    async with aiohttp.ClientSession() as ntfy_session, \
               aiohttp.ClientSession() as renault_session:

        await send_ntfy_notification(
            ntfy_session,
            admin_ntfy_uri, admin_ntfy_username, admin_ntfy_password,
            f"[Server starting] Starting {PROJECT_NAME} server ...",
            f"[{datetime.today().strftime('%Y/%m/%d - %H:%M:%S')}] "
            f"The {PROJECT_NAME} server is starting ...",
            "checkered_flag", "min")

        # Build the Renault client backed by a persistent token store.
        # After the first successful login, Gigya and Kamereon JWTs are
        # written to CREDENTIAL_STORE_PATH. On the next systemd restart,
        # the library reloads them and skips the Gigya round-trip if
        # the tokens haven't expired yet.
        credential_store = FileCredentialStore(CREDENTIAL_STORE_PATH)
        client = RenaultClient(
            websession=renault_session,
            locale=config_dict['locale'],
            credential_store=credential_store,
        )

        # Initial login -- may be a no-op if a valid token already exists on disk
        await do_login(client, config_dict)
        logging.info("Logged in to Renault API")

        # Account object is stable for the process lifetime -- fetch it once
        account_person_data = await client.get_person()
        account_id          = account_person_data.accounts[0].accountId
        #TODO:FIXME: Implement accounts for both MyDacia and MyRenault instead of whatever comes first
        account = await client.get_api_account(account_id)

        # --- Signal handling ---
        # tasks is defined here so the signal handler closure can always
        # reference the current list, even as it is replaced each loop iteration.
        tasks = []
        loop  = asyncio.get_running_loop()

        def _signal_handler(sig):
            logging.info("Received signal %s -- cancelling tasks for graceful shutdown", sig.name)
            for task in tasks:
                task.cancel()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler, sig)

        # --- Main retry loop ---
        try:
            while True:
                tasks = []
                try:
                    vehicles = await account.get_vehicles()

                    if str(vehicles.errors) != 'None':
                        logging.warning("Got vehicle errors: %s -- retrying in %ds",
                                        vehicles.errors, WAIT_TRANSIENT)
                        await asyncio.sleep(WAIT_TRANSIENT)
                        continue

                    # Validate VINs from config against those on the Renault account
                    renault_vins = [link['vin'] for link in vehicles.raw_data['vehicleLinks']]
                    invalid_vin = False
                    for vehicle_name in config_dict['Cars']:
                        if config_dict['Cars'][vehicle_name]['VIN'] not in renault_vins:
                            logging.error("[main] `%s` is missing in the Renault/Dacia account!",
                                          config_dict['Cars'][vehicle_name]['VIN'])
                            invalid_vin = True
                    if invalid_vin:
                        sys.exit(1)

                    # One asyncio task per vehicle
                    for vehicle_entry in config_dict['Cars']:
                        tasks.append(asyncio.create_task(
                            create_vehicle(ntfy_session, account,
                                           config_dict['Cars'][vehicle_entry], vehicle_entry)
                        ))

                    # One task for the HTTP HVAC listener
                    tasks.append(asyncio.create_task(
                        http_hvac_listener(ntfy_session, account, config_dict, port)
                    ))

                    await asyncio.gather(*tasks)

                # --- Signal-driven cancellation: exit the retry loop cleanly ---
                except asyncio.CancelledError:
                    logging.info("Shutdown signal received -- stopping")
                    await cancel_tasks(tasks)
                    raise  # propagate out of while True to the outer try

                # --- Transient network / upstream errors: cancel, sleep, retry ---
                except (aiohttp.ClientConnectionError,
                        aiohttp.ClientResponseError,
                        aiohttp.ClientPayloadError,
                        aiohttp.ClientError,
                        asyncio.TimeoutError,
                        FailedForwardException,
                        InvalidUpstreamException) as e:

                    logging.warning("Transient connection error (retrying in %ds): %s",
                                    WAIT_TRANSIENT, e)
                    await cancel_tasks(tasks)
                    await asyncio.sleep(WAIT_TRANSIENT)
                    continue

                # --- Access / permission errors: slightly longer wait, then retry ---
                except (AccessDeniedException, ForbiddenException) as e:
                    logging.warning("Access denied error (retrying in %ds): %s",
                                    WAIT_FORBIDDEN, e)
                    await cancel_tasks(tasks)
                    await asyncio.sleep(WAIT_FORBIDDEN)
                    continue

                # --- Quota exhausted: wait longer before hammering the API again ---
                except QuotaLimitException as e:
                    logging.warning("Quota limit exceeded (retrying in %ds): %s",
                                    WAIT_QUOTA, e)
                    await cancel_tasks(tasks)
                    await asyncio.sleep(WAIT_QUOTA)
                    continue

                # --- Auth errors: re-login, then continue the main loop ---
                except (NotAuthenticatedException, GigyaException) as e:
                    # Use a longer wait for credential errors to avoid triggering
                    # Gigya's rate-limiter (which can temporarily ban the account)
                    wait = WAIT_AUTH if isinstance(e, InvalidCredentialsException) else WAIT_TRANSIENT
                    logging.warning("Authentication error (re-logging in after %ds): %s", wait, e)
                    await cancel_tasks(tasks)
                    await asyncio.sleep(wait)
                    try:
                        await do_login(client, config_dict)
                        logging.info("Re-login successful")
                    except Exception as login_err:
                        # Login itself failed -- log and let the next iteration retry
                        logging.error("Re-login attempt failed: %s -- will retry next cycle", login_err)
                    continue

                # --- Unexpected / fatal errors: notify admin and shut down ---
                except Exception as e:
                    logging.error("[SERVER SHUTDOWN] Unexpected error: %s", e)

                    await send_ntfy_notification(
                        ntfy_session,
                        admin_ntfy_uri, admin_ntfy_username, admin_ntfy_password,
                        "[SERVER SHUTDOWN] Unexpected error - SHUTTING DOWN",
                        ("[SERVER SHUTDOWN] An unexpected error occurred\n\n"
                         "**********************\n"
                         f"{e}\n"
                         "**********************\n\n"
                         f"[{datetime.today().strftime('%Y/%m/%d - %H:%M:%S')}] "
                         "Shutting down the server!"),
                        "computer", "urgent")

                    await cancel_tasks(tasks)
                    sys.exit(1)

        except asyncio.CancelledError:
            logging.info("Shutdown complete")


### START ###
if __name__ == "__main__":
    asyncio.run(main())
