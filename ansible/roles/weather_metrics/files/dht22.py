#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
#
# Ansible managed
r"""
Weather Metrics script.

Read Sensor metrics, output to stdout (CSV format) and optionally post them to ThingSpeak.
Logs to syslog but if there is an error it will also start logging to stderr.
Since this is intended to be called from cron if there are messages to stderr an e-mail alert will be generated.
That way if an e-mail alert is send (only upon errors) we will receive all logs send to stderr, including the final success status if any.

An additional GPIO port can be used to control the power of the sensor.
This is optional but it solves an occasional issue with this sensor. Sometimes the sensor returns Nan values until it is powered off and on again. Restarting Raspberry won’t help in this case since the 5V GPIO pin will remain on during the power cycle.

Configuration file:
Load options from the first yaml file found (dht22.yml, /usr/local/etc/dht22.yml).

If Power control port is used:
Optionally the below cron job will configure the Power control port.
Otherwise the script will power on the sensor upon first run.
@reboot /usr/bin/gpio -g mode <GPIO_Powerctl_Port> output && /usr/bin/gpio -g write <GPIO_Powerctl_Port> 1

Crontab entry that runs the script every 10 minutes and appends stdout to a monthly file:
*/10 * * * * : Weather_Metrics ; /usr/local/bin/dht.py 1>>/var/local/dht22/$(/bin/date +\%Y\%m).csv

"""

import sys
import time
import datetime
import logging
import logging.handlers
import Adafruit_DHT
import sys
import RPi.GPIO as GPIO
import urllib.request
import urllib.error
import yaml
from pprint import pprint

CONFIG_FILE = ("dht22.yml", "/usr/local/etc/dht22.yml") #Get configuration options from the first file found.

# Python version check
assert sys.version_info.major == 3 and sys.version_info.minor >= 6, \
        "Running Python version: {}.{}. Requires Python 3.6 or higher!.".format(sys.version_info.major, sys.version_info.minor)

def get_config(config_files):
    r"""
    Load configuration options from the first yaml file that exists in config_files (tuple) argument and return a config dict.
    Valid WEATHER_METRICS['sensor'] values:(DHT11, DHT22, AM2302).
    """
    cfg = {}
    # Main configuration.
    for conf_file in config_files:
        try:
            with open(conf_file, 'r') as cfgfile: cfg = yaml.load(cfgfile)
            break
        except FileNotFoundError: pass

    cfg['WEATHER_METRICS']['SENSOR'] = getattr(Adafruit_DHT, cfg['WEATHER_METRICS']['sensor'])
    return cfg


class LoggingSyslogStderr():
    """
    Log to Syslog and if any error is raised start logging to stderr as well.

    Class Variables:
    ----------------
    DEFAULT_LOGGING_OPTIONS (dict):
        A dict containing defaults for the following options as keys:
        syslog_logformat (str): Logformat for syslog.
            Default: '%(module)s:[%(levelname)8s]: %(message)s'
        syslog_level (str): Syslog min level (name).
            Default: 'INFO'
        syslog_facility (str): Syslog facility.
            Default: 'LOG_LOCAL1'
        stderr_logformat (str): Logformat for stderr logging.
            Default: '%(asctime)s [%(levelname)8s]: %(message)s'
        stderr_level (str): stderr min level (name).
            Default: 'INFO'
        stderr_always (boolean): Output to stderr always, regardless of option stderr_on_errors.
            Default: False
        stderr_on_errors (boolean): Output to stderr only after an error is raised. 
            Otherwise don't output anything unless options stderr_always is enabled.
            Default: True


        For other available options refer to python documentation for logging modules.
        (e.g. Classes: logging.Formatter, logging.LogRecord, logging.handlers.SysLogHandler).

    Logging Methods:
    ---------------
    info(msg): Logs msg with level name INFO
    error(msg): Logs msg with level name ERROR and set instance variable errors_raised to True.
    debug(msg): Logs msg with level name DEBUG
    warning(msg): Logs msg with level name WARNING

    """

    DEFAULT_LOGGING_OPTIONS = {
        'syslog_logformat'  : '%(module)s:[%(levelname)8s]: %(message)s',
        'syslog_level'      : 'INFO',
        'syslog_facility'   : 'LOG_LOCAL1',
        'stderr_logformat'  : '%(asctime)s [%(levelname)8s]: %(message)s',
        'stderr_level'      : 'INFO',
        'stderr_always'     : False,
        'stderr_on_errors'  : True
    }

    def __init__(self, logging_options=None, name=None):
        """
        Set logger and handlers for syslog and stderr logging.
        Initialize errors_raised attribute to keep track if an error is raised.

        Keyword Arguments:
        -----------------
        logging_options (dict, optional): Same as DEFAULT_LOGGING_OPTIONS class attribute.
            If not provided here copy the DEFAULT_LOGGING_OPTIONS dict.
        name (str, optional):
            logger name to set. Otherwise passes __name__
            It can also be added to syslog_logformat as %(name)s.

        """

        if logging_options and isinstance(logging_options, dict):
            self.logging_options = {dkey: logging_options.get(dkey,dvalue) for dkey, dvalue in LoggingSyslogStderr.DEFAULT_LOGGING_OPTIONS.items()}
        else:
            self.logging_options = {dkey: dvalue for dkey, dvalue in LoggingSyslogStderr.DEFAULT_LOGGING_OPTIONS.items()}

        # We dont want to output to stderr until there is an error raised.
        self.errors_raised = False

        # Convert text options to the corresponding logging attributes.
        self.logging_options['syslog_level'] = getattr(logging, self.logging_options['syslog_level'])
        self.logging_options['syslog_facility'] = getattr(logging.handlers.SysLogHandler, self.logging_options['syslog_facility'])
        self.logging_options['stderr_level'] = getattr(logging, self.logging_options['stderr_level'])

        # Configure logger
        if name: self.logger = logging.getLogger(name)
        else: self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Syslog handler
        self.syslog_handler = logging.handlers.SysLogHandler(address='/dev/log', facility=self.logging_options['syslog_facility'])
        self.syslog_handler.setLevel(self.logging_options['syslog_level'])
        self.syslog_handler.setFormatter(logging.Formatter(self.logging_options['syslog_logformat']))
        self.logger.addHandler(self.syslog_handler)

        # Stderr handler
        self.stderr_handler = logging.StreamHandler(sys.stderr)
        self.stderr_handler.setLevel(self.logging_options['stderr_level'])
        self.stderr_handler.setFormatter(logging.Formatter(self.logging_options['stderr_logformat']))
        if not self.logging_options['stderr_always']: self.stderr_handler.addFilter(self._filter_stderr_messages)
        self.logger.addHandler(self.stderr_handler)


    def _filter_stderr_messages(self, record):
        """
        Filter stderr messages.
        This filter is added to stderr handler by __init__() unless stderr_always is enabled.
        Accepts log record argument as per standard record filter method but is not used here.
        Returns True only if option stderr_on_errors is enabled and instance variable errors_raised is set to true.

        """
        if self.logging_options['stderr_on_errors'] and self.errors_raised: return True
        return False

    def info(self, msg): self.logger.info(msg)
    def error(self, msg):
        self.errors_raised = True
        self.logger.error(msg)
    def debug(self, msg): self.logger.debug(msg)
    def warning(self, msg): self.logger.warning(msg)


class Weather_Metrics():
    """
    Class for reading Sensor data.

    Public Methods: get_sensor_data.

    Public Read-Only Properties:
    ---------------------------
    sensor_read_time_utc: return _sensor_read_time_utc
    sensor_humidity: return _humidity
    sensor_temperature: return _temperature
    valid_sensor_read: return _valid_sensor_read
    sensor_read_elapsed: return _sensor_read_elapsed
    total_process_time: return _total_process_time

    """
    def __init__(self, weather_metrics_options=None, logger=None):
        """
        Initialize Weather_Metrics object. Call __init_powerctl_port()

        Keyword Arguments:
        -----------------
        weather_metrics_options (dict): Weather Metrics Options dict.
        logger (obj, optional): logger object to use for logging. If not provided call logging.getLogger(__name__)


        Private Attributes:
        ----------
        _sensor_read_time_utc (datetime obj) (UTC): Timestamp of last sensor read
        _humidity (Float): Humidity value
        _temperature (Float): Temperature value
        _valid_sensor_read (bool): True if last read was successful
        _sensor_read_elapsed (Float): Duration of Sensor read
        _total_process_time (Float): Total process duration to retrieve Sensor data (including delays of retries).

        """
        if logger: self.log = logger
        else: self.log = logging.getLogger(__name__)

        self.wmoptions = {dkey: dvalue for dkey, dvalue in weather_metrics_options.items()}

        self._sensor_read_time_utc = None
        self._humidity = None
        self._temperature = None
        self._valid_sensor_read = None
        self._sensor_read_elapsed = None
        self._total_process_time = None

        if self.wmoptions['GPIO_Powerctl_Port']: self.__init_powerctl_port()

    @property
    def sensor_read_time_utc(self): return self._sensor_read_time_utc

    @property
    def sensor_humidity(self): return self._humidity

    @property
    def sensor_temperature(self): return self._temperature

    @property
    def valid_sensor_read(self): return self._valid_sensor_read

    @property
    def sensor_read_elapsed(self): return self._sensor_read_elapsed

    @property
    def total_process_time(self): return self._total_process_time


    def __init_powerctl_port(self):
        r"""
        If Power control port is enabled then set Powerctl_Port to OUTPUT and HIGH.
        Only called once upon instance initialization.

        Uses GPIO module and sets GPIO mode to BCM. Valid GPIO modes: {-1:"Unset", 11:"BCM", 10:"BOARD"}
        """
        if self.wmoptions['GPIO_Powerctl_Port']:
            if GPIO.getmode() is None or GPIO.getmode() != 11:
                self.log.debug("Setting GPIO mode to BCM")
                GPIO.setmode(GPIO.BCM)

            self.log.debug("GPIO: disable warnings")
            GPIO.setwarnings(False)

            if GPIO.gpio_function(self.wmoptions['GPIO_Powerctl_Port']):
                self.log.warning(f"GPIO: Power control Port: {self.wmoptions['GPIO_Powerctl_Port']} is set to IN")

            self.log.debug(f"GPIO: Set Power control Port: {self.wmoptions['GPIO_Powerctl_Port']} to OUT")
            GPIO.setup(self.wmoptions['GPIO_Powerctl_Port'], GPIO.OUT)

            if not GPIO.input(self.wmoptions['GPIO_Powerctl_Port']):
                self.log.warning(f"GPIO: {self.wmoptions['GPIO_Powerctl_Port']} is set to Low. Setting to High...")
                GPIO.output(self.wmoptions['GPIO_Powerctl_Port'], GPIO.HIGH)
                self.log.debug(f"Sleeping for {self.wmoptions['POWERCTL_PORT_SET_HIGH_SLEEP_TIME']} seconds after powering on the sensor...")
                time.sleep(self.wmoptions['POWERCTL_PORT_SET_HIGH_SLEEP_TIME'])

        return

    def __reset_sensor(self):
        """
        If Power control port is enabled then power cycle the sensor.
        """
        if self.wmoptions['GPIO_Powerctl_Port']:
            self.log.warning('Resseting Sensor...')

            # Power Off
            self.log.warning(f"Setting GPIO: {self.wmoptions['GPIO_Powerctl_Port']} to Low...")
            GPIO.output(self.wmoptions['GPIO_Powerctl_Port'], GPIO.LOW)
            self.log.debug(f"Sleeping for {self.wmoptions['POWERCTL_PORT_SET_LOW_SLEEP_TIME']} seconds after powering off the sensor...")
            time.sleep(self.wmoptions['POWERCTL_PORT_SET_LOW_SLEEP_TIME'])

            # Power on
            self.log.warning(f"Setting GPIO: {self.wmoptions['GPIO_Powerctl_Port']} to High...")
            GPIO.output(self.wmoptions['GPIO_Powerctl_Port'], GPIO.HIGH)
            self.log.debug(f"Sleeping for {self.wmoptions['POWERCTL_PORT_SET_HIGH_SLEEP_TIME']} seconds after powering on the sensor...")
            time.sleep(self.wmoptions['POWERCTL_PORT_SET_HIGH_SLEEP_TIME'])

        return

    def __read_sensor(self):
        """
        Read Sensor data and update instance attributes: _sensor_read_time_utc, _humidity, _temperature & _sensor_read_elapsed
        """
        self._sensor_read_time_utc = None
        self._humidity = None
        self._temperature = None
        self._sensor_read_elapsed = None

        tsensor0 = time.perf_counter()
        self._humidity, self._temperature = Adafruit_DHT.read_retry(self.wmoptions['SENSOR'], self.wmoptions['GPIO_Data_Port'])
        self._sensor_read_elapsed = time.perf_counter() - tsensor0
        self._sensor_read_time_utc = datetime.datetime.utcnow()
        return

    def get_sensor_data(self):
        """
        Call __read_sensor(). Validates sensor data and retries upon failure with exponential back off delays.
        Valid sensor values:
            Temperature: [-40..125]
            Humidity: [0..100]

        if Power control is used:
            If sensor returns None call __reset_sensor() at every retry.
            If sensor returns invalid values start calling __reset_sensor() after retry num.: ERR_RETRIES-2

        Updates instance attributes: _valid_sensor_read & _total_process_time

        """
        trynum = 0
        sleep_time = 3
        self._valid_sensor_read = None
        self._total_process_time = None
        tprocess0 = time.perf_counter()
        while not self._valid_sensor_read and trynum < self.wmoptions['ERR_RETRIES']:
            trynum += 1
            if trynum >= 2:
                self.log.warning(f"Try num.: {trynum}")
                sleep_time = max(3, (min((2**trynum), self.wmoptions['MAXIMUM_BACKOFF_TIME']) - round(int(self._sensor_read_elapsed or 0))))
                self.log.debug(f"Sleeping for {sleep_time} seconds")
                time.sleep(sleep_time)

            self._valid_sensor_read = None
            self.log.debug("Requesting Sensor data...")
            self.__read_sensor()
            self.log.debug(f"Sensor read elapsed time: {self._sensor_read_elapsed:.4f} seconds at: {self._sensor_read_time_utc} (UTC)")

            if self._humidity is None or self._temperature is None:
                self.log.error("Sensor didn't return anything")
                self.__reset_sensor()
            elif self._temperature < -40 or self._temperature > 125 or self._humidity < 0 or self._humidity > 100:
                self.log.error(f"Bogus values: Temperature: {self._temperature}, Humidity: {self._humidity}")
                if trynum + 2 > self.wmoptions['ERR_RETRIES']:
                    self.log.warning("Less then two retries remaining.")
                    self.__reset_sensor()
            else: self._valid_sensor_read = True

        self._total_process_time = time.perf_counter() - tprocess0
        self.log.debug(f"Total sensor read process time: {self._total_process_time:.4f} seconds - Tries: {trynum}")

        if self._valid_sensor_read:
            self.log.info(f"Success reading sensor. Temperature: {self._temperature}, Humidity: {self._humidity}")
        else: self.log.error("Could not read sensor. Aborting...")

        return self._valid_sensor_read


def thingspeak_post(metrics_time_utc, humidity, temperature, logger=None, thingspeak_options=None):
    """
    Post metrics to ThingSpeak.

    Parameters
    ----------
    metrics_time_utc (datetime obj) (UTC): Sensor read time.
    humidity (Float): Sensor humidity value.
    temperature (Float): Sensor temperature value.

    Returns
    -------
    errors (Boolean): If any errors are raised.
    """

    if not logger: logger = logging.getLogger(__name__)

    thingspeak_strf_utcnowtime = metrics_time_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    thingspeak_url= f"{thingspeak_options['THINGSPEAK_BASEURL']}&field1={str(round(float(temperature),1))}&field2={str(round(float(humidity),1))}&created_at={thingspeak_strf_utcnowtime}"

    # Post data to ThingSpeak. Retry upon failure with exponential back off delays.
    trynum = 0
    sleep_time = 3
    post_success = None
    tpost_elapsed = None
    total_process_time = None
    tprocess0 = time.perf_counter()
    while not post_success and trynum < thingspeak_options['THINGSPEAK_POST_ERR_RETRIES']:
        trynum += 1
        if trynum >= 2:
            logger.warning(f"Try num.: {trynum}")
            sleep_time = max(3, (min((2**trynum), thingspeak_options['THINGSPEAK_POST_MAXIMUM_BACKOFF_TIME']) - round(int(tpost_elapsed or 0))))
            logger.debug(f"Sleeping for {sleep_time} seconds")
            time.sleep(sleep_time)

        tpost_elapsed = None
        logger.debug("Sending metrics to ThingSpeak...")
        tpost0 = time.perf_counter()
        try:
            urlpost = urllib.request.urlopen(thingspeak_url)
            post_success = True
        except (urllib.error.URLError, urllib.error.HTTPError) as err:
            post_success = False
            # We are substiting the url if it's included in the error msg since it contains the API key.
            logger.error(f"urllib.error: {str(err).replace(thingspeak_options['THINGSPEAK_BASEURL'], '<HIDDEN_URL>')}")
        finally:
            tpost_elapsed = time.perf_counter() - tpost0
            try: urlpost.close()
            except NameError: pass

        logger.debug(f"ThingSpeak post elapsed time: {tpost_elapsed:.4f} seconds")

    total_process_time = time.perf_counter() - tprocess0
    logger.debug(f"Total ThingSpeak post Process time: {total_process_time:.4f} seconds - Tries: {trynum}")

    if post_success:
        logger.info(f"Success sending metrics to ThingSpeak: Temperature: {temperature}, Humidity: {humidity} at: {thingspeak_strf_utcnowtime} (UTC)")
    else: logger.error("Could not post metrics to ThingSpeak. Aborting...")

    return post_success


def main(argv=None):
    """
    Main function.
    Read config file, initialize custom logger and get sensor data.
    If configured post data to ThingSpeak.

    Returns script exit status.
    """

    # Get config
    cfg = get_config(CONFIG_FILE)
    return_code = None

    # Set logger
    logs = LoggingSyslogStderr(logging_options=cfg.get('LOGGING_OPTIONS',None), name='Weather_Metrics')
    logs.debug("Initialized logger")

    # Init Weather Metrics
    logs.debug("Initialize Weather Metrics")
    weather_metrics = Weather_Metrics(weather_metrics_options=cfg['WEATHER_METRICS'], logger=logs)

    # Read Sensor and if sucessfull print to stdout as csv and proceed
    logs.debug("Get Sensor data")
    if weather_metrics.get_sensor_data():
        logs.debug("Printing Weather Metrics as csv to stdout")
        print_strf_utcnowtime = weather_metrics.sensor_read_time_utc.strftime('%Y-%m-%d %H:%M:%S+00')
        print(print_strf_utcnowtime, str(round(float(weather_metrics.sensor_temperature),1)), str(round(float(weather_metrics.sensor_humidity),1)), sep=';')
        return_code = 0

        # Post metrics to ThingSpeak
        if 'THINGSPEAK' in cfg and isinstance(cfg['THINGSPEAK'], dict):
            logs.debug("Post data to ThingSpeak")
            if thingspeak_post(weather_metrics.sensor_read_time_utc, weather_metrics.sensor_humidity, weather_metrics.sensor_temperature, logs, cfg['THINGSPEAK']):
                return_code = 0
            else: return_code = 1
    else: return_code = 1

    return return_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))

