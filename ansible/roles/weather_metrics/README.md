## Deploying raspberrypi-dht22 with Ansible

# Requires variables
- dht22_data_port: GPIO data pin to read sensor
- dht22_powerctl_port (Optional): GPIO data pin for power control
- thingspeak_dht22_api_key (Optional): ThingSpeak API key


Example host_vars
-----------------

```yml
is_weather_station: True
dht22_data_port: 17
dht22_powerctl_port: 27
  
```

Example Playbook
----------------

```yml
- hosts: pi
  roles:
   - { role: weather_metrics, tags: weather_metrics }
  when: is_weather_station is defined and is_weather_station
```

