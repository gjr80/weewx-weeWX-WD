# wdwu.py
#  This program is free software; you can redistribute it and/or modify it under
#  the terms of the GNU General Public License as published by the Free Software
#  Foundation; either version 3 of the License, or (at your option) any later
#  version.
# 
#  This program is distributed in the hope that it will be useful, but WITHOUT 
#  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
#  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
#  details.
# 
#  Version: 1.2.0a1                                     Date: 8 March 2018
# 
#  Revision History
#   8 March 2018    v1.2.0
#       - initial implementation
# 

import syslog
import threading
import urllib2
import json
import time

import weewx
import weewx.manager
import weeutil.Sun 
from weewx.units import obs_group_dict

WDWU3_VERSION = '1.2.0a1'

def logmsg(level, msg):
    syslog.syslog(level, 'wdwu: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)
    
def toint(label, value_tbc, default_value):
    """ Convert value_tbc to an integer whilst handling None.
    
        If value_tbc cannot be converted to an integer default_value is returned.
        
        Input:
            label: String with the name of the parameter being set
            value_tbc: The value to be converted to an integer
            default_value: The value to be returned if value cannot be 
                           converted to an integer
        
    """
    if isinstance(value_tbc, str) and value_tbc.lower() == 'none':
        value_tbc = None
    if value_tbc is not None:
        try:
            value_tbc = int(value_tbc)
        except Exception, e:
            logerr("bad value '%s' for %s" % (value_tbc, label))
            value_tbc = default_value
    return value_tbc

def get_default_binding_dict():
    """Define a default binding dictionary."""
    
    return {'database':   'weewxwd_sqlite',
            'manager':    'weewx.manager.Manager',
            'table_name': 'conditions',
            'schema':     'user.wdwu.schema'}
    
# define schema for conditions table
schema = [('dateTime',            'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
          ('usUnits',             'INTEGER NOT NULL'),
          ('forecastIcon',        'INTEGER'),
          ('forecastText',        'VARCHAR(256)'),
          ('forecastTextMetric',  'VARCHAR(256)'),
          ('currentIcon',         'INTEGER'),
          ('currentText',         'VARCHAR(256)'),
          ('tempRecordHigh',      'REAL'),
          ('tempNormalHigh',      'REAL'),
          ('tempRecordHighYear',  'INTEGER'),
          ('tempRecordLow',       'REAL'),
          ('tempNormalLow',       'REAL'),
          ('tempRecordLowYear',   'INTEGER'),
          ('vantageForecastIcon', 'INTEGER'),
          ('vantageForecastRule', 'VARCHAR(256)'),
          ('stormRain',           'REAL'),
          ('stormStart',          'INTEGER')]

# dict to look up WU icon names and return corresponding Saratoga icon code
icon_dict = {
    'clear'             : 0,
    'cloudy'            : 18,
    'flurries'          : 25,
    'fog'               : 11,
    'hazy'              : 7,
    'mostlycloudy'      : 18,
    'mostlysunny'       : 9,
    'partlycloudy'      : 19,
    'partlysunny'       : 9,
    'sleet'             : 23,
    'rain'              : 20,
    'snow'              : 25,
    'sunny'             : 28,
    'tstorms'           : 29,
    'nt_clear'          : 1,
    'nt_cloudy'         : 13,
    'nt_flurries'       : 16,
    'nt_fog'            : 11,
    'nt_hazy'           : 13,
    'nt_mostlycloudy'   : 13,
    'nt_mostlysunny'    : 1,
    'nt_partlycloudy'   : 4,
    'nt_partlysunny'    : 1,
    'nt_sleet'          : 12,
    'nt_rain'           : 14,
    'nt_snow'           : 16,
    'nt_tstorms'        : 17,
    'chancerain'        : 20,
    'chancesleet'       : 23,
    'chancesnow'        : 25,
    'chancetstorms'     : 29
    }

# dict to look up Davis forecast rule and return forecast text
davis_fr_dict= {
        0   : 'Mostly clear and cooler.',
        1   : 'Mostly clear with little temperature change.',
        2   : 'Mostly clear for 12 hours with little temperature change.',
        3   : 'Mostly clear for 12 to 24 hours and cooler.',
        4   : 'Mostly clear with little temperature change.',
        5   : 'Partly cloudy and cooler.',
        6   : 'Partly cloudy with little temperature change.',
        7   : 'Partly cloudy with little temperature change.',
        8   : 'Mostly clear and warmer.',
        9   : 'Partly cloudy with little temperature change.',
        10  : 'Partly cloudy with little temperature change.',
        11  : 'Mostly clear with little temperature change.',
        12  : 'Increasing clouds and warmer. Precipitation possible within 24 to 48 hours.',
        13  : 'Partly cloudy with little temperature change.',
        14  : 'Mostly clear with little temperature change.',
        15  : 'Increasing clouds with little temperature change. Precipitation possible within 24 hours.',
        16  : 'Mostly clear with little temperature change.',
        17  : 'Partly cloudy with little temperature change.',
        18  : 'Mostly clear with little temperature change.',
        19  : 'Increasing clouds with little temperature change. Precipitation possible within 12 hours.',
        20  : 'Mostly clear with little temperature change.',
        21  : 'Partly cloudy with little temperature change.',
        22  : 'Mostly clear with little temperature change.',
        23  : 'Increasing clouds and warmer. Precipitation possible within 24 hours.',
        24  : 'Mostly clear and warmer. Increasing winds.',
        25  : 'Partly cloudy with little temperature change.',
        26  : 'Mostly clear with little temperature change.',
        27  : 'Increasing clouds and warmer. Precipitation possible within 12 hours. Increasing winds.',
        28  : 'Mostly clear and warmer. Increasing winds.',
        29  : 'Increasing clouds and warmer.',
        30  : 'Partly cloudy with little temperature change.',
        31  : 'Mostly clear with little temperature change.',
        32  : 'Increasing clouds and warmer. Precipitation possible within 12 hours. Increasing winds.',
        33  : 'Mostly clear and warmer. Increasing winds.',
        34  : 'Increasing clouds and warmer.',
        35  : 'Partly cloudy with little temperature change.',
        36  : 'Mostly clear with little temperature change.',
        37  : 'Increasing clouds and warmer. Precipitation possible within 12 hours. Increasing winds.',
        38  : 'Partly cloudy with little temperature change.',
        39  : 'Mostly clear with little temperature change.',
        40  : 'Mostly clear and warmer. Precipitation possible within 48 hours.',
        41  : 'Mostly clear and warmer.',
        42  : 'Partly cloudy with little temperature change.',
        43  : 'Mostly clear with little temperature change.',
        44  : 'Increasing clouds with little temperature change. Precipitation possible within 24 to 48 hours.',
        45  : 'Increasing clouds with little temperature change.',
        46  : 'Partly cloudy with little temperature change.',
        47  : 'Mostly clear with little temperature change.',
        48  : 'Increasing clouds and warmer. Precipitation possible within 12 to 24 hours.',
        49  : 'Partly cloudy with little temperature change.',
        50  : 'Mostly clear with little temperature change.',
        51  : 'Increasing clouds and warmer. Precipitation possible within 12 to 24 hours. Windy.',
        52  : 'Partly cloudy with little temperature change.',
        53  : 'Mostly clear with little temperature change.',
        54  : 'Increasing clouds and warmer. Precipitation possible within 12 to 24 hours. Windy.',
        55  : 'Partly cloudy with little temperature change.',
        56  : 'Mostly clear with little temperature change.',
        57  : 'Increasing clouds and warmer. Precipitation possible within 6 to 12 hours.',
        58  : 'Partly cloudy with little temperature change.',
        59  : 'Mostly clear with little temperature change.',
        60  : 'Increasing clouds and warmer. Precipitation possible within 6 to 12 hours. Windy.',
        61  : 'Partly cloudy with little temperature change.',
        62  : 'Mostly clear with little temperature change.',
        63  : 'Increasing clouds and warmer. Precipitation possible within 12 to 24 hours. Windy.',
        64  : 'Partly cloudy with little temperature change.',
        65  : 'Mostly clear with little temperature change.',
        66  : 'Increasing clouds and warmer. Precipitation possible within 12 hours.',
        67  : 'Partly cloudy with little temperature change.',
        68  : 'Mostly clear with little temperature change.',
        69  : 'Increasing clouds and warmer. Precipitation likley.',
        70  : 'Clearing and cooler. Precipitation ending within 6 hours.',
        71  : 'Partly cloudy with little temperature change.',
        72  : 'Clearing and cooler. Precipitation ending within 6 hours.',
        73  : 'Mostly clear with little temperature change.',
        74  : 'Clearing and cooler. Precipitation ending within 6 hours.',
        75  : 'Partly cloudy and cooler.',
        76  : 'Partly cloudy with little temperature change.',
        77  : 'Mostly clear and cooler.',
        78  : 'Clearing and cooler. Precipitation ending within 6 hours.',
        79  : 'Mostly clear with little temperature change.',
        80  : 'Clearing and cooler. Precipitation ending within 6 hours.',
        81  : 'Mostly clear and cooler.',
        82  : 'Partly cloudy with little temperature change.',
        83  : 'Mostly clear with little temperature change.',
        84  : 'Increasing clouds with little temperature change. Precipitation possible within 24 hours.',
        85  : 'Mostly cloudy and cooler. Precipitation continuing.',
        86  : 'Partly cloudy with little temperature change.',
        87  : 'Mostly clear with little temperature change.',
        88  : 'Mostly cloudy and cooler. Precipitation likely.',
        89  : 'Mostly cloudy with little temperature change. Precipitation continuing.',
        90  : 'Mostly cloudy with little temperature change. Precipitation likely.',
        91  : 'Partly cloudy with little temperature change.',
        92  : 'Mostly clear with little temperature change.',
        93  : 'Increasing clouds and cooler. Precipitation possible and windy within 6 hours.',
        94  : 'Increasing clouds with little temperature change. Precipitation possible and windy within 6 hours.',
        95  : 'Mostly cloudy and cooler. Precipitation continuing. Increasing winds.',
        96  : 'Partly cloudy with little temperature change.',
        97  : 'Mostly clear with little temperature change.',
        98  : 'Mostly cloudy and cooler. Precipitation likely. Increasing winds.',
        99  : 'Mostly cloudy with little temperature change. Precipitation continuing. Increasing winds.',
        100 : 'Mostly cloudy with little temperature change. Precipitation likely. Increasing winds.',
        101 : 'Partly cloudy with little temperature change.',
        102 : 'Mostly clear with little temperature change.',
        103 : 'Increasing clouds and cooler. Precipitation possible within 12 to 24 hours possible wind shift to the W, NW, or N.',
        104 : 'Increasing clouds with little temperature change. Precipitation possible within 12 to 24 hours possible wind shift to the W, NW, or N.',
        105 : 'Partly cloudy with little temperature change.',
        106 : 'Mostly clear with little temperature change.',
        107 : 'Increasing clouds and cooler. Precipitation possible within 6 hours possible wind shift to the W, NW, or N.',
        108 : 'Increasing clouds with little temperature change. Precipitation possible within 6 hours possible wind shift to the W, NW, or N.',
        109 : 'Mostly cloudy and cooler. Precipitation ending within 12 hours possible wind shift to the W, NW, or N.',
        110 : 'Mostly cloudy and cooler. Possible wind shift to the W, NW, or N.',
        111 : 'Mostly cloudy with little temperature change. Precipitation ending within 12 hours possible wind shift to the W, NW, or N.',
        112 : 'Mostly cloudy with little temperature change. Possible wind shift to the W, NW, or N.',
        113 : 'Mostly cloudy and cooler. Precipitation ending within 12 hours possible wind shift to the W, NW, or N.',
        114 : 'Partly cloudy with little temperature change.',
        115 : 'Mostly clear with little temperature change.',
        116 : 'Mostly cloudy and cooler. Precipitation possible within 24 hours possible wind shift to the W, NW, or N.',
        117 : 'Mostly cloudy with little temperature change. Precipitation ending within 12 hours possible wind shift to the W, NW, or N.',
        118 : 'Mostly cloudy with little temperature change. Precipitation possible within 24 hours possible wind shift to the W, NW, or N.',
        119 : 'Clearing, cooler and windy. Precipitation ending within 6 hours.',
        120 : 'Clearing, cooler and windy.',
        121 : 'Mostly cloudy and cooler. Precipitation ending within 6 hours. Windy with possible wind shift to the W, NW, or N.',
        122 : 'Mostly cloudy and cooler. Windy with possible wind shift o the W, NW, or N.',
        123 : 'Clearing, cooler and windy.',
        124 : 'Partly cloudy with little temperature change.',
        125 : 'Mostly clear with little temperature change.',
        126 : 'Mostly cloudy with little temperature change. Precipitation possible within 12 hours. Windy.',
        127 : 'Partly cloudy with little temperature change.',
        128 : 'Mostly clear with little temperature change.',
        129 : 'Increasing clouds and cooler. Precipitation possible within 12 hours, possibly heavy at times. Windy.',
        130 : 'Mostly cloudy and cooler. Precipitation ending within 6 hours. Windy.',
        131 : 'Partly cloudy with little temperature change.',
        132 : 'Mostly clear with little temperature change.',
        133 : 'Mostly cloudy and cooler. Precipitation possible within 12 hours. Windy.',
        134 : 'Mostly cloudy and cooler. Precipitation ending in 12 to 24 hours.',
        135 : 'Mostly cloudy and cooler.',
        136 : 'Mostly cloudy and cooler. Precipitation continuing, possible heavy at times. Windy.',
        137 : 'Partly cloudy with little temperature change.',
        138 : 'Mostly clear with little temperature change.',
        139 : 'Mostly cloudy and cooler. Precipitation possible within 6 to 12 hours. Windy.',
        140 : 'Mostly cloudy with little temperature change. Precipitation continuing, possibly heavy at times. Windy.',
        141 : 'Partly cloudy with little temperature change.',
        142 : 'Mostly clear with little temperature change.',
        143 : 'Mostly cloudy with little temperature change. Precipitation possible within 6 to 12 hours. Windy.',
        144 : 'Partly cloudy with little temperature change.',
        145 : 'Mostly clear with little temperature change.',
        146 : 'Increasing clouds with little temperature change. Precipitation possible within 12 hours, possibly heavy at times. Windy.',
        147 : 'Mostly cloudy and cooler. Windy.',
        148 : 'Mostly cloudy and cooler. Precipitation continuing, possibly heavy at times. Windy.',
        149 : 'Partly cloudy with little temperature change.',
        150 : 'Mostly clear with little temperature change.',
        151 : 'Mostly cloudy and cooler. Precipitation likely, possibly heavy at times. Windy.',
        152 : 'Mostly cloudy with little temperature change. Precipitation continuing, possibly heavy at times. Windy.',
        153 : 'Mostly cloudy with little temperature change. Precipitation likely, possibly heavy at times. Windy.',
        154 : 'Partly cloudy with little temperature change.',
        155 : 'Mostly clear with little temperature change.',
        156 : 'Increasing clouds and cooler. Precipitation possible within 6 hours. Windy.',
        157 : 'Increasing clouds with little temperature change. Precipitation possible within 6 hours. Windy',
        158 : 'Increasing clouds and cooler. Precipitation continuing. Windy with possible wind shift to the W, NW, or N.',
        159 : 'Partly cloudy with little temperature change.',
        160 : 'Mostly clear with little temperature change.',
        161 : 'Mostly cloudy and cooler. Precipitation likely. Windy with possible wind shift to the W, NW, or N.',
        162 : 'Mostly cloudy with little temperature change. Precipitation continuing. Windy with possible wind shift to the W, NW, or N.',
        163 : 'Mostly cloudy with little temperature change. Precipitation likely. Windy with possible wind shift to the W, NW, or N.',
        164 : 'Increasing clouds and cooler. Precipitation possible within 6 hours. Windy with possible wind shift to the W, NW, or N.',
        165 : 'Partly cloudy with little temperature change.',
        166 : 'Mostly clear with little temperature change.',
        167 : 'Increasing clouds and cooler. Precipitation possible within 6 hours possible wind shift to the W, NW, or N.',
        168 : 'Increasing clouds with little temperature change. Precipitation possible within 6 hours. Windy with possible wind shift to the W, NW, or N.',
        169 : 'Increasing clouds with little temperature change. Precipitation possible within 6 hours possible wind shift to the W, NW, or N.',
        170 : 'Partly cloudy with little temperature change.',
        171 : 'Mostly clear with little temperature change.',
        172 : 'Increasing clouds and cooler. Precipitation possible within 6 hours. Windy with possible wind shift to the W, NW, or N.',
        173 : 'Increasing clouds with little temperature change. Precipitation possible within 6 hours. Windy with possible wind shift to the W, NW, or N.',
        174 : 'Partly cloudy with little temperature change.',
        175 : 'Mostly clear with little temperature change.',
        176 : 'Increasing clouds and cooler. Precipitation possible within 12 to 24 hours. Windy with possible wind shift to the W, NW, or N.',
        177 : 'Increasing clouds with little temperature change. Precipitation possible within 12 to 24 hours. Windy with possible wind shift to the W, NW, or N.',
        178 : 'Mostly cloudy and cooler. Precipitation possibly heavy at times and ending within 12 hours. Windy with possible wind shift to the W, NW, or N.',
        179 : 'Partly cloudy with little temperature change.',
        180 : 'Mostly clear with little temperature change.',
        181 : 'Mostly cloudy and cooler. Precipitation possible within 6 to 12 hours, possibly heavy at times. Windy with possible wind shift to the W, NW, or N.',
        182 : 'Mostly cloudy with little temperature change. Precipitation ending within 12 hours. Windy with possible wind shift to the W, NW, or N.',
        183 : 'Mostly cloudy with little temperature change. Precipitation possible within 6 to 12 hours, possibly heavy at times. Windy with possible wind shift to the W, NW, or N.',
        184 : 'Mostly cloudy and cooler. Precipitation continuing.',
        185 : 'Partly cloudy with little temperature change.',
        186 : 'Mostly clear with little temperature change.',
        187 : 'Mostly cloudy and cooler. Precipitation likely. Windy with possible wind shift to the W, NW, or N.',
        188 : 'Mostly cloudy with little temperature change. Precipitation continuing.',
        189 : 'Mostly cloudy with little temperature change. Precipitation likely.',
        190 : 'Partly cloudy with little temperature change.',
        191 : 'Mostly clear with little temperature change.',
        192 : 'Mostly cloudy and cooler. Precipitation possible within 12 hours, possibly heavy at times. Windy.',
        193 : 'FORECAST REQUIRES 3 HOURS OF RECENT DATA',
        194 : 'Mostly clear and cooler.',
        195 : 'Mostly clear and cooler.',
        196 : 'Mostly clear and cooler.'
        }

        
# ============================================================================
#                              class WUThread
# ============================================================================


class WUThread(threading.Thread):
    """Thread to run WUArchive service."""
    
    def __init__(self, target, *args):
        self._target = target
        self._args = args
        threading.Thread.__init__(self)

    def run(self):
        self._target(*self._args)
    

# ============================================================================
#                              class WUArchive
# ============================================================================


class WUArchive(weewx.engine.StdService):
    """Service to store WU sourced data and Davis console forecast data."""
    
    def __init__(self, engine, config_dict):
        super(WUArchive, self).__init__(engine, config_dict)

        #
        # Setup for WU API calls/Vantage Console data
        #
        
        # Get our lat/long, needed for sunrise/sunset calcs to set transition to 
        # day/night icons
        self.latitude = float(config_dict['Station']['latitude'])
        self.longitude = float(config_dict['Station']['longitude'])
        # Create a list of the WU API calls we need
        self.WUqueryTypes=['conditions', 'forecast', 'almanac']
        # Set interval between API calls for each API call type we need
        self.interval = {}
        self.interval['conditions'] = int(self.config_dict['Weewx-WD']['Conditions']['WU'].get('current_interval', 1800))
        self.interval['forecast'] = int(self.config_dict['Weewx-WD']['Conditions']['WU'].get('forecast_interval', 1800))
        self.interval['almanac'] = int(self.config_dict['Weewx-WD']['Conditions']['WU'].get('almanac_interval', 3600))
        # Set ts we last made the call
        self.last = {}
        self.last['conditions'] = None
        self.last['forecast'] = None
        self.last['almanac'] = None
        # Create holder for WU responses
        self.response = {}
        # Create holder for Davis Console loop data
        self.loop_packet = {}
        # Set max no of tries we will make in any one attempt to contact WU via API
        self.max_WU_tries = self.config_dict['Weewx-WD']['Conditions']['WU'].get('max_WU_tries', 3)
        self.max_WU_tries = toint('max_WU_tries', self.max_WU_tries, 3)
        # set API call lockout period. refer weewx.conf
        self.api_lockout_period = self.config_dict['Weewx-WD']['Conditions']['WU'].get('api_lockout_period', 60)
        self.api_lockout_period = toint('api_lockout_period', self.api_lockout_period, 60)
        # create holder for last WU API call ts
        self.last_WU_query = None
        # Get our API key from weewx.conf, first look in [Weewx-WD] and if no luck
        # try [Forecast] if it exists. Wrap in a try..except loop to catch exceptions (ie one or
        # both don't exist.
        try:
            if self.config_dict['Weewx-WD']['Conditions']['WU'].get('apiKey', None) != None:
                self.api_key = self.config_dict['Weewx-WD']['Conditions']['WU'].get('apiKey')
            elif self.config_dict['Forecast']['WU'].get('api_key', None) != None:
                self.api_key = self.config_dict['Forecast']['WU'].get('api_key')
            else:
                loginf("Cannot find valid Weather Underground API key")
        except:
            loginf("Cannot find Weather Underground API key")
        # Get our 'location' for use in WU API calls. Refer weewx.conf for details.
        self.location = self.config_dict['Weewx-WD']['Conditions']['WU'].get('location', (self.latitude, self.longitude))
        # Set fixed part of WU API call url
        self.default_url = 'http://api.wunderground.com/api'
        
        # Extract our binding from the Weewx-WD section of the config file. If
        # it's missing, fill with a default
        if 'Weewx-WD' in config_dict:
            self.binding = config_dict['Weewx-WD'].get('WU_data_binding', 'wdwu_binding')
        else:
            self.binding = 'wdwu_binding'
            
        syslog.syslog(syslog.LOG_INFO, "engine: WUArchive will use data binding %s" % self.binding)
        
        # setup our database if needed
        self.setup_database(config_dict)
        
        # Set some of our parameters we require to manage the db
        # How long to keep loop records
        self.max_age = config_dict['Weewx-WD']['Conditions'].get('max_age', 3600)
        self.max_age = toint('max_age', self.max_age, 3600)
        # Option to vacuum the sqlite database
        self.vacuum = config_dict['Weewx-WD']['Conditions'].get('vacuum', 86400)
        self.vacuum = toint('vacuum', self.vacuum, 86400)
        # ts at which we last vacuumed
        self.last_vacuum = None
        # How often to retry database failures
        self.db_max_tries = config_dict['Weewx-WD']['Conditions'].get('database_max_tries', 3)
        self.db_max_tries = int(self.db_max_tries)
        # How long to wait between retries, in seconds
        self.db_retry_wait = config_dict['Weewx-WD']['Conditions'].get('database_retry_wait', 10)
        self.db_retry_wait = int(self.db_retry_wait)

        # set the unit groups for our obs
        obs_group_dict["tempRecordHigh"] = "group_temperature"
        obs_group_dict["tempNormalHigh"] = "group_temperature"
        obs_group_dict["tempRecordLow"] = "group_temperature"
        obs_group_dict["tempNormalLow"] = "group_temperature"
        obs_group_dict["stormRain"] = "group_rain"
        obs_group_dict["stormStart"] = "group_time"
        
        # Bind ourself to NEW_ARCHIVE_RECORD to ensure we have a chance to:
        # - update WU data(if necessary)
        # - save our data
        # on each new record
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        # bind ourself to each new loop packet so we can capture Davis
        # Vantage forecast data
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        loginf(('forecast interval=%s conditions interval=%s almanac interval=%s '
               'max_age=%s vacuum=%s api_key=%s location=%s') %
               (self.interval['forecast'], self.interval['conditions'], self.interval['almanac'],
               self.max_age, self.vacuum, 'xxxxxxxxxxxx'+self.api_key[-4:], self.location))

    def new_archive_record(self, event):
        """ Kick off in a new thread."""
        
        t = WUThread(self.wdWU_main, event)
        t.setName('WUThread')
        t.start()

    def wdWU_main(self, event):
        """ Loop through the WU API requests we need to do making the API call,
            parsing and saving the results.
        """

        # Get time now as a ts
        now = time.time()
        # Work out sunrise and sunset ts so we can determine if it is night or day. Needed so
        # we can set day or night icons when translating WU icons to Saratoga icons
        (y,m,d) = time.localtime(now)[0:3]
        (sunrise_utc, sunset_utc) = weeutil.Sun.sunRiseSet(y, m, d, self.longitude, self.latitude)
        sunrise_tt = weeutil.weeutil.utc_to_local_tt(y, m, d, sunrise_utc)
        sunset_tt  = weeutil.weeutil.utc_to_local_tt(y, m, d, sunset_utc)
        sunrise_ts = time.mktime(sunrise_tt)
        sunset_ts = time.mktime(sunset_tt) 
        # If we are not between sunrise and sunset it must be night
        self.night = not (sunrise_ts < now < sunset_ts)
        # Loop through our list of API calls to be made
        for _WUquery in self.WUqueryTypes:
            logdbg("Last Weather Underground %s query at %s" % (_WUquery, self.last[_WUquery]))
            # Has it been at least 60 seconds since our last API call?
            if self.last_WU_query is None or ((now + 1 - self.api_lockout_period) >= self.last_WU_query):
                # If we haven't made this API call previously or if its been too long since
                # the last call then make the call
                if (self.last[_WUquery] is None) or ((now + 1 - self.interval[_WUquery]) >= self.last[_WUquery]):
                    # Make the call, wrap in a try..except just in case
                    try:
                        self.response[_WUquery] = self.get_WU_response(_WUquery, self.max_WU_tries)
                        loginf("Downloaded updated Weather Underground %s information" % (_WUquery))
#                        logdbg("Downloaded updated Weather Underground %s information" % (_WUquery))
                        # If we got something back then reset our timer
                        if self.response[_WUquery] is not None:
                            self.last[_WUquery] = now
                    except:
                        loginf("Weather Underground '%s' API query failure" % (_WUquery))
            else:
                # API call limiter kicked in so say so
                loginf("API call limit reached. Tried to make an API call within %d sec of the previous call" % (self.api_lockout_period, ))
                break
        self.last_WU_query = max(self.last[q] for q in self.last)
        # Parse the responses
        _data_packet = self.parse_WU_responses(event)
        # Get a dictionary for our database manager
        dbm_dict = weewx.manager.get_manager_dict(
            self.config_dict['DataBindings'],
            self.config_dict['Databases'],
            self.binding,
            default_binding_dict=get_default_binding_dict())
        with weewx.manager.open_manager(dbm_dict) as dbm:
            # save our responses
            self.save_wu_response(dbm, _data_packet, self.db_max_tries, self.db_retry_wait)
            # set ts of last packet processed
            self.last_ts = _data_packet['dateTime']
            # prune older packets and vacuum if required
            if self.max_age > 0:
                self.prune(dbm, self.last_ts - self.max_age,
                           self.db_max_tries, self.db_retry_wait)
                # vacuum the database
                if self.vacuum > 0:
                    if self.last_vacuum is None or ((now + 1 - self.vacuum) >= self.last_vacuum):
                        self.vacuum_database(dbm)
                        self.last_vacuum = now
        return
        
    def get_WU_response(self, wu_query, max_wu_tries):
        """Construct and make a WU API call and return the response."""

        # construct our API call URL
        url = '%s/%s/%s/pws:1/q/%s.json' % (self.default_url, 
                                            self.api_key, wu_query, 
                                            self.location)
        # we will attempt the call max_wu_tries times
        for count in range(max_wu_tries):
            # attempt the call
            try:
                w = urllib2.urlopen(url)
                _wu_response = w.read()
                w.close()
                return _wu_response
            except:
                loginf("Failed to get '%s' on attempt %d" % (wu_query, count+1))
        else:
            loginf("Failed to get Weather Underground '%s'" % (wu_query, ))
        return None

    def parse_WU_responses(self, event):
        """Parse a WU API response and construct a data packet."""
        
        # create a holder for the data (lines) we will write to file
        _packet = {}
        _packet['dateTime'] = event.record['dateTime']
        _packet['usUnits'] = event.record['usUnits']
        # iterate over each of the API calls
        for query in self.WUqueryTypes:
            # deserialise our JSON response
            _resp = json.loads(self.response[query])
            # check for recognised format
            if not 'response' in _resp:
                loginf("Unknown format in Weather Underground '%s'" % (query, ))
                return _packet
            _response = _resp['response']
            # check for WU provided error otherwise start pulling in the 
            # fields/data we want
            if 'error' in _response:
                loginf("Error in Weather Underground '%s' response" % (query, ))
                return _packet
            # forecast data
            elif query == 'forecast':
                # look up Saratoga icon number given the WU icon name
                _name = _resp['forecast']['txt_forecast']['forecastday'][0]['icon']
                _packet['forecastIcon'] = icon_dict[_name]
                _packet['forecastText'] = _resp['forecast']['txt_forecast']['forecastday'][0]['fcttext']
                _packet['forecastTextMetric'] = _resp['forecast']['txt_forecast']['forecastday'][0]['fcttext_metric']
            # conditions data
            elif query == 'conditions':
                # WU does not seem to provide day/night icon name in their 
                # 'conditions' response so we need to add it. Just need to add 
                # 'nt_' to front of name before looking up in out Saratoga 
                # icons dictionary
                if self.night:
                    _packet['currentIcon'] = icon_dict['nt_%s' % (_resp['current_observation']['icon'],)]
                else:
                    _packet['currentIcon'] = icon_dict[_resp['current_observation']['icon']]
                _packet['currentText'] = _resp['current_observation']['weather']
            # almanac data
            elif query == 'almanac':
                if _packet['usUnits'] is weewx.US:
                    _packet['tempRecordHigh'] = _resp['almanac']['temp_high']['record']['F']
                    _packet['tempNormalHigh'] = _resp['almanac']['temp_high']['normal']['F']
                    _packet['tempRecordLow'] = _resp['almanac']['temp_low']['record']['F']
                    _packet['tempNormalLow'] = _resp['almanac']['temp_low']['normal']['F']
                else:
                    _packet['tempRecordHigh'] = _resp['almanac']['temp_high']['record']['C']
                    _packet['tempNormalHigh'] = _resp['almanac']['temp_high']['normal']['C']
                    _packet['tempRecordLow'] = _resp['almanac']['temp_low']['record']['C']
                    _packet['tempNormalLow'] = _resp['almanac']['temp_low']['normal']['C']
                _packet['tempRecordHighYear'] = _resp['almanac']['temp_high']['recordyear']
                _packet['tempRecordLowYear'] = _resp['almanac']['temp_low']['recordyear']
        _packet['vantageForecastIcon'] = self.loop_packet['forecastIcon']
        try:
            _packet['vantageForecastRule'] = davis_fr_dict[self.loop_packet['forecastRule']]
        except:
            _packet['vantageForecastRule'] = ""
            loginf('parse_WU_responses: Could not decode Vantage forecast code.')
        _packet['stormRain'] = self.loop_packet['stormRain']
        _packet['stormStart'] = self.loop_packet['stormStart']
        return _packet
        
    @staticmethod
    def save_wu_response(dbm, _data_packet, max_tries=3, retry_wait=10):
        """Save the WU responses to our database."""
        
        for count in range(max_tries):
            try:
                logdbg('saving WU response')
                # save our data to the database
                dbm.addRecord(_data_packet, log_level=syslog.LOG_DEBUG)
                break
            except Exception, e:
                logerr('save failed (attempt %d of %d): %s' %
                       ((count + 1), max_tries, e))
                logerr('waiting %d seconds before retry' % (retry_wait, ))
                time.sleep(retry_wait)
        else:
            raise Exception('save failed after %d attempts' % max_tries)

    @staticmethod
    def prune(dbm, ts, max_tries=3, retry_wait=10):
        """Remove records older than ts from the database."""

        sql = "delete from %s where dateTime < %d" % (dbm.table_name, ts)
        for count in range(max_tries):
            try:
                logdbg('deleting Weather Underground data before %d' % (ts, ))
                dbm.getSql(sql)
                logdbg('deleted Weather Underground before %d' % (ts))
                break
            except Exception, e:
                logerr('prune failed (attempt %d of %d): %s' % ((count+1), max_tries, e))
                logerr('waiting %d seconds before retry' % (retry_wait, ))
                time.sleep(retry_wait)
        else:
            raise Exception('prune failed after %d attempts' % max_tries)
        return

    @staticmethod
    def vacuum_database(dbm):
        """Vacuum our database to save space.
        
            SQLite databases need a little help to prevent them from 
            continually growing in size even though we prune records from the 
            database. Vacuum will only work on SQLite databases. It will 
            compact the database file. It should be OK to run this on a MySQL 
            database - it will silently fail.
        """
        
# remove timing code once we get a handle on how long this takes
        # Get time now as a ts
        t1 = time.time()
        try:
            logdbg('vacuuming database %s' % (dbm.database_name))
            dbm.getSql('vacuum')
        except Exception, e:
            logerr('Vacuuming database % failed: %s' % (dbm.database_name, e))

        t2 = time.time()
        loginf("vacuum_database executed in %0.9f seconds" % (t2-t1))
        
    def setup_database(self, config_dict):
        """Setup the database table we will be using."""

        # create the database and/or table if either doesn't exist, then return 
        # an opened instance of the database manager
        dbmanager = self.engine.db_binder.get_database(self.binding, 
                                                       initialize=True)
        loginf("Using binding '%s' to database '%s'" % (self.binding, 
                                                        dbmanager.database_name))
        
    def new_loop_packet(self, event):
        """Save loop based Davis console forecast data.
        
            The Davis Console forecast data is published in each loop packet. 
            There is little benefit in saving this data to database each loop 
            period as the data is slow changing so we will stash the data and 
            save to database each archive period along with our WU sourced data.
        """
        
        # update our stashed loop packet data
        try:
            self.loop_packet['forecastIcon'] = event.packet['forecastIcon']
            self.loop_packet['forecastRule'] = event.packet['forecastRule']
            self.loop_packet['stormRain'] = event.packet['stormRain']
            self.loop_packet['stormStart'] = event.packet['stormStart']
        except:
            loginf('new_loop_packet: Loop packet data error. Cannot decode packet.')
        
    def shutDown(self):
        pass