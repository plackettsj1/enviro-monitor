#!/usr/bin/env python3
#Northcliff Environment Monitor - 4.41 - Gen

import paho.mqtt.client as mqtt
import colorsys
import math
import json
import requests
import ST7735
import os
import time
from datetime import datetime, timedelta
import numpy
from fonts.ttf import RobotoMedium as UserFont
import pytz
from pytz import timezone
from astral.geocoder import database, lookup, add_locations
from astral.sun import sun
try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus

try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559
    ltr559 = LTR559()
except ImportError:
    import ltr559
from enviroplus import gas
from bme280 import BME280
from pms5003 import PMS5003, ReadTimeoutError, ChecksumMismatchError
from subprocess import check_output
from PIL import Image, ImageDraw, ImageFont, ImageFilter
try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus
import logging

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
logging.info("""Northcliff_Environment_Monitor.py 4.41 - Combined enviro+ sensor capture, external sensor capture, Luftdaten and Home Manager Updates and display of readings.
#Press Ctrl+C to exit!

#Note: you'll need to register with Luftdaten at:
#https://meine.luftdaten.info/ and enter your Raspberry Pi
#serial number that's displayed on the Enviro plus LCD along
#with the other details before the data appears on the
#Luftdaten map.

#""")

bus = SMBus(1)

# Create a BME280 instance
bme280 = BME280(i2c_dev=bus)

# Create an LCD instance
disp = ST7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rotation=270,
    spi_speed_hz=10000000
)

# Initialize display
disp.begin()

def retrieve_config():
    try:
        with open('<Your config.json file location>', 'r') as f:
            parsed_config_parameters = json.loads(f.read())
            print('Retrieved Config', parsed_config_parameters)
    except IOError:
        print('Config Retrieval Failed')
    temp_offset = parsed_config_parameters['temp_offset']
    altitude = parsed_config_parameters['altitude']
    enable_display = parsed_config_parameters['enable_display'] # Enables the display and flags that the weather protection cover is used with different temp/hum compensation
    enable_adafruit_io = parsed_config_parameters['enable_adafruit_io']
    aio_user_name = parsed_config_parameters['aio_user_name']
    aio_key = parsed_config_parameters['aio_key']
    aio_feed_window = parsed_config_parameters['aio_feed_window']
    aio_feed_sequence = parsed_config_parameters['aio_feed_sequence']
    aio_household_prefix = parsed_config_parameters['aio_household_prefix']
    aio_location_prefix = parsed_config_parameters['aio_location_prefix']
    aio_package = parsed_config_parameters['aio_package']
    enable_send_data_to_homemanager = parsed_config_parameters['enable_send_data_to_homemanager']
    enable_receive_data_from_homemanager = parsed_config_parameters['enable_receive_data_from_homemanager']
    enable_indoor_outdoor_functionality = parsed_config_parameters['enable_indoor_outdoor_functionality']
    mqtt_broker_name = parsed_config_parameters['mqtt_broker_name']
    enable_luftdaten = parsed_config_parameters['enable_luftdaten']
    enable_climate_and_gas_logging = parsed_config_parameters['enable_climate_and_gas_logging']
    enable_particle_sensor = parsed_config_parameters['enable_particle_sensor']
    incoming_temp_hum_mqtt_topic = parsed_config_parameters['incoming_temp_hum_mqtt_topic']
    incoming_temp_hum_mqtt_sensor_name = parsed_config_parameters['incoming_temp_hum_mqtt_sensor_name']
    incoming_barometer_mqtt_topic = parsed_config_parameters['incoming_barometer_mqtt_topic']
    incoming_barometer_sensor_id = parsed_config_parameters['incoming_barometer_sensor_id']
    indoor_outdoor_function = parsed_config_parameters['indoor_outdoor_function']
    mqtt_client_name = parsed_config_parameters['mqtt_client_name']
    outdoor_mqtt_topic = parsed_config_parameters['outdoor_mqtt_topic']
    indoor_mqtt_topic = parsed_config_parameters['indoor_mqtt_topic']
    city_name = parsed_config_parameters['city_name']
    time_zone = parsed_config_parameters['time_zone']
    custom_locations = parsed_config_parameters['custom_locations']
    return (temp_offset, altitude, enable_display, enable_adafruit_io, aio_user_name, aio_key, aio_feed_window, aio_feed_sequence,
            aio_household_prefix, aio_location_prefix, aio_package, enable_send_data_to_homemanager,
            enable_receive_data_from_homemanager, enable_indoor_outdoor_functionality,
            mqtt_broker_name, enable_luftdaten, enable_climate_and_gas_logging, enable_particle_sensor,
            incoming_temp_hum_mqtt_topic, incoming_temp_hum_mqtt_sensor_name, incoming_barometer_mqtt_topic, incoming_barometer_sensor_id,
            indoor_outdoor_function, mqtt_client_name, outdoor_mqtt_topic, indoor_mqtt_topic, city_name, time_zone, custom_locations)

# Config Setup
(temp_offset, altitude, enable_display, enable_adafruit_io, aio_user_name, aio_key, aio_feed_window, aio_feed_sequence,
  aio_household_prefix, aio_location_prefix, aio_package, enable_send_data_to_homemanager,
  enable_receive_data_from_homemanager, enable_indoor_outdoor_functionality, mqtt_broker_name,
  enable_luftdaten, enable_climate_and_gas_logging,  enable_particle_sensor, incoming_temp_hum_mqtt_topic,
  incoming_temp_hum_mqtt_sensor_name, incoming_barometer_mqtt_topic, incoming_barometer_sensor_id,
  indoor_outdoor_function, mqtt_client_name, outdoor_mqtt_topic, indoor_mqtt_topic,
  city_name, time_zone, custom_locations) = retrieve_config()

# Add to city database
db = database()
add_locations(custom_locations, db)

if enable_particle_sensor:
    # Create a PMS5003 instance
    pms5003 = PMS5003()
    time.sleep(1)
            
def read_pm_values(luft_values, mqtt_values, own_data, own_disp_values):
    if enable_particle_sensor:
        try:
            pm_values = pms5003.read()
            #print('PM Values:', pm_values)
            own_data["P2.5"][1] = pm_values.pm_ug_per_m3(2.5)
            mqtt_values["P2.5"] = own_data["P2.5"][1]
            own_disp_values["P2.5"] = own_disp_values["P2.5"][1:] + [[own_data["P2.5"][1], 1]]
            luft_values["P2"] = str(mqtt_values["P2.5"])
            own_data["P10"][1] = pm_values.pm_ug_per_m3(10)
            mqtt_values["P10"] = own_data["P10"][1]
            own_disp_values["P10"] = own_disp_values["P10"][1:] + [[own_data["P10"][1], 1]]
            luft_values["P1"] = str(own_data["P10"][1])
            own_data["P1"][1] = pm_values.pm_ug_per_m3(1.0)
            mqtt_values["P1"] = own_data["P1"][1]
            own_disp_values["P1"] = own_disp_values["P1"][1:] + [[own_data["P1"][1], 1]]
        except (ReadTimeoutError, ChecksumMismatchError):
            logging.info("Failed to read PMS5003")
            display_error('Particle Sensor Error')
            pms5003.reset()
            pm_values = pms5003.read()
            own_data["P2.5"][1] = pm_values.pm_ug_per_m3(2.5)
            mqtt_values["P2.5"] = own_data["P2.5"][1]
            own_disp_values["P2.5"] = own_disp_values["P2.5"][1:] + [[own_data["P2.5"][1], 1]]
            luft_values["P2"] = str(mqtt_values["P2.5"])
            own_data["P10"][1] = pm_values.pm_ug_per_m3(10)
            mqtt_values["P10"] = own_data["P10"][1]
            own_disp_values["P10"] = own_disp_values["P10"][1:] + [[own_data["P10"][1], 1]]
            luft_values["P1"] = str(own_data["P10"][1])
            own_data["P1"][1] = pm_values.pm_ug_per_m3(1.0)
            mqtt_values["P1"] = own_data["P1"][1]
            own_disp_values["P1"] = own_disp_values["P1"][1:] + [[own_data["P1"][1], 1]]
    return(luft_values, mqtt_values, own_data, own_disp_values)

# Read gas and climate values from Home Manager and /or BME280 
def read_climate_gas_values(luft_values, mqtt_values, own_data, maxi_temp, mini_temp, own_disp_values, gas_sensors_warm, gas_calib_temp, gas_calib_hum, gas_calib_bar, altitude):
    raw_temp, comp_temp = adjusted_temperature()
    raw_hum, comp_hum = adjusted_humidity()
    current_time = time.time()
    use_external_temp_hum = False
    use_external_barometer = False
    if enable_receive_data_from_homemanager:
        use_external_temp_hum, use_external_barometer = es.check_valid_readings(current_time)
    if use_external_temp_hum == False:
        print("Internal Temp/Hum Sensor")
        luft_values["temperature"] = "{:.2f}".format(comp_temp)
        own_data["Temp"][1] = round(comp_temp, 1)
        luft_values["humidity"] = "{:.2f}".format(comp_hum)
        own_data["Hum"][1] = round(comp_hum, 1)
    else: # Use external temp/hum sensor but still capture raw temp and raw hum for gas compensation and logging
        print("External Temp/Hum Sensor")
        luft_values["temperature"] = es.temperature
        own_data["Temp"][1] = float(luft_values["temperature"])
        luft_values["humidity"] = es.humidity
        own_data["Hum"][1] = float(luft_values["humidity"])
    own_disp_values["Temp"] = own_disp_values["Temp"][1:] + [[own_data["Temp"][1], 1]]
    mqtt_values["Temp"] = own_data["Temp"][1]
    own_disp_values["Hum"] = own_disp_values["Hum"][1:] + [[own_data["Hum"][1], 1]]
    mqtt_values["Hum"][0] = own_data["Hum"][1]
    mqtt_values["Hum"][1] = domoticz_hum_map[describe_humidity(own_data["Hum"][1])]
    # Determine max and min temps
    if first_climate_reading_done :
        if maxi_temp is None:
            maxi_temp = own_data["Temp"][1]
        elif own_data["Temp"][1] > maxi_temp:
            maxi_temp = own_data["Temp"][1]
        else:
            pass
        if mini_temp is None:
            mini_temp = own_data["Temp"][1]
        elif own_data["Temp"][1] < mini_temp:
            mini_temp = own_data["Temp"][1]
        else:
            pass
    mqtt_values["Min Temp"] = mini_temp
    mqtt_values["Max Temp"] = maxi_temp
    raw_barometer = bme280.get_pressure()
    if use_external_barometer == False:
        print("Internal Barometer")
        own_data["Bar"][1] = round(raw_barometer * barometer_altitude_comp_factor(altitude, own_data["Temp"][1]), 1)
        own_disp_values["Bar"] = own_disp_values["Bar"][1:] + [[own_data["Bar"][1], 1]]
        mqtt_values["Bar"][0] = own_data["Bar"][1]
        luft_values["pressure"] = "{:.2f}".format(raw_barometer * 100) # Send raw air pressure to Lufdaten, since it does its own altitude air pressure compensation
        print("Raw Bar:", round(raw_barometer, 1), "Comp Bar:", own_data["Bar"][1])
    else:
        print("External Barometer")
        own_data["Bar"][1] = round(float(es.barometer), 1)
        own_disp_values["Bar"] = own_disp_values["Bar"][1:] + [[own_data["Bar"][1], 1]]
        mqtt_values["Bar"][0] = own_data["Bar"][1]
        # Remove altitude compensation from external barometer because Lufdaten does its own altitude air pressure compensation
        luft_values["pressure"] = "{:.2f}".format(float(es.barometer) / barometer_altitude_comp_factor(altitude, own_data["Temp"][1]) * 100)
        print("Luft Bar:", luft_values["pressure"], "Comp Bar:", own_data["Bar"][1])
    red_in_ppm, oxi_in_ppm, nh3_in_ppm, comp_red_rs, comp_oxi_rs, comp_nh3_rs, raw_red_rs, raw_oxi_rs, raw_nh3_rs = read_gas_in_ppm(gas_calib_temp, gas_calib_hum, gas_calib_bar, raw_temp, raw_hum, raw_barometer, gas_sensors_warm)
    own_data["Red"][1] = round(red_in_ppm, 2)
    own_disp_values["Red"] = own_disp_values["Red"][1:] + [[own_data["Red"][1], 1]]
    mqtt_values["Red"] = own_data["Red"][1]
    own_data["Oxi"][1] = round(oxi_in_ppm, 2)
    own_disp_values["Oxi"] = own_disp_values["Oxi"][1:] + [[own_data["Oxi"][1], 1]]
    mqtt_values["Oxi"] = own_data["Oxi"][1]
    own_data["NH3"][1] = round(nh3_in_ppm, 2)
    own_disp_values["NH3"] = own_disp_values["NH3"][1:] + [[own_data["NH3"][1], 1]]
    mqtt_values["NH3"] = own_data["NH3"][1]
    mqtt_values["Gas Calibrated"] = gas_sensors_warm
    proximity = ltr559.get_proximity()
    if proximity < 500:
        own_data["Lux"][1] = round(ltr559.get_lux(), 1)
    else:
        own_data["Lux"][1] = 1
    own_disp_values["Lux"] = own_disp_values["Lux"][1:] + [[own_data["Lux"][1], 1]]
    mqtt_values["Lux"] = own_data["Lux"][1]
    return luft_values, mqtt_values, own_data, maxi_temp, mini_temp, own_disp_values, raw_red_rs, raw_oxi_rs, raw_nh3_rs, raw_temp, comp_temp, comp_hum, raw_hum, use_external_temp_hum, use_external_barometer, raw_barometer
    
def barometer_altitude_comp_factor(alt, temp):
    comp_factor = math.pow(1 - (0.0065 * altitude/(temp + 0.0065 * alt + 273.15)), -5.257)
    return comp_factor
    
def read_raw_gas():
    gas_data = gas.read_all()
    raw_red_rs = round(gas_data.reducing, 0)
    raw_oxi_rs = round(gas_data.oxidising, 0)
    raw_nh3_rs = round(gas_data.nh3, 0)
    return raw_red_rs, raw_oxi_rs, raw_nh3_rs
    
def read_gas_in_ppm(gas_calib_temp, gas_calib_hum, gas_calib_bar, raw_temp, raw_hum, raw_barometer, gas_sensors_warm):
    if gas_sensors_warm:
        comp_red_rs, comp_oxi_rs, comp_nh3_rs, raw_red_rs, raw_oxi_rs, raw_nh3_rs = comp_gas(gas_calib_temp, gas_calib_hum, gas_calib_bar, raw_temp, raw_hum, raw_barometer)
        print("Reading Compensated Gas sensors after warmup completed")
    else:
        raw_red_rs, raw_oxi_rs, raw_nh3_rs = read_raw_gas()
        comp_red_rs = raw_red_rs
        comp_oxi_rs = raw_oxi_rs
        comp_nh3_rs = raw_nh3_rs
        print("Reading Raw Gas sensors before warmup completed")
    print("Red Rs:", round(comp_red_rs, 0), "Oxi Rs:", round(comp_oxi_rs, 0), "NH3 Rs:", round(comp_nh3_rs, 0))
    if comp_red_rs/red_r0 > 0:
        red_ratio = comp_red_rs/red_r0
    else:
        red_ratio = 0.0001
    if comp_oxi_rs/oxi_r0 > 0:
        oxi_ratio = comp_oxi_rs/oxi_r0
    else:
        oxi_ratio = 0.0001
    if comp_nh3_rs/nh3_r0 > 0:
        nh3_ratio = comp_nh3_rs/nh3_r0
    else:
        nh3_ratio = 0.0001
    red_in_ppm = math.pow(10, -1.25 * math.log10(red_ratio) + 0.64)
    oxi_in_ppm = math.pow(10, math.log10(oxi_ratio) - 0.8129)
    nh3_in_ppm = math.pow(10, -1.8 * math.log10(nh3_ratio) - 0.163)
    return red_in_ppm, oxi_in_ppm, nh3_in_ppm, comp_red_rs, comp_oxi_rs, comp_nh3_rs, raw_red_rs, raw_oxi_rs, raw_nh3_rs

def comp_gas(gas_calib_temp, gas_calib_hum, gas_calib_bar, raw_temp, raw_hum, raw_barometer):
    gas_data = gas.read_all()
    gas_temp_diff = raw_temp - gas_calib_temp
    gas_hum_diff = raw_hum - gas_calib_hum
    gas_bar_diff = raw_barometer - gas_calib_bar
    raw_red_rs = round(gas_data.reducing, 0)
    comp_red_rs = round(raw_red_rs - (red_temp_comp_factor * gas_temp_diff + red_hum_comp_factor * gas_hum_diff + red_bar_comp_factor * gas_bar_diff), 0)
    raw_oxi_rs = round(gas_data.oxidising, 0)
    comp_oxi_rs = round(raw_oxi_rs - (oxi_temp_comp_factor * gas_temp_diff + oxi_hum_comp_factor * gas_hum_diff + oxi_bar_comp_factor * gas_bar_diff), 0)
    raw_nh3_rs = round(gas_data.nh3, 0)
    comp_nh3_rs = round(raw_nh3_rs - (nh3_temp_comp_factor * gas_temp_diff + nh3_hum_comp_factor * gas_hum_diff + nh3_bar_comp_factor * gas_bar_diff), 0)
    print("Gas Compensation. Raw Red Rs:", raw_red_rs, "Comp Red Rs:", comp_red_rs, "Raw Oxi Rs:", raw_oxi_rs, "Comp Oxi Rs:", comp_oxi_rs,
          "Raw NH3 Rs:", raw_nh3_rs, "Comp NH3 Rs:", comp_nh3_rs)
    return comp_red_rs, comp_oxi_rs, comp_nh3_rs, raw_red_rs, raw_oxi_rs, raw_nh3_rs   
    
def adjusted_temperature():
    raw_temp = bme280.get_temperature()
    #comp_temp = comp_temp_slope * raw_temp + comp_temp_intercept
    comp_temp = comp_temp_cub_a * math.pow(raw_temp, 3) + comp_temp_cub_b * math.pow(raw_temp, 2) + comp_temp_cub_c * raw_temp + comp_temp_cub_d
    return raw_temp, comp_temp

def adjusted_humidity():
    raw_hum = bme280.get_humidity()
    #comp_hum = comp_hum_slope * raw_hum + comp_hum_intercept
    comp_hum = comp_hum_quad_a * math.pow(raw_hum, 2) + comp_hum_quad_b * raw_hum + comp_hum_quad_c
    return raw_hum, min(100, comp_hum)
    
def log_climate_and_gas(run_time, own_data, raw_red_rs, raw_oxi_rs, raw_nh3_rs, raw_temp, comp_temp, comp_hum, raw_hum, use_external_temp_hum, use_external_barometer, raw_barometer): # Used to log climate and gas data to create compensation algorithms
    raw_temp = round(raw_temp, 2)
    raw_hum = round(raw_hum, 2)
    comp_temp = round(comp_temp, 2)
    comp_hum = round(comp_hum, 2)
    raw_barometer = round(raw_barometer, 1)
    raw_red_rs = round(raw_red_rs, 0)
    raw_oxi_rs = round(raw_oxi_rs, 0)
    raw_nh3_rs = round(raw_nh3_rs, 0)
    if use_external_temp_hum and use_external_barometer:
        environment_log_data = {'Run Time': run_time, 'Raw Temperature': raw_temp, 'Output Temp': comp_temp,
                             'Real Temperature': own_data["Temp"][1], 'Raw Humidity': raw_hum,
                             'Output Humidity': comp_hum, 'Real Humidity': own_data["Hum"][1], 'Real Bar': own_data["Bar"][1], 'Raw Bar': raw_barometer,
                             'Oxi': own_data["Oxi"][1], 'Red': own_data["Red"][1], 'NH3': own_data["NH3"][1], 'Raw OxiRS': raw_oxi_rs, 'Raw RedRS': raw_red_rs, 'Raw NH3RS': raw_nh3_rs}
    elif use_external_temp_hum and not(use_external_barometer):
        environment_log_data = {'Run Time': run_time, 'Raw Temperature': raw_temp, 'Output Temp': comp_temp,
                             'Real Temperature': own_data["Temp"][1], 'Raw Humidity': raw_hum,
                             'Output Humidity': comp_hum, 'Real Humidity': own_data["Hum"][1], 'Output Bar': own_data["Bar"][1], 'Raw Bar': raw_barometer,
                             'Oxi': own_data["Oxi"][1], 'Red': own_data["Red"][1], 'NH3': own_data["NH3"][1], 'Raw OxiRS': raw_oxi_rs, 'Raw RedRS': raw_red_rs, 'Raw NH3RS': raw_nh3_rs}     
    elif not(use_external_temp_hum) and use_external_barometer:
        environment_log_data = {'Run Time': run_time, 'Raw Temperature': raw_temp, 'Output Temp': comp_temp,
                             'Raw Humidity': raw_hum, 'Output Humidity': comp_hum, 'Real Bar': own_data["Bar"][1], 'Raw Bar': raw_barometer,
                             'Oxi': own_data["Oxi"][1], 'Red': own_data["Red"][1], 'NH3': own_data["NH3"][1], 'Raw OxiRS': raw_oxi_rs, 'Raw RedRS': raw_red_rs, 'Raw NH3RS': raw_nh3_rs}
    else:
        environment_log_data = {'Run Time': run_time, 'Raw Temperature': raw_temp, 'Output Temp': comp_temp,
                             'Raw Humidity': raw_hum, 'Output Humidity': comp_hum, 'Output Bar': own_data["Bar"][1], 'Raw Bar': raw_barometer,
                             'Oxi': own_data["Oxi"][1], 'Red': own_data["Red"][1], 'NH3': own_data["NH3"][1], 'Raw OxiRS': raw_oxi_rs, 'Raw RedRS': raw_red_rs, 'Raw NH3RS': raw_nh3_rs}
    print('Logging Environment Data.', environment_log_data)
    with open('<Your environment log file location>', 'a') as f:
        f.write(',\n' + json.dumps(environment_log_data))

# Calculate AQI Level
def max_aqi_level_factor(gas_sensors_warm, air_quality_data, air_quality_data_no_gas, data):
    max_aqi_level = 0
    max_aqi_factor = 'All'
    max_aqi = [max_aqi_factor, max_aqi_level]
    if gas_sensors_warm:
        aqi_data = air_quality_data
    else:
        aqi_data = air_quality_data_no_gas
    for aqi_factor in aqi_data:
        aqi_factor_level = 0
        thresholds = data[aqi_factor][2]
        for level in range(len(thresholds)):
            if data[aqi_factor][1] > thresholds[level]:
                aqi_factor_level = level + 1
        if aqi_factor_level > max_aqi[1]:
            max_aqi = [aqi_factor, aqi_factor_level]
    return max_aqi
        
# Get Raspberry Pi serial number to use as ID
def get_serial_number():
    with open('/proc/cpuinfo', 'r') as f:
        for line in f:
            if line[0:6] == 'Serial':
                return line.split(":")[1].strip()

# Check for Wi-Fi connection
def check_wifi():
    if check_output(['hostname', '-I']):
        return True
    else:
        return False

# Display Error Message on LCD
def display_error(message):
    text_colour = (255, 255, 255)
    back_colour = (85, 15, 15)
    error_message = "System Error\n{}".format(message)
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    size_x, size_y = draw.textsize(message, mediumfont)
    x = (WIDTH - size_x) / 2
    y = (HEIGHT / 2) - (size_y / 2)
    draw.rectangle((0, 0, 160, 80), back_colour)
    draw.text((x, y), error_message, font=mediumfont, fill=text_colour)
    disp.display(img)

# Display the Raspberry Pi serial number on a background colour based on the air quality level
def disabled_display(gas_sensors_warm, air_quality_data, air_quality_data_no_gas, data, palette):
    max_aqi = max_aqi_level_factor(gas_sensors_warm, air_quality_data, air_quality_data_no_gas, data)
    back_colour = palette[max_aqi[1]]
    text_colour = (255, 255, 255)
    id = get_serial_number()
    message = "{}".format(id)
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    size_x, size_y = draw.textsize(message, mediumfont)
    x = (WIDTH - size_x) / 2
    y = (HEIGHT / 2) - (size_y / 2)
    draw.rectangle((0, 0, 160, 80), back_colour)
    draw.text((x, y), message, font=mediumfont, fill=text_colour)
    disp.display(img)
    
# Display Raspberry Pi serial and Wi-Fi status on LCD
def display_status():
    wifi_status = "connected" if check_wifi() else "disconnected"
    text_colour = (255, 255, 255)
    back_colour = (0, 170, 170) if check_wifi() else (85, 15, 15)
    id = get_serial_number()
    message = "Northcliff\nEnvironment Monitor\n{}\nWi-Fi: {}".format(id, wifi_status)
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    size_x, size_y = draw.textsize(message, mediumfont)
    x = (WIDTH - size_x) / 2
    y = (HEIGHT / 2) - (size_y / 2)
    draw.rectangle((0, 0, 160, 80), back_colour)
    draw.text((x, y), message, font=mediumfont, fill=text_colour)
    disp.display(img)
    
def send_data_to_aio(feed_key, data):
    aio_json = {"value": data}
    resp_error = False
    reason = ''
    response = ''
    try:
        response = requests.post(aio_url + '/feeds/' + feed_key + '/data',
                                 headers={'X-AIO-Key': aio_key,
                                          'Content-Type': 'application/json'},
                                 data=json.dumps(aio_json), timeout=5)
        status_code = response.status_code
    except requests.exceptions.ConnectionError as e:
        resp_error = True
        reason = 'aio Connection Error'
        print('aio Connection Error', e)
    except requests.exceptions.Timeout as e:
        resp_error = True
        reason = 'aio Timeout Error'
        print('aio Timeout Error', e)
    except requests.exceptions.HTTPError as e:
        resp_error = True
        reason = 'aio HTTP Error'
        print('aio HTTP Error', e)     
    except requests.exceptions.RequestException as e:
        resp_error = True
        reason = 'aio Request Error'
        print('aio Request Error', e)
    else:
        if status_code == 429:
            resp_error = True
            reason = 'Throttling Error'
            print('aio Throttling Error')
        elif status_code >= 400:
            resp_error = True
            reason = 'Response Error: ' + str(response.status_code)
            print('aio ', reason)
    return not resp_error

def send_to_luftdaten(luft_values, id, enable_particle_sensor):
    print("Sending Data to Luftdaten")
    if enable_particle_sensor:
        pm_values = dict(i for i in luft_values.items() if i[0].startswith("P"))
    temp_values = dict(i for i in luft_values.items() if not i[0].startswith("P"))
    resp1_exception = False
    resp2_exception = False

    if enable_particle_sensor:
        try:
            resp_1 = requests.post("https://api.luftdaten.info/v1/push-sensor-data/",
                     json={
                         "software_version": "enviro-plus 0.0.1",
                         "sensordatavalues": [{"value_type": key, "value": val} for
                                              key, val in pm_values.items()]
                     },
                     headers={
                         "X-PIN":   "1",
                         "X-Sensor": id,
                         "Content-Type": "application/json",
                         "cache-control": "no-cache"
                     },
                    timeout=5
            )
        except requests.exceptions.ConnectionError as e:
            resp1_exception = True
            print('Luftdaten PM Connection Error', e)
        except requests.exceptions.Timeout as e:
            resp1_exception = True
            print('Luftdaten PM Timeout Error', e)
        except requests.exceptions.RequestException as e:
            resp1_exception = True
            print('Luftdaten PM Request Error', e)

    try:
        resp_2 = requests.post("https://api.luftdaten.info/v1/push-sensor-data/",
                 json={
                     "software_version": "enviro-plus 0.0.1",
                     "sensordatavalues": [{"value_type": key, "value": val} for
                                          key, val in temp_values.items()]
                 },
                 headers={
                     "X-PIN":   "11",
                     "X-Sensor": id,
                     "Content-Type": "application/json",
                     "cache-control": "no-cache"
                 },
                timeout=5
        )
    except requests.exceptions.ConnectionError as e:
        resp2_exception = True
        print('Luftdaten Climate Connection Error', e)
    except requests.exceptions.Timeout as e:
        resp2_exception = True
        print('Luftdaten Climate Timeout Error', e)
    except requests.exceptions.RequestException as e:
        resp2_exception = True
        print('Luftdaten Climate Request Error', e)

    if resp1_exception == False and resp2_exception == False:
        if resp_1.ok and resp_2.ok:
            return True
        else:
            return False
    else:
        return False
    
def on_connect(client, userdata, flags, rc):
    es.print_update('Northcliff Environment Monitor Connected with result code ' + str(rc))
    if enable_receive_data_from_homemanager:
        client.subscribe(incoming_temp_hum_mqtt_topic) # Subscribe to the topic for the external temp/hum data
        client.subscribe(incoming_barometer_mqtt_topic) # Subscribe to the topic for the external barometer data
    if enable_indoor_outdoor_functionality and indoor_outdoor_function == 'Indoor':
        client.subscribe(outdoor_mqtt_topic)

def on_message(client, userdata, msg):
    decoded_payload = str(msg.payload.decode("utf-8"))
    parsed_json = json.loads(decoded_payload)
    if msg.topic == incoming_temp_hum_mqtt_topic and parsed_json['name'] == incoming_temp_hum_mqtt_sensor_name: # Identify external temp/hum sensor
        es.capture_temp_humidity(parsed_json)
    if msg.topic == incoming_barometer_mqtt_topic and parsed_json['idx'] == incoming_barometer_sensor_id: # Identify external barometer
        es.capture_barometer(parsed_json['svalue'])
    if enable_indoor_outdoor_functionality and indoor_outdoor_function == 'Indoor' and msg.topic == outdoor_mqtt_topic:
        capture_outdoor_data(parsed_json)
            
def capture_outdoor_data(parsed_json):
    global outdoor_reading_captured
    global outdoor_reading_captured_time
    global outdoor_data
    global outdoor_maxi_temp
    global outdoor_mini_temp
    global outdoor_disp_values
    global outdoor_gas_sensors_warm
    for reading in outdoor_data:
        if reading == "Bar" or reading == "Hum": # Barometer and Humidity readings have their data in lists
            outdoor_data[reading][1] = parsed_json[reading][0]
        else:
            outdoor_data[reading][1] = parsed_json[reading]
        outdoor_disp_values[reading] = outdoor_disp_values[reading][1:] + [[outdoor_data[reading][1], 1]]
    outdoor_maxi_temp = parsed_json["Max Temp"]
    outdoor_mini_temp = parsed_json["Min Temp"]
    outdoor_gas_sensors_warm = parsed_json["Gas Calibrated"]
    outdoor_reading_captured = True
    outdoor_reading_captured_time = time.time()
    
# Displays graphed data and text on the 0.96" LCD
def display_graphed_data(location, disp_values, variable, data, WIDTH):
    # Scale the received disp_values for the variable between 0 and 1
    received_disp_values = [disp_values[variable][v][0]*disp_values[variable][v][1] for v in range(len(disp_values[variable]))]
    graph_range = [(v - min(received_disp_values)) / (max(received_disp_values) - min(received_disp_values)) if ((max(received_disp_values) - min(received_disp_values)) != 0)
                   else 0 for v in received_disp_values]           
    # Format the variable name and value
    if variable == "Oxi":
        message = "{} {}: {:.2f} {}".format(location, variable[:4], data[1], data[0])
    elif variable == "Bar":
        message = "{}: {:.1f} {}".format(variable[:4], data[1], data[0])
    elif variable[:1] == "P" or variable == "Red" or variable == "NH3" or variable == "Hum" or variable == "Lux":
        message = "{} {}: {:.0f} {}".format(location, variable[:4], round(data[1], 0), data[0])
    else:
        message = "{} {}: {:.1f} {}".format(location, variable[:4], data[1], data[0])
    #logging.info(message)
    draw.rectangle((0, 0, WIDTH, HEIGHT), (255, 255, 255))
    # Determine the backgound colour for received data, based on level thresholds. Black for data not received.
    for i in range(len(disp_values[variable])):
        if disp_values[variable][i][1] == 1:
            lim = data[2]
            rgb = palette[0]
            for j in range(len(lim)):
                if disp_values[variable][i][0] > lim[j]:
                    rgb = palette[j+1]
        else:
            rgb = (0,0,0)
        # Draw a 2-pixel wide rectangle of colour based on reading levels relative to level thresholds
        draw.rectangle((i*2, top_pos, i*2+2, HEIGHT), rgb)
        # Draw a 2 pixel by 2 pixel line graph in black based on the reading levels
        line_y = (HEIGHT-2) - ((top_pos + 1) + (graph_range[i] * ((HEIGHT-2) - (top_pos + 1)))) + (top_pos + 1)
        draw.rectangle((i*2, line_y, i*2+2, line_y+2), (0, 0, 0))
    # Write the text at the top in black
    draw.text((0, 0), message, font=font_ml, fill=(0, 0, 0))
    disp.display(img)

# Displays the weather forecast on the 0.96" LCD
def display_forecast(valid_barometer_history, forecast, barometer_available_time, barometer, barometer_change):
    text_colour = (255, 255, 255)
    back_colour = (0, 0, 0)
    if valid_barometer_history:
        message = "Barometer {:.0f} hPa\n3Hr Change {:.0f} hPa\n{}".format(round(barometer, 0), round(barometer_change, 0), forecast)
    else:
        minutes_to_forecast = (barometer_available_time - time.time()) / 60
        if minutes_to_forecast >= 2:
            message = "WEATHER FORECAST\nReady in {:.0f} minutes".format(minutes_to_forecast)
        elif minutes_to_forecast > 0 and minutes_to_forecast < 2:
            message = "WEATHER FORECAST\nReady in a minute"
        else:
            message = "WEATHER FORECAST\nPreparing Summary\nPlease Wait..."
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    size_x, size_y = draw.textsize(message, mediumfont)
    x = (WIDTH - size_x) / 2
    y = (HEIGHT / 2) - (size_y / 2)
    draw.rectangle((0, 0, 160, 80), back_colour)
    draw.text((x, y), message, font=mediumfont, fill=text_colour)
    disp.display(img)
    
# Displays all the air quality text on the 0.96" LCD
def display_all_aq(location, data, data_in_display_all_aq):
    draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
    column_count = 2
    draw.text((2, 2), location + ' AIR QUALITY', font=font_ml, fill=(255, 255, 255))
    row_count = round((len(data_in_display_all_aq) / column_count), 0)
    for i in data_in_display_all_aq:
        data_value = data[i][1]
        unit = data[i][0]
        column = int(data[i][3] / row_count)
        row = data[i][3] % row_count
        x = x_offset + ((WIDTH/column_count) * column)
        y = y_offset + ((HEIGHT/(row_count + 1) * (row +1)))
        if i == "Oxi":
            message = "{}: {:.2f}".format(i, data_value)
        else:
            message = "{}: {:.0f}".format(i, round(data_value, 0))
        lim = data[i][2]
        rgb = palette[0]
        for j in range(len(lim)):
            if data_value > lim[j]:
                rgb = palette[j+1]
        draw.text((x, y), message, font=font_ml, fill=rgb)
    disp.display(img)

def display_results(start_current_display, current_display_is_own, display_modes, indoor_outdoor_display_duration, own_data, data_in_display_all_aq, outdoor_data, outdoor_reading_captured,
                    own_disp_values, outdoor_disp_values, delay, last_page, mode, luft_values, mqtt_values, WIDTH, valid_barometer_history, forecast,
                    barometer_available_time, barometer_change, barometer_trend, icon_forecast, maxi_temp, mini_temp, air_quality_data, air_quality_data_no_gas,
                    gas_sensors_warm, outdoor_gas_sensors_warm, enable_display, palette):
    # Allow for display selection if display is enabled, else only display the serial number on a background colour based on max_aqi
    if enable_display:
        proximity = ltr559.get_proximity()
        # If the proximity crosses the threshold, toggle the mode
        if proximity > 1500 and time.time() - last_page > delay:
            mode += 1
            mode %= len(display_modes)
            print('Mode', mode)
        selected_display_mode = display_modes[mode]
        if enable_indoor_outdoor_functionality and indoor_outdoor_function == 'Indoor':
            if outdoor_reading_captured:
                if ((time.time() -  start_current_display) > indoor_outdoor_display_duration):
                    current_display_is_own = not current_display_is_own
                    start_current_display = time.time()
            else:
                current_display_is_own = True
        if selected_display_mode in own_data:
            if current_display_is_own and indoor_outdoor_function == 'Indoor' or selected_display_mode == "Bar":
                display_graphed_data('IN', own_disp_values, selected_display_mode, own_data[selected_display_mode], WIDTH)
            elif current_display_is_own and indoor_outdoor_function == 'Outdoor':
                display_graphed_data('OUT', own_disp_values, selected_display_mode, own_data[selected_display_mode], WIDTH)
            else:
                display_graphed_data('OUT', outdoor_disp_values, selected_display_mode, outdoor_data[selected_display_mode], WIDTH)
        elif selected_display_mode == "Forecast":
            display_forecast(valid_barometer_history, forecast, barometer_available_time, own_data["Bar"][1], barometer_change)
        elif selected_display_mode == "Status":
            display_status()
        elif selected_display_mode == "All Air":
            # Display everything on one screen
            if current_display_is_own and indoor_outdoor_function == 'Indoor':
                display_all_aq('IN', own_data, data_in_display_all_aq)
            elif current_display_is_own and indoor_outdoor_function == 'Outdoor':
                display_all_aq('OUT', own_data, data_in_display_all_aq)
            else:
                display_all_aq('OUT', outdoor_data, data_in_display_all_aq)
        elif selected_display_mode == "Icon Weather":
            # Display icon weather/aqi
            if current_display_is_own and indoor_outdoor_function == 'Indoor':
                display_icon_weather_aqi('IN', own_data, barometer_trend, icon_forecast, maxi_temp, mini_temp, air_quality_data,
                                         air_quality_data_no_gas, icon_air_quality_levels, gas_sensors_warm)
            elif current_display_is_own and indoor_outdoor_function == 'Outdoor':
                display_icon_weather_aqi('OUT', own_data, barometer_trend, icon_forecast, maxi_temp, mini_temp, air_quality_data,
                                         air_quality_data_no_gas, icon_air_quality_levels, gas_sensors_warm)
            else:
                display_icon_weather_aqi('OUT', outdoor_data, barometer_trend, icon_forecast, outdoor_maxi_temp, outdoor_mini_temp,
                                         air_quality_data, air_quality_data_no_gas, icon_air_quality_levels, outdoor_gas_sensors_warm)
        else:
            pass
    else:
        disabled_display(gas_sensors_warm, air_quality_data, air_quality_data_no_gas, own_data, palette)
    last_page = time.time()
    return last_page, mode, start_current_display, current_display_is_own


class ExternalSensors(object): # Handles the external temp/hum sensors
    def __init__(self):
        self.barometer_update_time = 0
        self.temp_humidity_update_time = 0
        #self.print_update('Instantiated External Sensors')
        
    def capture_barometer(self, value):
        self.barometer = value[:-2] # Remove forecast data
        self.barometer_update_time = time.time()
        #self.print_update('External Barometer ' + self.barometer + ' Pa')

    def capture_temp_humidity(self, parsed_json):
        self.temperature = parsed_json['svalue1']+'0'
        #self.print_update('External Temperature ' + self.temperature + ' degrees C')
        self.humidity = parsed_json['svalue2']+'.00'
        #self.print_update('External Humidity ' + self.humidity + '%')
        self.temp_humidity_update_time = time.time()
        
    def check_valid_readings(self, check_time):
        if check_time - self.barometer_update_time < 500:
            valid_barometer_reading = True
        else:
            valid_barometer_reading = False
        if check_time - self.temp_humidity_update_time < 500:
            valid_temp_humidity_reading = True
        else:
            valid_temp_humidity_reading = False
        return valid_temp_humidity_reading, valid_barometer_reading

    def print_update(self, message):
        today = datetime.now()
        print('')
        print(message + ' on ' + today.strftime('%A %d %B %Y @ %H:%M:%S'))
        
def log_barometer(barometer, barometer_history): # Logs 3 hours of barometer readings, taken every 20 minutes
    barometer_log_time = time.time()
    three_hour_barometer=barometer_history[8] # Capture barometer reading from 3 hours ago
    for pointer in range (8, 0, -1): # Move previous temperatures one position in the list to prepare for new temperature to be recorded
        barometer_history[pointer] = barometer_history[pointer - 1]
    barometer_history[0] = barometer # Log latest reading
    if three_hour_barometer!=0:
        valid_barometer_history = True
        barometer_change = barometer - three_hour_barometer
        if barometer_change > -1.1 and barometer_change < 1.1:
            barometer_trend = '-'
        elif barometer_change <= -1.1 and barometer_change > -4:
            barometer_trend = '<'
        elif barometer_change <= -4 and barometer_change > -10:
            barometer_trend = '<<'
        elif barometer_change <= -10:
            barometer_trend = '<!'
        elif barometer_change >= 1.1 and barometer_change < 6:
            barometer_trend = '>'
        elif barometer_change >= 6 and barometer_change < 10:
            barometer_trend = '>>'
        elif barometer_change >= 10:
            barometer_trend = '>!'
        else:
            pass
        forecast, icon_forecast, domoticz_forecast, aio_forecast = analyse_barometer(barometer_change, barometer)
    else:
        valid_barometer_history=False
        forecast = 'Insufficient Data'
        icon_forecast = 'Wait'
        aio_forecast = 'question'
        domoticz_forecast = '0'
        barometer_change = 0
        barometer_trend = ''
    #print("Log Barometer")
    #print("Result", barometer_history, "Valid Barometer History is", valid_barometer_history, "3 Hour Barometer Change is", round(barometer_change,2), "millibars")
    return barometer_history, barometer_change, valid_barometer_history, barometer_log_time, forecast, barometer_trend, icon_forecast, domoticz_forecast, aio_forecast

def analyse_barometer(barometer_change, barometer):
    if barometer<1009:
        if barometer_change>-1.1 and barometer_change<6:
            forecast = 'Clearing and Colder'
            icon_forecast = 'Fair'
            domoticz_forecast = '1'
            aio_forecast = 'thermometer-quarter'
        elif barometer_change>=6 and barometer_change<10:
            forecast = 'Strong Wind Warning'
            icon_forecast = 'Windy'
            domoticz_forecast = '3'
            aio_forecast = 'w:wind-beaufort-7'
        elif barometer_change>=10:
            forecast = 'Gale Warning'
            icon_forecast = 'Gale'
            domoticz_forecast = '4'
            aio_forecast = 'w:wind-beaufort-9'
        elif barometer_change<=-1.1 and barometer_change>=-4:
            forecast = 'Rain and Wind'
            icon_forecast = 'Rain'
            domoticz_forecast = '4'
            aio_forecast = 'w:rain-wind'
        elif barometer_change<-4 and barometer_change>-10:
            forecast = 'Storm'
            icon_forecast = 'Storm'
            domoticz_forecast = '4'
            aio_forecast = 'w:thunderstorm'
        else:
            forecast = 'Storm and Gale'
            icon_forecast = 'Gale'
            domoticz_forecast = '4'
            aio_forecast = 'w:thunderstorm'
    elif barometer>=1009 and barometer <=1018:
        if barometer_change>-4 and barometer_change<1.1:
            forecast = 'No Change'
            icon_forecast = 'Stable'
            domoticz_forecast = '0'
            aio_forecast = 'balance-scale'
        elif barometer_change>=1.1 and barometer_change<=6 and barometer<=1015:
            forecast = 'No Change'
            icon_forecast = 'Stable'
            domoticz_forecast = '0'
            aio_forecast = 'balance-scale'
        elif barometer_change>=1.1 and barometer_change<=6 and barometer>1015:
            forecast = 'Poorer Weather'
            icon_forecast = 'Poorer'
            domoticz_forecast = '3'
            aio_forecast = 'w:cloud'
        elif barometer_change>=6 and barometer_change<10:
            forecast = 'Strong Wind Warning'
            icon_forecast = 'Windy'
            domoticz_forecast = '3'
            aio_forecast = 'w:wind-beaufort-7'
        elif barometer_change>=10:
            forecast = 'Gale Warning'
            icon_forecast = 'Gale'
            domoticz_forecast = '4'
            aio_forecast = 'w:wind-beaufort-9'
        else:
            forecast = 'Rain and Wind'
            icon_forecast = 'Rain'
            domoticz_forecast = '4'
            aio_forecast = 'w:rain-wind'
    elif barometer>1018 and barometer <=1023:
        if barometer_change>0 and barometer_change<1.1:
            forecast = 'No Change'
            icon_forecast = 'Stable'
            domoticz_forecast = '0'
            aio_forecast = 'balance-scale'
        elif barometer_change>=1.1 and barometer_change<6:
            forecast = 'Poorer Weather'
            icon_forecast = 'Poorer'
            domoticz_forecast = '3'
            aio_forecast = 'w:cloud'
        elif barometer_change>=6 and barometer_change<10:
            forecast = 'Strong Wind Warning'
            icon_forecast = 'Windy'
            domoticz_forecast = '3'
            aio_forecast = 'w:wind-beaufort-7'
        elif barometer_change>=10:
            forecast = 'Gale Warning'
            icon_forecast = 'Gale'
            domoticz_forecast = '4'
            aio_forecast = 'w:wind-beaufort-9'
        elif barometer_change>-1.1 and barometer_change<=0:
            forecast = 'Fair Weather with\nSlight Temp Change'
            icon_forecast = 'Fair'
            domoticz_forecast = '1'
            aio_forecast = 'w:day-sunny'
        elif barometer_change<=-1.1 and barometer_change>-4:
            forecast = 'No Change but\nRain in 24 Hours'
            icon_forecast = 'Stable'
            domoticz_forecast = '0'
            aio_forecast = 'balance-scale'
        else:
            forecast = 'Rain, Wind and\n Higher Temp'
            icon_forecast = 'Rain'
            domoticz_forecast = '4'
            aio_forecast = 'w:rain-wind'
    else: # barometer>1023
        if barometer_change>0 and barometer_change<1.1:
            forecast = 'Fair Weather'
            icon_forecast = 'Fair'
            domoticz_forecast = '1'
            aio_forecast = 'w:day-sunny'
        elif barometer_change>-1.1 and barometer_change<=0:
            forecast = 'Fair Weather with\nLittle Temp Change'
            icon_forecast = 'Fair'
            domoticz_forecast = '1'
            aio_forecast = 'w:day-sunny'
        elif barometer_change>=1.1 and barometer_change<6:
            forecast = 'Poorer Weather'
            icon_forecast = 'Poorer'
            domoticz_forecast = '3'
            aio_forecast = 'w:cloud'
        elif barometer_change>=6 and barometer_change<10:
            forecast = 'Strong Wind Warning'
            icon_forecast = 'Windy'
            domoticz_forecast = '3'
            aio_forecast = 'w:wind-beaufort-7'
        elif barometer_change>=10:
            forecast = 'Gale Warning'
            icon_forecast = 'Gale'
            domoticz_forecast = '4'
            aio_forecast = 'w:wind-beaufort-9'
        elif barometer_change<=-1.1 and barometer_change>-4:
            forecast = 'Fair Weather and\nSlowly Rising Temp'
            icon_forecast = 'Fair'
            domoticz_forecast = '1'
            aio_forecast = 'w:day-sunny'
        else:
            forecast = 'Warming Trend'
            icon_forecast = 'Fair'
            domoticz_forecast = '1'
            aio_forecast = 'thermometer-three-quarters'
    print('3 hour barometer change is '+str(round(barometer_change,1))+' millibars with a current reading of '+str(round(barometer,1))+' millibars. The weather forecast is '+forecast) 
    return forecast, icon_forecast, domoticz_forecast, aio_forecast

# Icon Display Methods
def calculate_y_pos(x, centre):
    """Calculates the y-coordinate on a parabolic curve, given x."""
    centre = 80
    y = 1 / centre * (x - centre) ** 2 + sun_radius

    return int(y)


def circle_coordinates(x, y, radius):
    """Calculates the bounds of a circle, given centre and radius."""

    x1 = x - radius  # Left
    x2 = x + radius  # Right
    y1 = y - radius  # Bottom
    y2 = y + radius  # Top

    return (x1, y1, x2, y2)


def map_colour(x, centre, icon_aqi_level, day):
    """Given an x coordinate and a centre point, an aqi hue (in degrees),
       and a Boolean for day or night (day is True, night False), calculate a colour
       hue representing the 'colour' of that aqi level."""
    sat = 1.0
    # Dim the brightness as you move from the centre to the edges
    val = 0.8 - 0.6 * (abs(centre - x) / (2 * centre))
    # Select the hue based on the max aqi level and rescale between 0 and 1
    hue = icon_background_hue[icon_aqi_level]/360
    # Reverse dimming at night
    if not day:
        val = 1 - val
    #print(day, x, hue, sat, val)
    r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(hue, sat, val)]
    return (r, g, b)


def x_from_sun_moon_time(progress, period, x_range):
    """Recalculate/rescale an amount of progress through a time period."""
    x = int((progress / period) * x_range)
    return x


def sun_moon_time(city_name, time_zone):
    """Calculate the progress through the current sun/moon period (i.e day or
       night) from the last sunrise or sunset, given a datetime object 't'."""

    city = lookup(city_name, db)

    # Datetime objects for yesterday, today, tomorrow
    utc = pytz.utc
    utc_dt = datetime.now(tz=utc)
    local_dt = utc_dt.astimezone(pytz.timezone(time_zone))
    today = local_dt.date()
    yesterday = today - timedelta(1)
    tomorrow = today + timedelta(1)

    # Sun objects for yesterday, today, tomorrow
    sun_yesterday = sun(city.observer, date=yesterday)
    sun_today = sun(city.observer, date=today)
    sun_tomorrow = sun(city.observer, date=tomorrow)

    # Work out sunset yesterday, sunrise/sunset today, and sunrise tomorrow
    sunset_yesterday = sun_yesterday["sunset"]
    sunrise_today = sun_today["sunrise"]
    sunset_today = sun_today["sunset"]
    sunrise_tomorrow = sun_tomorrow["sunrise"]

    # Work out lengths of day or night period and progress through period
    if sunrise_today < local_dt < sunset_today:
        day = True
        period = sunset_today - sunrise_today
        mid = sunrise_today + (period / 2)
        progress = local_dt - sunrise_today

    elif local_dt > sunset_today:
        day = False
        period = sunrise_tomorrow - sunset_today
        mid = sunset_today + (period / 2)
        progress = local_dt - sunset_today

    else:
        day = False
        period = sunrise_today - sunset_yesterday
        mid = sunset_yesterday + (period / 2)
        progress = local_dt - sunset_yesterday

    # Convert time deltas to seconds
    progress = progress.total_seconds()
    period = period.total_seconds()

    return (progress, period, day, local_dt)

def draw_background(progress, period, day, icon_aqi_level):
    """Given an amount of progress through the day or night, draw the
       background colour and overlay a blurred sun/moon."""

    # x-coordinate for sun/moon
    x = x_from_sun_moon_time(progress, period, WIDTH)

    # If it's day, then move right to left
    if day:
        x = WIDTH - x

    # Calculate position on sun/moon's curve
    centre = WIDTH / 2
    y = calculate_y_pos(x, centre)

    # Background colour
    background = map_colour(x, 80, icon_aqi_level, day)
    

    # New image for background colour
    img = Image.new('RGBA', (WIDTH, HEIGHT), color=background)
    draw = ImageDraw.Draw(img)

    # New image for sun/moon overlay
    overlay = Image.new('RGBA', (WIDTH, HEIGHT), color=(0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Draw the sun/moon
    circle = circle_coordinates(x, y, sun_radius)
    if day:
        overlay_draw.ellipse(circle, fill=(180, 180, 0, opacity), outline = (0, 0, 0))

    # Overlay the sun/moon on the background
    composite = Image.alpha_composite(img, overlay).filter(ImageFilter.GaussianBlur(radius=blur))

    return composite

def overlay_text(img, position, text, font, align_right=False, rectangle=False):
    draw = ImageDraw.Draw(img)
    w, h = font.getsize(text)
    if align_right:
        x, y = position
        x -= w
        position = (x, y)
    if rectangle:
        x += 1
        y += 1
        position = (x, y)
        border = 1
        rect = (x - border, y, x + w, y + h + border)
        rect_img = Image.new('RGBA', (WIDTH, HEIGHT), color=(0, 0, 0, 0))
        rect_draw = ImageDraw.Draw(rect_img)
        rect_draw.rectangle(rect, (255, 255, 255))
        rect_draw.text(position, text, font=font, fill=(0, 0, 0, 0))
        img = Image.alpha_composite(img, rect_img)
    else:
        draw.text(position, text, font=font, fill=(255, 255, 255))
    return img

def describe_humidity(humidity):
    """Convert relative humidity into wet/good/dry description."""
    if 30 < humidity < 70:
        description = "good"
    elif humidity >= 70:
        description = "wet"
    else:
        description = "dry"
    return description

def display_icon_weather_aqi(location, data, barometer_trend, icon_forecast, maxi_temp, mini_temp, air_quality_data,
                             air_quality_data_no_gas, icon_air_quality_levels, gas_sensors_warm):
    progress, period, day, local_dt = sun_moon_time(city_name, time_zone)

    # Calculate AQI
    max_aqi = max_aqi_level_factor(gas_sensors_warm, air_quality_data, air_quality_data_no_gas, data)

    # Background
    background = draw_background(progress, period, day, max_aqi[1])

    # Time.
    date_string = local_dt.strftime("%d %b %y").lstrip('0')
    time_string = local_dt.strftime("%H:%M") + '  ' + location
    img = overlay_text(background, (0 + margin, 0 + margin), time_string, font_smm)
    img = overlay_text(img, (WIDTH - margin, 0 + margin), date_string, font_smm, align_right=True)
    temp_string = f"{data['Temp'][1]:.0f}°C"
    img = overlay_text(img, (68, 18), temp_string, font_smm, align_right=True)
    spacing = font_smm.getsize(temp_string)[1] + 1
    if mini_temp is not None and maxi_temp is not None:
        range_string = f"{mini_temp:.0f}-{maxi_temp:.0f}"
    else:
        range_string = "------"
    img = overlay_text(img, (68, 18 + spacing), range_string, font_sm, align_right=True, rectangle=True)
    temp_icon = Image.open(path + "/icons/temperature.png")
    img.paste(temp_icon, (margin, 18), mask=temp_icon)

    # Humidity
    corr_humidity = data["Hum"][1]
    humidity_string = f"{corr_humidity:.0f}%"
    img = overlay_text(img, (68, 48), humidity_string, font_smm, align_right=True)
    spacing = font_smm.getsize(humidity_string)[1] + 1
    humidity_desc = describe_humidity(corr_humidity).upper()
    img = overlay_text(img, (68, 48 + spacing), humidity_desc, font_sm, align_right=True, rectangle=True)
    humidity_icon = Image.open(path + "/icons/humidity-" + humidity_desc.lower() + ".png")
    img.paste(humidity_icon, (margin, 48), mask=humidity_icon)
                
    # AQI
    aqi_string = f"{max_aqi[1]}: {max_aqi[0]}"
    img = overlay_text(img, (WIDTH - margin, 18), aqi_string, font_smm, align_right=True)
    spacing = font_smm.getsize(aqi_string)[1] + 1
    aqi_desc = icon_air_quality_levels[max_aqi[1]].upper()
    img = overlay_text(img, (WIDTH - margin - 1, 18 + spacing), aqi_desc, font_sm, align_right=True, rectangle=True)
    #aqi_icon = Image.open(path + "/icons/aqi-" + icon_air_quality_levels[max_aqi[1]].lower() +  ".png")
    aqi_icon = Image.open(path + "/icons/aqi.png")
    img.paste(aqi_icon, (80, 18), mask=aqi_icon)

    # Pressure
    pressure = data["Bar"][1]
    pressure_string = f"{int(pressure)} {barometer_trend}"
    img = overlay_text(img, (WIDTH - margin, 48), pressure_string, font_smm, align_right=True)
    pressure_desc = icon_forecast.upper()
    spacing = font_smm.getsize(pressure_string)[1] + 1
    img = overlay_text(img, (WIDTH - margin - 1, 48 + spacing), pressure_desc, font_sm, align_right=True, rectangle=True)
    pressure_icon = Image.open(path + "/icons/weather-" + pressure_desc.lower() +  ".png")
    img.paste(pressure_icon, (80, 48), mask=pressure_icon)

    # Display image
    disp.display(img)
    
def update_aio(mqtt_values, forecast, aio_format, aio_forecast_text_format, aio_forecast_icon_format, aio_air_quality_level_format,
               air_quality_text_format, own_data, icon_air_quality_levels, aio_forecast, aio_package, gas_sensors_warm, air_quality_data,
               air_quality_data_no_gas, previous_aio_air_quality_level, previous_aio_air_quality_text, previous_aio_forecast_text, previous_aio_forecast):
    aio_resp = False # Set to True when there is at least one successful aio feed response
    aio_json = {}
    aio_path = '/feeds/'
    if gas_sensors_warm and aio_package == "Premium":
        print("Sending Premium package feeds to Adafruit IO with Gas Data")
    elif gas_sensors_warm == False and aio_package == "Premium":
        print("Sending Premium package feeds to Adafruit IO without Gas Data")
    else:
        print("Sending", aio_package, "package feeds to Adafruit IO")
    # Analyse air quality levels and combine into an overall air quality level based on own_data thesholds
    max_aqi = max_aqi_level_factor(gas_sensors_warm, air_quality_data, air_quality_data_no_gas, own_data)
    combined_air_quality_level_factor = max_aqi[0]
    combined_air_quality_level = max_aqi[1]
    combined_air_quality_text = icon_air_quality_levels[combined_air_quality_level] + ": " + combined_air_quality_level_factor
    if combined_air_quality_level != previous_aio_air_quality_level: # Only update if it's changed
        print('Sending Air Quality Level Feed')
        aio_json['value'] = combined_air_quality_level
        feed_resp = send_data_to_aio(aio_air_quality_level_format, combined_air_quality_level)  # Used by all aio packages
        if feed_resp:
            aio_resp = True
        previous_aio_air_quality_level = combined_air_quality_level
    if (aio_package == 'Premium' or aio_package == 'Basic Air') and combined_air_quality_text != previous_aio_air_quality_text: # Only update if it's changed
        print('Sending Air Quality Text Feed')
        feed_resp = send_data_to_aio(aio_air_quality_text_format, combined_air_quality_text)
        if feed_resp:
            aio_resp = True
        previous_aio_air_quality_text = combined_air_quality_text
    if enable_indoor_outdoor_functionality == False or enable_indoor_outdoor_functionality and indoor_outdoor_function == "Outdoor":
        # If indoor_outdoor_functionality is enabled, only send the forecast from the outdoor unit and only if it's been updated
        aio_forecast_text = forecast.replace("\n", " ")
        if aio_package == 'Premium' and aio_forecast_text != previous_aio_forecast_text:
            print('Sending Weather Forecast Text Feed')
            feed_resp = send_data_to_aio(aio_forecast_text_format, aio_forecast_text)
            if feed_resp:
                aio_resp = True
            previous_aio_forecast_text = aio_forecast_text
        if (aio_package == 'Premium' or aio_package == 'Basic Combo') and aio_forecast != previous_aio_forecast:
            print('Sending Weather Forecast Icon Feed')
            feed_resp = send_data_to_aio(aio_forecast_icon_format, aio_forecast)
            if feed_resp:
                aio_resp = True
            previous_aio_forecast = aio_forecast
    # Send other feeds
    for feed in aio_format: # aio_format varies, based on the relevant aio_package
        if aio_format[feed][1]: # Send the first value of the list if sending humidity or barometer data
            if (feed == "Hum" or
                feed == "Bar" and enable_indoor_outdoor_functionality == False or
                feed == "Bar" and enable_indoor_outdoor_functionality and indoor_outdoor_function == "Outdoor"):
                # If indoor_outdoor_functionality is enabled, only send outdoor barometer feed
                print('Sending', feed, 'Feed')
                feed_resp = send_data_to_aio(aio_format[feed][0], mqtt_values[feed][0])
                if feed_resp:
                    aio_resp = True
        else: # Send the value if sending data other than humidity or barometer
            if (feed != "Red" and feed != "Oxi" and feed != "NH3") or mqtt_values['Gas Calibrated']: # Only send gas data if the gas sensors are warm and calibrated
                print('Sending', feed, 'Feed')
                feed_resp = send_data_to_aio(aio_format[feed][0], mqtt_values[feed])
                if feed_resp:
                    aio_resp = True
    return previous_aio_air_quality_level, previous_aio_air_quality_text, previous_aio_forecast_text, previous_aio_forecast, aio_resp
     
# Compensation factors for temperature, humidity and air pressure
if enable_display: # Set temp and hum compensation when display is enabled (no weather protection cover in place)
    # Cubic polynomial temp comp coefficients adjusted by config's temp_offset
    comp_temp_cub_a = -0.0001
    comp_temp_cub_b = 0.0037
    comp_temp_cub_c = 1.00568
    comp_temp_cub_d = -6.78291
    comp_temp_cub_d = comp_temp_cub_d + temp_offset
    # Quadratic polynomial hum comp coefficients
    comp_hum_quad_a = -0.0032
    comp_hum_quad_b = 1.6931
    comp_hum_quad_c = 0.9391
else: # Set temp and hum compensation when display is disabled (weather protection cover in place)
    # Cubic polynomial temp comp coefficients adjusted by config's temp_offset
    comp_temp_cub_a = -0.00028
    comp_temp_cub_b = 0.01370
    comp_temp_cub_c = 1.07037
    comp_temp_cub_d = -12.35321
    comp_temp_cub_d = comp_temp_cub_d + temp_offset
    # Quadratic polynomial hum comp coefficients
    comp_hum_quad_a = -0.0098
    comp_hum_quad_b = 2.0705
    comp_hum_quad_c = -1.2795
# Gas Comp Factors: Change in Rs per raw temp degree C, raw percent humidity or hPa of raw air pressure relative to baselines
red_temp_comp_factor = -5522
red_hum_comp_factor = -3128
red_bar_comp_factor = -915
oxi_temp_comp_factor = -5144
oxi_hum_comp_factor = 1757
oxi_bar_comp_factor = -566
nh3_temp_comp_factor = -5000
nh3_hum_comp_factor = -1499
nh3_bar_comp_factor = -1000

# Display setup
delay = 0.5 # Debounce the proximity tap when choosing the data to be displayed
mode = 0 # The starting mode for the data display
last_page = 0
light = 1
# Width and height to calculate text position
WIDTH = disp.width
HEIGHT = disp.height

# The position of the top bar
top_pos = 25

# Set up canvas and fonts
img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
x_offset = 2
y_offset = 2
# Set up fonts
font_size_small = 10
font_size_sm = 12
font_size_smm = 14
font_size_medium = 16
font_size_ml = 18
font_size_large = 20
smallfont = ImageFont.truetype(UserFont, font_size_small)
font_sm = ImageFont.truetype(UserFont, font_size_sm)
font_smm = ImageFont.truetype(UserFont, font_size_smm)
mediumfont = ImageFont.truetype(UserFont, font_size_medium)
font_ml = ImageFont.truetype(UserFont, font_size_ml)
largefont = ImageFont.truetype(UserFont, font_size_large)
message = ""

# Set up icon display
# Set up air quality levels for icon display
icon_air_quality_levels = ['Great', 'OK', 'Alert', 'Poor', 'Bad']
# Values that alter the look of the background
blur = 5
opacity = 255
icon_background_hue = [240, 120, 60, 39, 0]
sun_radius = 20
# Margins
margin = 3

# Create own_data dict to store the data to be displayed in Display Everything
# Format: {Display Item: [Units, Current Value, [Level Thresholds], display_all_aq position]}
own_data = {"P1": ["ug/m3", 0, [6,17,27,35], 0], "P2.5": ["ug/m3", 0, [11,35,53,70], 1], "P10": ["ug/m3", 0, [16,50,75,100], 2],
            "Oxi": ["ppm", 0, [0.5, 1, 3, 5], 3], "Red": ["ppm", 0, [5, 30, 50, 75], 4], "NH3": ["ppm", 0, [5, 30, 50, 75], 5],
            "Temp": ["C", 0, [10,16,28,35], 6], "Hum": ["%", 0, [20,40,60,90], 7], "Bar": ["hPa", 0, [250,650,1013,1015], 8],
            "Lux": ["Lux", 1, [-1,-1,30000,100000], 9]}
data_in_display_all_aq =  ["P1", "P2.5", "P10", "Oxi", "Red", "NH3"]

# Defines the order in which display modes are chosen
display_modes = ["Icon Weather", "All Air", "P1", "P2.5", "P10", "Oxi", "Red", "NH3", "Forecast", "Temp", "Hum", "Bar", "Lux", "Status"]

# For graphing own display data
own_disp_values = {}
for v in own_data:
    own_disp_values[v] = [[1, 0]] * int(WIDTH/2)
                   
if enable_indoor_outdoor_functionality and indoor_outdoor_function == 'Indoor': # Prepare outdoor data, if it's required'             
    outdoor_data = {"P1": ["ug/m3", 0, [6,17,27,35], 0], "P2.5": ["ug/m3", 0, [11,35,53,70], 1], "P10": ["ug/m3", 0, [16,50,75,100], 2],
                    "Oxi": ["ppm", 0, [0.5, 1, 3, 5], 3], "Red": ["ppm", 0, [5, 30, 50, 75], 4], "NH3": ["ppm", 0, [10, 50, 100, 150], 5],
                    "Temp": ["C", 0, [10,16,28,35], 6], "Hum": ["%", 0, [20,40,60,80], 7], "Bar": ["hPa", 0, [250,650,1013,1015], 8],
                    "Lux": ["Lux", 1, [-1,-1,30000,100000], 9]}
    # For graphing outdoor display data
    outdoor_disp_values = {}
    for v in outdoor_data:
        outdoor_disp_values[v] = [[1, 0]] * int(WIDTH/2)
else:
    outdoor_data = {}
    outdoor_disp_values = []
# Used to define aqi components and their priority for the icon display.
air_quality_data = ["P1", "P2.5", "P10", "Oxi", "Red", "NH3"]
air_quality_data_no_gas = ["P1", "P2.5", "P10"]
current_display_is_own = True # Start with own display
start_current_display = time.time()
indoor_outdoor_display_duration = 5 # Seconds for duration of indoor or outdoor display
outdoor_reading_captured = False # Used to determine whether the outdoor display is ready
outdoor_reading_captured_time = 0 # Used to determine the last time that an mqtt message was received from the outdoor sensor

# Define your own threshold limits for Display Everything
# The limits definition follows the order of the variables array
# Example limits explanation for temperature:
# [4,18,28,35] means
# [-273.15 .. 4] -> Very Low
# (4 .. 18]   -> Low
# (18 .. 28]     -> Moderate
# (28 .. 35]     -> High
# (35 .. MAX]   -> Very High
# DISCLAIMER: The limits provided here are just examples and come
# with NO WARRANTY. The authors of this example code claim
# NO RESPONSIBILITY if reliance on the following values or this
# code in general leads to ANY DAMAGES or DEATH.

# RGB palette for values on the combined screen
palette = [(128,128,255),   # Very Low
           (0,255,0),       # Low
           (255,255,0),     # Moderate
           (255,165,0),     # High
           (255,0,0)]       # Very High
    
luft_values = {} # To be sent to Luftdaten
mqtt_values = {} # To be sent to Home Manager, outdoor to indoor unit communications and used for the Adafruit IO Feeds
data_sent_to_luftdaten_or_aio = False # Used to flag that the main loop delay is not required when data is sent to Luftdaten of Adafruit IO
maxi_temp = None
mini_temp = None


# Raspberry Pi ID to send to Luftdaten
id = "raspi-" + get_serial_number()

# Display Raspberry Pi serial and Wi-Fi status
logging.info("Raspberry Pi serial: {}".format(get_serial_number()))
logging.info("Wi-Fi: {}\n".format("connected" if check_wifi() else "disconnected"))

# Set up mqtt if required
if enable_send_data_to_homemanager or enable_receive_data_from_homemanager or enable_indoor_outdoor_functionality:
    es = ExternalSensors()
    client = mqtt.Client(mqtt_client_name)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(mqtt_broker_name, 1883, 60)
    client.loop_start()
  
if enable_adafruit_io:
    # Set up Adafruit IO. aio_format{'measurement':[feed, is value in list format?]}
    # Barometer and Weather Forecast Feeds only have one feed per household (i.e. no location prefix)
    # Three aio_packages: Basic Air (Air Quality Level, Air Quality Text, PM1,  PM2.5, PM10), Basic Combo (Air Quality Level, Weather Forecast Icon, Temp, Hum, Bar Feeds) and Premium (All Feeds)
    print('Setting up', aio_package, 'Adafruit IO')
    aio_url = "https://io.adafruit.com/api/v2/" + aio_user_name
    aio_feed_prefix = aio_household_prefix + '-' + aio_location_prefix
    aio_format = {}
    aio_forecast_text_format = None
    aio_forecast_icon_format = None
    aio_air_quality_level_format = None
    aio_air_quality_text_format = None
    previous_aio_air_quality_level = None
    previous_aio_air_quality_text = None
    previous_aio_forecast_text = None
    previous_aio_forecast = None
    if aio_package == "Premium":
        aio_format = {'Temp': [aio_feed_prefix + "-temperature", False], 'Hum': [aio_feed_prefix + "-humidity", True],
                      'Bar': [aio_household_prefix + "-barometer", True], 'Lux': [aio_feed_prefix + "-lux", False],
                      'P1': [aio_feed_prefix + "-pm1", False],'P2.5': [aio_feed_prefix + "-pm2-dot-5", False],
                      'P10': [aio_feed_prefix + "-pm10", False], 'Red': [aio_feed_prefix + "-reducing", False],
                      'Oxi': [aio_feed_prefix + "-oxidising", False], 'NH3': [aio_feed_prefix + "-ammonia", False]}
        aio_forecast_text_format = aio_household_prefix + "-weather-forecast-text"
        aio_forecast_icon_format = aio_household_prefix + "-weather-forecast-icon"
        aio_air_quality_level_format = aio_feed_prefix + "-air-quality-level"
        aio_air_quality_text_format = aio_feed_prefix + "-air-quality-text"
    elif aio_package == "Basic Air":
        aio_format = {'P1': [aio_feed_prefix + "-pm1", False],'P2.5': [aio_feed_prefix + "-pm2-dot-5", False],
                      'P10': [aio_feed_prefix + "-pm10", False]}
        aio_air_quality_level_format = aio_feed_prefix + "-air-quality-level"
        aio_air_quality_text_format = aio_feed_prefix + "-air-quality-text"
    elif aio_package == "Basic Combo":
        aio_format = {'Temp': [aio_feed_prefix + "-temperature", False], 'Hum': [aio_feed_prefix + "-humidity", True],
                      'Bar': [aio_household_prefix + "-barometer", True]}
        aio_forecast_icon_format = aio_household_prefix + "-weather-forecast-icon"
        aio_air_quality_level_format = aio_feed_prefix + "-air-quality-level"
    else:
        print('Invalid Adafruit IO Package')

# Set up comms error and failure flags
luft_resp = True # Set to False when there is a Luftdaten comms error
aio_resp = True # Set to False when there is an comms error on all Adafruit IO feeds
successful_comms_time = time.time()
comms_failure_tolerance = 3600 # Adjust this to set the comms failure duration before a reboot via the watchdog is triggered when both Luftdaten and Adafruit IO are enabled
comms_failure = False # Set to True when there has been a comms failure on both Luftdaten and Adafruit IO
    
# Take one reading from each climate and gas sensor on start up to stabilise readings
first_temperature_reading = bme280.get_temperature()
first_humidity_reading = bme280.get_humidity()
first_pressure_reading = bme280.get_pressure() * barometer_altitude_comp_factor(altitude, first_temperature_reading)
use_external_temp_hum = False
use_external_barometer = False
first_light_reading = ltr559.get_lux()
first_proximity_reading = ltr559.get_proximity()
raw_red_rs, raw_oxi_rs, raw_nh3_rs = read_raw_gas()

# Set up startup R0 with no compensation (Compensation will be set up after warm up time)
red_r0, oxi_r0, nh3_r0 = read_raw_gas()
# Set up daily gas sensor calibration lists
reds_r0 = []
oxis_r0 = []
nh3s_r0 = []
gas_calib_temps = []
gas_calib_hums = []
gas_calib_bars = []
print("Startup R0. Red R0:", round(red_r0, 0), "Oxi R0:", round(oxi_r0, 0), "NH3 R0:", round(nh3_r0, 0))
# Capture temp/hum/bar to define variables
gas_calib_temp = first_temperature_reading
gas_calib_hum = first_humidity_reading
gas_calib_bar = first_pressure_reading
gas_sensors_warm = False
outdoor_gas_sensors_warm = False # Only used for an indoor unit when indoor/outdoor functionality is enabled
mqtt_values["Gas Calibrated"] = False # Only set to true after the gas sensor warmup time has been completed
gas_sensors_warmup_time = 6000
gas_daily_r0_calibration_completed = False
# Set up weather forecast
first_climate_reading_done = False
barometer_history = [0.00 for x in range (9)]
barometer_change = 0
barometer_trend = ''
barometer_log_time = 0
valid_barometer_history = False
forecast = 'Insufficient Data'
icon_forecast = 'Wait'
domoticz_forecast = '0'
aio_forecast = 'question'

# Set up times
short_update_time = 0 # Set the short update time baseline (for watchdog alive file and Luftdaten updates)
short_update_delay = 150 # Time between short updates
previous_aio_update_minute = None # Used to record the last minute that the aio feeds were updated
long_update_time = 0 # Set the long update time baseline (for all other updates)
long_update_delay = 300 # Time between long updates
startup_stabilisation_time = 300 # Time to allow sensor stabilisation before sending external updates
start_time = time.time()
gas_daily_r0_calibration_hour = 3 # Adjust this to set the hour at which daily gas sensor calibrations are undertaken
barometer_available_time = start_time + 10945 # Initialise the time until a forecast is available (3 hours + the time taken before the first climate reading)
mqtt_values["Bar"] = [gas_calib_bar, domoticz_forecast]
domoticz_hum_map = {"good": "1", "dry": "2", "wet": "3"}
mqtt_values["Hum"] = [gas_calib_hum, domoticz_hum_map["good"]]
path = os.path.dirname(os.path.realpath(__file__))
# Check for a persistence data log and use it if it exists and was < 10 minutes ago
persistent_data_log = {}
    
try:
    with open('<Your Persistent Data Log File Name Here>', 'r') as f:
        persistent_data_log = json.loads(f.read())
except IOError:
    print('No Persistent Data Log Available. Using Defaults')
if "Update Time" in persistent_data_log and "Gas Calib Temp List" in persistent_data_log: # Check that the log has been updated and has a format > 3.87
    if (start_time - persistent_data_log["Update Time"]) < 1200: # Only update variables if the log was updated < 20 minutes before start-up
        long_update_time = persistent_data_log["Update Time"]
        short_update_time = long_update_time
        barometer_log_time = persistent_data_log["Barometer Log Time"]
        forecast = persistent_data_log["Forecast"]
        barometer_available_time = persistent_data_log["Barometer Available Time"]
        valid_barometer_history = persistent_data_log["Valid Barometer History"]
        barometer_history = persistent_data_log["Barometer History"]
        barometer_change = persistent_data_log["Barometer Change"]
        barometer_trend = persistent_data_log["Barometer Trend"]
        icon_forecast = persistent_data_log["Icon Forecast"]
        domoticz_forecast = persistent_data_log["Domoticz Forecast"]
        aio_forecast = persistent_data_log["AIO Forecast"]
        gas_sensors_warm = persistent_data_log["Gas Sensors Warm"]
        gas_calib_temp = persistent_data_log["Gas Temp"]
        gas_calib_hum = persistent_data_log["Gas Hum"]
        gas_calib_bar = persistent_data_log["Gas Bar"]
        gas_calib_temps = persistent_data_log["Gas Calib Temp List"]
        gas_calib_hums = persistent_data_log["Gas Calib Hum List"]
        gas_calib_bars = persistent_data_log["Gas Calib Bar List"]
        red_r0 = persistent_data_log["Red R0"]
        oxi_r0 = persistent_data_log["Oxi R0"]
        nh3_r0 = persistent_data_log["NH3 R0"]
        reds_r0 = persistent_data_log["Red R0 List"]
        oxis_r0 = persistent_data_log["Oxi R0 List"]
        nh3s_r0 = persistent_data_log["NH3 R0 List"]
        own_disp_values = persistent_data_log["Own Disp Values"]
        outdoor_disp_values = persistent_data_log["Outdoor Disp Values"]
        maxi_temp = persistent_data_log["Maxi Temp"]
        mini_temp = persistent_data_log["Mini Temp"]
        last_page = persistent_data_log["Last Page"]
        mode = persistent_data_log["Mode"]
        print('Persistent Data Log retrieved and used')
        print("Recovered R0. Red R0:", round(red_r0, 0), "Oxi R0:", round(oxi_r0, 0), "NH3 R0:", round(nh3_r0, 0))
    else:
        print('Persistent Data Log Too Old. Using Defaults')
mqtt_values["Forecast"] = {"Valid": valid_barometer_history, "3 Hour Change": round(barometer_change, 1), "Forecast": forecast}
                                 
# Main loop to read data, display, and send to Luftdaten, HomeManager and Adafruit IO
try:
    while True:       
        # Read air particle values on every loop
        luft_values, mqtt_values, own_data, own_disp_values = read_pm_values(luft_values, mqtt_values, own_data, own_disp_values)
        
        # Read climate values, provide external updates and write to watchdog file every 2.5 minutes (set by short_update_time).
        run_time = round((time.time() - start_time), 0)
        time_since_short_update = time.time() - short_update_time
        if time_since_short_update >= short_update_delay:
            short_update_time = time.time()
            (luft_values, mqtt_values, own_data, maxi_temp, mini_temp, own_disp_values, raw_red_rs, raw_oxi_rs, raw_nh3_rs,
             raw_temp, comp_temp, comp_hum, raw_hum, use_external_temp_hum,
             use_external_barometer, raw_barometer) = read_climate_gas_values(luft_values, mqtt_values, own_data,
                                                                              maxi_temp, mini_temp, own_disp_values,
                                                                              gas_sensors_warm,
                                                                              gas_calib_temp, gas_calib_hum, gas_calib_bar, altitude)
            first_climate_reading_done = True
            print('Luftdaten Values', luft_values)
            print('mqtt Values', mqtt_values)
            # Write to the watchdog file unless there is a comms failure for >= comms_failure_tolerance when both Luftdaten and Adafruit IO arenabled
            if comms_failure == False:
                with open('<Your Watchdog File Name Here>', 'w') as f:
                    f.write('Enviro Script Alive')
            if enable_luftdaten: # Send data to Luftdaten if enabled
                luft_resp = send_to_luftdaten(luft_values, id, enable_particle_sensor)
                #logging.info("Luftdaten Response: {}\n".format("ok" if luft_resp else "failed"))
                data_sent_to_luftdaten_or_aio = True
                if luft_resp:
                    print("Luftdaten update successful. Waiting for next capture cycle")
                else:
                    print("Luftdaten update unsuccessful. Waiting for next capture cycle")
            else:
                print('Waiting for next capture cycle')
                
        # Read and update the barometer log if the first climate reading has been done and the last update was >= 20 minutes ago
        if first_climate_reading_done and (time.time() - barometer_log_time) >= 1200:
            if barometer_log_time == 0: # If this is the first barometer log, record the time that a forecast will be available (3 hours)
                barometer_available_time = time.time() + 10800
            barometer_history, barometer_change, valid_barometer_history, barometer_log_time, forecast, barometer_trend, icon_forecast, domoticz_forecast, aio_forecast = log_barometer(own_data['Bar'][1], barometer_history)
            mqtt_values["Forecast"] = {"Valid": valid_barometer_history, "3 Hour Change": round(barometer_change, 1), "Forecast": forecast.replace("\n", " ")}
            mqtt_values["Bar"][1] = domoticz_forecast # Add Domoticz Weather Forecast
            print('Barometer Logged. Waiting for next capture cycle')

        # Update Display on every loop
        last_page, mode, start_current_display, current_display_is_own = display_results(start_current_display, current_display_is_own, display_modes,
                                                                                         indoor_outdoor_display_duration, own_data,
                                                                                         data_in_display_all_aq, outdoor_data,
                                                                                         outdoor_reading_captured, own_disp_values,
                                                                                         outdoor_disp_values, delay, last_page, mode,
                                                                                         luft_values, mqtt_values, WIDTH,
                                                                                         valid_barometer_history, forecast,
                                                                                         barometer_available_time, barometer_change,
                                                                                         barometer_trend, icon_forecast, maxi_temp,
                                                                                         mini_temp, air_quality_data, air_quality_data_no_gas,
                                                                                         gas_sensors_warm,
                                                                                         outdoor_gas_sensors_warm, enable_display, palette)

        # Provide external updates and update persistent data log
        if run_time > startup_stabilisation_time: # Wait until the gas sensors have stabilised before providing external updates or updating the persistent data log
            # Send data to Adafruit IO if enabled, set up and the time is now within the configured window and sequence
            if enable_adafruit_io and aio_format != {}:
                today=datetime.now()
                window_minute = int(today.strftime('%M'))
                window_second = int(today.strftime('%S'))
                if window_minute % 10 == aio_feed_window and window_second // 15 == aio_feed_sequence and window_minute != previous_aio_update_minute:
                    previous_aio_air_quality_level, previous_aio_air_quality_text, previous_aio_forecast_text, previous_aio_forecast, aio_resp = update_aio(mqtt_values, forecast, aio_format, aio_forecast_text_format,
                                                                                                                                                  aio_forecast_icon_format, aio_air_quality_level_format,
                                                                                                                                                  aio_air_quality_text_format, own_data, icon_air_quality_levels,
                                                                                                                                                  aio_forecast, aio_package, gas_sensors_warm, air_quality_data,
                                                                                                                                                  air_quality_data_no_gas, previous_aio_air_quality_level,
                                                                                                                                                  previous_aio_air_quality_text,previous_aio_forecast_text,
                                                                                                                                                  previous_aio_forecast)
                    data_sent_to_luftdaten_or_aio = True
                    previous_aio_update_minute = window_minute
                    if aio_resp:
                        print("At least one Adafruit IO feed successful. Waiting for next capture cycle")
                    else:
                        print("No Adafruit IO feeds successful. Waiting for next capture cycle")
            time_since_long_update = time.time() - long_update_time
            # Provide other external updates and update persistent data log every 5 minutes (Set by long_update_delay)
            if time_since_long_update >= long_update_delay:
                long_update_time = time.time()
                if (indoor_outdoor_function == 'Indoor' and enable_send_data_to_homemanager):
                    client.publish(indoor_mqtt_topic, json.dumps(mqtt_values))
                elif (indoor_outdoor_function == 'Outdoor' and (enable_indoor_outdoor_functionality or enable_send_data_to_homemanager)):
                    client.publish(outdoor_mqtt_topic, json.dumps(mqtt_values))
                else:
                    pass
                if enable_climate_and_gas_logging:
                    log_climate_and_gas(run_time, own_data, raw_red_rs, raw_oxi_rs, raw_nh3_rs, raw_temp, comp_temp, comp_hum, raw_hum,
                                        use_external_temp_hum, use_external_barometer, raw_barometer)
                # Write to the persistent data log
                persistent_data_log = {"Update Time": long_update_time, "Barometer Log Time": barometer_log_time, "Forecast": forecast, "Barometer Available Time": barometer_available_time,
                                       "Valid Barometer History": valid_barometer_history, "Barometer History": barometer_history, "Barometer Change": barometer_change,
                                       "Barometer Trend": barometer_trend, "Icon Forecast": icon_forecast, "Domoticz Forecast": domoticz_forecast,
                                       "AIO Forecast": aio_forecast, "Gas Sensors Warm": gas_sensors_warm, "Gas Temp": gas_calib_temp,
                                       "Gas Hum": gas_calib_hum, "Gas Bar": gas_calib_bar, "Red R0": red_r0, "Oxi R0": oxi_r0, "NH3 R0": nh3_r0,
                                       "Red R0 List": reds_r0, "Oxi R0 List": oxis_r0, "NH3 R0 List": nh3s_r0, "Gas Calib Temp List": gas_calib_temps,
                                       "Gas Calib Hum List": gas_calib_hums, "Gas Calib Bar List": gas_calib_bars, "Own Disp Values": own_disp_values,
                                       "Outdoor Disp Values": outdoor_disp_values, "Maxi Temp": maxi_temp, "Mini Temp": mini_temp, "Last Page": last_page, "Mode": mode}
                print('Logging Barometer, Forecast, Gas Calibration and Display Data')
                with open('<Your Persistent Data Log File Name Here>', 'w') as f:
                    f.write(json.dumps(persistent_data_log))
                if "Forecast" in mqtt_values:
                    mqtt_values.pop("Forecast") # Remove Forecast after sending it to home manager so that forecast data is only sent when updated
                print('Waiting for next capture cycle')
        # Luftdaten and Adafruit IO Communications Check
        if aio_resp or luft_resp: # Set time when a successful Luftdaten or Adafruit IO response is received, or if either Luftdaten or Adafruit IO is disabled
            successful_comms_time = time.time() 
        if time.time() - successful_comms_time >= comms_failure_tolerance:
            comms_failure = True
            print("Both Lufdaten and Adafruit IO communications have been lost for more than " + str(int(comms_failure_tolerance/60)) + " minutes. System will reboot via watchdog")
        # Outdoor Sensor Comms Check
        if time.time() - outdoor_reading_captured_time > long_update_delay * 2:
            outdoor_reading_captured = False # Reset outdoor reading captured flag if comms with the outdoor sensor is lost so that old outdoor data is not displayed
        # Calibrate gas sensors after warmup
        if ((time.time() - start_time) > gas_sensors_warmup_time) and gas_sensors_warm == False:
            gas_calib_temp = raw_temp
            gas_calib_hum = raw_hum
            gas_calib_bar = raw_barometer
            red_r0, oxi_r0, nh3_r0 = read_raw_gas()
            print("Gas Sensor Calibration after Warmup. Red R0:", red_r0, "Oxi R0:", oxi_r0, "NH3 R0:", nh3_r0)
            print("Gas Calibration Baseline. Temp:", round(gas_calib_temp, 1), "Hum:", round(gas_calib_hum, 0), "Barometer:", round(gas_calib_bar, 1))
            reds_r0 = [red_r0] * 7
            oxis_r0 = [oxi_r0] * 7
            nh3s_r0 = [nh3_r0] * 7
            gas_calib_temps = [gas_calib_temp] * 7
            gas_calib_hums = [gas_calib_hum] * 7
            gas_calib_bars = [gas_calib_bar] * 7
            gas_sensors_warm = True
            
        # Calibrate gas sensors daily at time set by gas_daily_r0_calibration_hour,
        # using average of daily readings over a week if not already done in the current day and if warmup calibration is completed
        # Compensates for gas sensor drift over time
        today=datetime.now()
        if int(today.strftime('%H')) == gas_daily_r0_calibration_hour and gas_daily_r0_calibration_completed == False and gas_sensors_warm and first_climate_reading_done:
            print("Daily Gas Sensor Calibration. Old R0s. Red R0:", red_r0, "Oxi R0:", oxi_r0, "NH3 R0:", nh3_r0)
            print("Old Calibration Baseline. Temp:", round(gas_calib_temp, 1), "Hum:", round(gas_calib_hum, 0), "Barometer:", round(gas_calib_bar, 1)) 
            # Set new calibration baseline using 7 day rolling average
            gas_calib_temps = gas_calib_temps[1:] + [raw_temp]
            #print("Calib Temps", gas_calib_temps)
            gas_calib_temp = round(sum(gas_calib_temps)/float(len(gas_calib_temps)), 1)
            gas_calib_hums = gas_calib_hums[1:] + [raw_hum]
            #print("Calib Hums", gas_calib_hums)
            gas_calib_hum = round(sum(gas_calib_hums)/float(len(gas_calib_hums)), 0)
            gas_calib_bars = gas_calib_bars[1:] + [raw_barometer]
            #print("Calib Bars", gas_calib_bars)
            gas_calib_bar = round(sum(gas_calib_bars)/float(len(gas_calib_bars)), 1)
            # Update R0s based on new calibration baseline
            spot_red_r0, spot_oxi_r0, spot_nh3_r0, raw_red_r0, raw_oxi_r0, raw_nh3_r0 = comp_gas(gas_calib_temp, gas_calib_hum, gas_calib_bar, raw_temp, raw_hum, raw_barometer)
            # Convert R0s to 7 day rolling average
            reds_r0 = reds_r0[1:] + [spot_red_r0]
            #print("Reds R0", reds_r0)
            red_r0 = round(sum(reds_r0)/float(len(reds_r0)), 0)
            oxis_r0 = oxis_r0[1:] + [spot_oxi_r0]
            ##print("Oxis R0", oxis_r0)
            oxi_r0 = round(sum(oxis_r0)/float(len(oxis_r0)), 0)
            nh3s_r0 = nh3s_r0[1:] + [spot_nh3_r0]
            #print("NH3s R0", nh3s_r0)
            nh3_r0 = round(sum(nh3s_r0)/float(len(nh3s_r0)), 0)
            print('New R0s with compensation. Red R0:', red_r0, 'Oxi R0:', oxi_r0, 'NH3 R0:', nh3_r0)
            print("New Calibration Baseline. Temp:", round(gas_calib_temp, 1), "Hum:", round(gas_calib_hum, 0), "Barometer:", round(gas_calib_bar, 1))
            gas_daily_r0_calibration_completed = True
        if int(today.strftime('%H')) == (gas_daily_r0_calibration_hour + 1) and gas_daily_r0_calibration_completed:
            gas_daily_r0_calibration_completed = False

        # Only add a delay in the loop if no Luftdaten or Adafruit IO data has been sent
        if data_sent_to_luftdaten_or_aio == False:
            time.sleep(0.5)
        else:
            data_sent_to_luftdaten_or_aio = False # Reset data_sent_to_luftdaten_or_aio flag until Luftdaten or Adafruit IO data has been sent again
            
except KeyboardInterrupt:
    if enable_send_data_to_homemanager or enable_receive_data_from_homemanager:
        client.loop_stop()
    print('Keyboard Interrupt')

# Acknowledgements
# Based on code from:
# https://github.com/pimoroni/enviroplus-python/blob/master/examples/all-in-one.py
# https://github.com/pimoroni/enviroplus-python/blob/master/examples/combined.py
# https://github.com/pimoroni/enviroplus-python/blob/master/examples/compensated-temperature.py
# https://github.com/pimoroni/enviroplus-python/blob/master/examples/luftdaten.py
# https://github.com/pimoroni/enviroplus-python/blob/enviro-non-plus/examples/weather-and-light.py
# Weather Forecast based on www.worldstormcentral.co/law_of_storms/secret_law_of_storms.html by R. J. Ellis
