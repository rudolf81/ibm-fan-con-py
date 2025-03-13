#!/usr/bin/python3

import argparse
import configparser
import datetime
import logging
import os
import time


DEFAULT_LOG_LEVEL = logging.DEBUG

FAN_MIN_TEMP_DEFAULT = 45
FAN_MIN_TEMP_LOWER_LIMIT = 1
FAN_MIN_TEMP_UPPER_LIMIT = 70

FAN_MAX_TEMP_DEFAULT = 70
FAN_MAX_TEMP_LOWER_LIMIT = 1
FAN_MAX_TEMP_UPPER_LIMIT = 75

WATCHDOG_TIMER_SECONDS_DEFAULT = 15
WATCHDOG_TIMER_SECONDS_LOWER_LIMIT = 5
WATCHDOG_TIMER_SECONDS_UPPER_LIMIT = 120

HYSTERESIS_SECONDS_DEFAULT = 10
HYSTERESIS_SECONDS_LOWER_LIMIT = 0
HYSTERESIS_SECONDS_UPPER_LIMIT = 60

BASE_HWMON_PATH = '/sys/class/hwmon/'


log_level = DEFAULT_LOG_LEVEL

fan_min_temp = FAN_MIN_TEMP_DEFAULT
fan_max_temp = FAN_MAX_TEMP_DEFAULT
watchdog_timer_seconds = WATCHDOG_TIMER_SECONDS_DEFAULT
hysteresis_seconds = HYSTERESIS_SECONDS_DEFAULT

blocklist = []
sensor_paths = []
bracket_temp_increment = 1
bracket_temps = [None] * 9
last_level_change = 0
current_level = 0


def read_args():
    parser = argparse.ArgumentParser(description='IBM Fan Controller - Python')
    parser.add_argument('--conf', type=str, default='/etc/ibm-fan-con.conf', help='Path to the configuration file')
    parser.add_argument('--log', type=str, help='Path to the log file (optional)')
    args = parser.parse_args()
    
    return args


def setup_logging(log_path=None):
    logging.basicConfig(level=log_level, filename=log_path, filemode='a', format='%(asctime)s - %(levelname)s - %(message)s')


def read_config(config_path):
    global fan_min_temp
    global fan_max_temp
    global watchdog_timer_seconds
    global hysteresis_seconds
    global blocklist
    global log_level
    
    config = configparser.ConfigParser()

    if os.path.exists(config_path):
        logging.info(f'Configuration file found at {config_path}')

        config.read(config_path)

        log_level_int = logging.DEBUG
        
        for section in config.sections():
            if section.startswith('blocklist-'):
                hwmon_name = config.get(section, 'hwmon.name', fallback=None)
                temp_label = config.get(section, 'temp.label', fallback=None)
                
                if hwmon_name and temp_label:
                    logging.info(f'Adding blocklist entry {hwmon_name}:{temp_label}')
                    blocklist.append({'hwmon_name': hwmon_name, 'temp_label': temp_label})
                else:
                    logging.warning(f'Skipping incomplete blocklist entry in section {section}')

            if section.startswith('temp-settings'):
                fan_min_cfg = int(config.get(section, 'fan.min.temp', fallback=FAN_MIN_TEMP_DEFAULT))
                if fan_min_cfg < FAN_MIN_TEMP_LOWER_LIMIT or fan_min_cfg > FAN_MIN_TEMP_UPPER_LIMIT:
                    logging.error(f'Illegal fan.min.temp value set in config file. fan.min.temp reverting to default: {FAN_MIN_TEMP_DEFAULT}')
                    fan_min_cfg = FAN_MIN_TEMP_DEFAULT
                fan_min_temp = fan_min_cfg

                fan_max_cfg = int(config.get(section, 'fan.max.temp', fallback=FAN_MAX_TEMP_DEFAULT))
                if fan_max_cfg < FAN_MAX_TEMP_LOWER_LIMIT or fan_max_cfg > FAN_MAX_TEMP_UPPER_LIMIT:
                    logging.error(f'Illegal fan.max.temp value set in config file. fan.max.temp reverting to default: {FAN_MAX_TEMP_DEFAULT}')
                    fan_max_cfg = FAN_MAX_TEMP_DEFAULT
                fan_max_temp = fan_max_cfg

            if section.startswith('control-settings'):
                watchdog_timer_cfg = int(config.get(section, 'watchdog.timer.seconds', fallback=WATCHDOG_TIMER_SECONDS_DEFAULT))
                if watchdog_timer_cfg < WATCHDOG_TIMER_SECONDS_LOWER_LIMIT or watchdog_timer_cfg > WATCHDOG_TIMER_SECONDS_UPPER_LIMIT:
                    logging.error(f'Illegal watchdog.timer.seconds value set in config file. watchdog.timer.seconds reverting to default: {WATCHDOG_TIMER_SECONDS_DEFAULT}')
                    watchdog_timer_cfg = WATCHDOG_TIMER_SECONDS_DEFAULT
                watchdog_timer_seconds = watchdog_timer_cfg

                hysteresis_seconds_cfg = int(config.get(section, 'spin.down.hysteresis.seconds', fallback=HYSTERESIS_SECONDS_DEFAULT))
                if hysteresis_seconds_cfg < HYSTERESIS_SECONDS_LOWER_LIMIT or hysteresis_seconds_cfg > HYSTERESIS_SECONDS_UPPER_LIMIT:
                    logging.error(f'Illegal spin.down.hysteresis.seconds value set in config file. spin.down.hysteresis.seconds reverting to default: {HYSTERESIS_SECONDS_DEFAULT}')
                    hysteresis_seconds_cfg = HYSTERESIS_SECONDS_DEFAULT
                hysteresis_seconds = hysteresis_seconds_cfg

            if section.startswith('log-settings'):
                log_level_cfg = config.get(section, 'log.level', fallback='DEBUG')

                log_level_int = logging.getLevelName(log_level_cfg)
                
                if isinstance(log_level_int, int):
                    pass
                else:
                    log_level_int = logging.DEBUG
                    logging.error(f'Illegal log.level value set in config file. log.level reverting to default: {logging.getLevelName(DEFAULT_LOG_LEVEL)}')

        if fan_min_temp >= fan_max_temp:
            logging.error(f'Illegal fan.min.temp / fan.max.temp values set in config file. fan.min.temp reverting to default: {FAN_MIN_TEMP_DEFAULT}, fan.max.temp reverting to default: {FAN_MAX_TEMP_DEFAULT}')
            fan_min_temp = FAN_MIN_TEMP_DEFAULT
            fan_max_temp = FAN_MAX_TEMP_DEFAULT

        log_level = log_level_int
        logging.info(f'Logging level updated to: {logging.getLevelName(log_level)}')
        logging.getLogger().setLevel(log_level)

    else:
        logging.warn(f'No config file found at {config_path} - will use default values')


def print_final_config():
    logging.info('Final Config:')
    logging.info(f'\tfan.min.temp: {fan_min_temp}')
    logging.info(f'\tfan.max.temp: {fan_max_temp}')
    logging.info(f'\twatchdog.timer.seconds: {watchdog_timer_seconds}')
    logging.info(f'\tspin.down.hysteresis.seconds: {hysteresis_seconds}')


def is_blocklisted(hwmon_name, temp_label):
    for entry in blocklist:
        if entry['hwmon_name'] == hwmon_name and entry['temp_label'] == temp_label:
            return True
        
    return False


def get_temp(sensor_path):
    with open(sensor_path, 'r') as sensor_file:
        sensor_value = sensor_file.read().strip()

        return int(sensor_value) / 1000


def format_temp_rounded1(deg_c):
    rounded_deg_c = round(deg_c, 1)

    return f'{rounded_deg_c}°C'


def format_temp(deg_c):
    return f'{deg_c}°C'


def format_temp_rounded3(deg_c):
    rounded_deg_c = round(deg_c, 3)

    return f'{rounded_deg_c}°C'


def get_valid_sensor_list():
    global sensor_paths

    logging.info(f'Scanning for devices & sensors in {BASE_HWMON_PATH}:')

    for hwmon in sorted(os.listdir(BASE_HWMON_PATH)):
        hwmon_dir = os.path.join(BASE_HWMON_PATH, hwmon)

        hwmon_name = None
        try:
            with open(os.path.join(hwmon_dir, 'name'), 'r') as name_file:
                hwmon_name = name_file.read().strip()
        except IOError as ioe:
            hwmon_name = hwmon
            
        logging.info(f'\t{hwmon}\t{hwmon_name}:')

        try:
            for hwmon_file_name in sorted(os.listdir(hwmon_dir)):
                if hwmon_file_name.startswith('temp') and hwmon_file_name.endswith('_input'):
                    temp_input_file_path = os.path.join(hwmon_dir, hwmon_file_name)
                    temp_label_file_name = hwmon_file_name.replace('_input', '_label')
                    temp_label_file_path = os.path.join(hwmon_dir, temp_label_file_name)
                    
                    if os.path.exists(temp_label_file_path):
                        try:
                            with open(temp_label_file_path, 'r') as temp_label_file:
                                temp_label = temp_label_file.read().strip()
                                
                                if is_blocklisted(hwmon_name, temp_label):
                                    logging.info(f'\t\t\t{temp_label.ljust(8)}\t{hwmon_file_name}\t{format_temp_rounded1(get_temp(temp_input_file_path))}\t[X] Blocked!')
                                else:
                                    logging.info(f'\t\t\t{temp_label.ljust(8)}\t{hwmon_file_name}\t{format_temp_rounded1(get_temp(temp_input_file_path))}\t[✓]')
                                    sensor_paths.append(temp_input_file_path)
                        
                        except IOError as ioe:
                            #Error reading temp label
                            try:
                                logging.info(f'\t\t\t(no-label)\t{hwmon_file_name}\t{format_temp_rounded1(get_temp(temp_input_file_path))}\t[✓] Can\'t read label')
                                sensor_paths.append(temp_input_file_path)
                            except IOError as ioe:
                                logging.info(f'\t\t\t(no-label)\t{hwmon_file_name}\t------\t[X] Can\'t read sensor')
                    
                    else:
                        #There is no impl to block a non-labeled sensor yet...
                        try:
                            logging.info(f'\t\t\t(no-label)\t{hwmon_file_name}\t{format_temp_rounded1(get_temp(temp_input_file_path))}\t[✓] Unlabelled')
                            sensor_paths.append(temp_input_file_path)
                        except IOError as ioe:
                            logging.info(f'\t\t\t(no-label)\t{hwmon_file_name}\t------\t[X] Can\'t read sensor')

        except IOError as ioe:
            logging.error(f'Error reading hwmon device at {hwmon_dir}: {ioe}')


def print_final_sensor_list():
    logging.info(f'Final Sensors ({len(sensor_paths)}):')
    for sensor in sensor_paths:
        logging.info(sensor)


def get_highest_sensor_temp():
    max_temp = 0
    for sensor in sensor_paths:
        sensor_temp = get_temp(sensor)
        if sensor_temp > max_temp:
            max_temp = sensor_temp
    
    return max_temp


def print_current_highest_temp():
    logging.info(f'Current highest sensor temp: {format_temp_rounded3(get_highest_sensor_temp())}')


def set_watchdog_interval(interval_seconds):
    logging.info(f'Setting watchdog interval to: {interval_seconds}')

    try:
        with open('/proc/acpi/ibm/fan', 'w') as fan:
            fan.write(f'watchdog {interval_seconds}')
        #pass
    except IOError as ioe:
        logging.error(f'Error setting watchdog interval: {ioe}')
        raise RuntimeError('Failure to write watchdog value to /proc/acpi/ibm/fan')


def set_fan_level(level):
    global current_level

    written_level = level

    if level == 'auto':
        written_level = 'auto'
        level = 0
    elif level == 8:
        written_level = 'disengaged'
    
    logging.info(f'Setting fan level to: {written_level}')

    try:
        with open('/proc/acpi/ibm/fan', 'w') as fan:
            fan.write(f'level {written_level}')

        current_level = level
    except IOError as ioe:
        logging.error(f'Error setting fan level: {ioe}')
        raise RuntimeError('Failure to write level value to /proc/acpi/ibm/fan')


def compute_brackets():
    global bracket_temp_increment
    global bracket_temps

    temp_range = fan_max_temp - fan_min_temp
    number_of_brackets = 7
    bracket_temp_increment = temp_range / number_of_brackets

    bracket_temps[0] = float('-inf')
    bracket_temps[1] = fan_min_temp
    bracket_temps[2] = bracket_temps[1] + bracket_temp_increment
    bracket_temps[3] = bracket_temps[2] + bracket_temp_increment
    bracket_temps[4] = bracket_temps[3] + bracket_temp_increment
    bracket_temps[5] = bracket_temps[4] + bracket_temp_increment
    bracket_temps[6] = bracket_temps[5] + bracket_temp_increment
    bracket_temps[7] = bracket_temps[6] + bracket_temp_increment
    bracket_temps[8] = fan_max_temp


def print_brackets():
    logging.info(f'Temp & Level Brackets:')
    logging.info(f'\tTemp range per bracket: {format_temp_rounded3(bracket_temp_increment)}')

    for i in range(8):
        logging.info(f'\tLevel {i}:\t{format_temp_rounded3(bracket_temps[i])}')

    logging.info(f'\tLevel \'max\':\t{format_temp_rounded3(bracket_temps[8])}')


def timestamp():
    current_time = datetime.datetime.now()
    
    return current_time.timestamp()


def get_target_level(current_temp):
    target_level = 0

    for i in range(8, -1, -1):
        if current_temp >= bracket_temps[i]:
            target_level = i
            break

    return target_level


def main_control_loop():
    global last_level_change
    global current_level

    last_level_change = 0
    current_level = 0
    current_highest_temp = get_highest_sensor_temp()

    while True:
        current_highest_temp = get_highest_sensor_temp()

        target_level = get_target_level(current_highest_temp)

        now = timestamp()

        logging.debug(f'Current highest temp: {format_temp(current_highest_temp).ljust(8)}\tCurrent level: {current_level}\tTarget level: {target_level}')

        if target_level > current_level:
            set_fan_level(target_level)
            last_level_change = now
        elif target_level < current_level and (now - last_level_change) >= hysteresis_seconds:
            set_fan_level(current_level - 1) #Step down 1 level
            last_level_change = now
        elif (now - last_level_change) >= (watchdog_timer_seconds - 3):
            logging.debug(f'Re-applying watchdog timeout to reset timer')
            #set_fan_level(current_level) #Prevent watchdog taking over
            set_watchdog_interval(watchdog_timer_seconds)
            last_level_change = now

        time.sleep(1)


def is_acpi_has_fan_control_enabled():
    try:
        with open('/proc/acpi/ibm/fan', 'r') as fan:
            content = fan.readlines()
            # Check for the presence of specific commands in the content
            for line in content:
                if 'watchdog' in line or 'level <level>' in line:
                    return True

            return False
    except IOError as ioe:
        logging.error(f'Error reading /proc/acpi/ibm/fan: {ioe}')
        raise RuntimeError('Failure to read /proc/acpi/ibm/fan')


def main():
    args = read_args()

    setup_logging(args.log)

    logging.info(f'IBM Fan Con Started...')

    if not is_acpi_has_fan_control_enabled():
        logging.error("Advanced ACPI fan control is not enabled! You need to run as root: \'rmmod thinkpad_acpi && modprobe thinkpad_acpi fan_control=1' to enable it first.")
        quit()
    else:
        logging.info("Advanced ACPI fan control is enabled")
    
    read_config(args.conf)

    print_final_config()

    get_valid_sensor_list()

    print_final_sensor_list()

    print_current_highest_temp()

    compute_brackets()

    print_brackets()

    set_watchdog_interval(watchdog_timer_seconds)

    try:
        main_control_loop()
    except KeyboardInterrupt:
        logging.info('Reverting back to auto control mode')
        set_watchdog_interval(watchdog_timer_seconds)
        set_fan_level('auto')
    except Exception as e:
        logging.error(f'Error in main_control_loop!: {e}')
        logging.error('Emergency reverting back to auto control mode!')
        set_fan_level('auto')


if __name__ == '__main__':
    main()
