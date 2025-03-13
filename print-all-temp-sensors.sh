#!/bin/bash

for hwmon_dir in /sys/class/hwmon/hwmon?/; do
    echo "Directory: $hwmon_dir"
    if [ -f "${hwmon_dir}name" ]; then
        echo "Name: $(cat ${hwmon_dir}name)"
    fi
    for temp_input in ${hwmon_dir}temp?_input; do
        if [ -f "$temp_input" ]; then
            temp_label="${temp_input%_input}_label"
            echo -n "  $(basename $temp_input): $(cat $temp_input)"
            if [ -f "$temp_label" ]; then
                label_content=$(cat $temp_label)
                echo -n " (${label_content})"
            fi
            echo
        fi
    done
    echo 
done