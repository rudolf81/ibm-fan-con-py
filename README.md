# ibm-fan-con-py
A Python app that manages the fan speed for Lenovo laptops.


## Why does this exist?
For use in Linux.

This app was developed as an alternative to the ACPI(/BIOS?) fan speed control that runs by default in many Linux distros for Lenovo laptops.
The default fan speed control has been known to act up - with RPM chasing up-and-down - causing a lot of noise...

Or you may want to have more fine-grained control over the fan speed.

If you want an easy solution, [zcfan](https://github.com/cdown/zcfan) is a good option, however it has a limitation where you can't block/ignore certain temperature sensors in the system from affecting the overall fan speed. In some Lenovo systems, there are temp sensors like SSD / Wifi, which you may want to ignore / are not fully implemented and report a bogus value.

ibm-fan-con-py allows you to add specific temperature sensors onto the blocklist, as to not affect fan speed control.


## Features
* Temperature sensor blocklist
* Min and max temp settings for fan control
* Automatic fan speed control between min and max
* You still retain the watchdog timer of the ACPI fan control, so if this app crashes, automatic fan control will take over
* Hysteresis on fan speed reduction (controllable spin-down timing) to reduce noise


## Compatible laptops
Uurm - difficult to say...

If you are running Linux on a Lenovo, you can check if you have thinkpad_acpi kernerl module:
`sudo modinfo thinkpad_acpi`

This app has been tested on a Thinkpad T16, with a single fan, running thinkpad_acpi v0.26.

*It seems to work alright - except for an issue with the T16, where making changes to the fan speed over a long period results in a system crash... This issue occurs with both this app, and [zcfan](https://github.com/cdown/zcfan), so is likely an issue in thinkpad_acpi. I've not read about this issue in other models however.*


## Warning ⚠️
This software comes with no warranty, and you use it at your own risk.

Although many modern systems have thermal-throttling and thermal-shutdown protections - if you mess around with your fan speed - things might get too hot or even get damaged...


## Config
Get an idea of what temperature sensors are present in your system, by running the included utility script: `print-all-temp-sensors.sh`.
This will list the location, name and current value of each sensor.

You can use this information to configure the blocklist.

The configuration lives in `ibm-fan-con.conf`. Please see the comments in the file for how to configure ibm-fan-con-py.

The **default expected location** of the config file is: `/etc/ibm-fan-con.conf` - or you can specify the location via `--conf` command line param.

You can also set the log level via `log.level` in the config file.

Config is not hot-loaded - you need to restart the app to read config changes.


## How to run it
Make a copy of `ibm-fan-con.conf` to `/etc/ibm-fan-con.conf`.
Review config options and add any sensors to the blocklist.

Enable manual speed control, by running the following commands as **root**:
```
rmmod thinkpad_acpi
modprobe thinkpad_acpi fan_control=1
```

Then, run ibm-fan-con-py as **root**:
```
python3 ./ibm-fan-con.py
```
*This app requires root to be able to write settings to the fan controller.*

You require at least **Python 3.11**.


You can redirect the console output to a log file:
```
python3 ./ibm-fan-con.py --log=./my-fan-output.log 
```

You can change the location of the config file:
```
python3 ./ibm-fan-con.py --conf=./my-fan-config.conf
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Further reading
[https://unix.stackexchange.com/questions/677382/why-fan-gets-enabled-again-and-again-after-thinkfan-started-and-ended-once]

[https://www.kernel.org/doc/Documentation/admin-guide/laptops/thinkpad-acpi.rst]
