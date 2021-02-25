## Logwatch configuration for raspberrypi-dht22 with Ansible

This role installs [Logwatch](https://sourceforge.net/projects/logwatch/) and uploads the service configuration and script files.<br/>
It will not modify ```/etc/logwatch/conf/logwatch.conf``` or any other part of an existing Logwatch setup.<br/>
Logwatch by default runs all services so this report should be included in the output as well.<br/>

Example host_vars
-----------------

```yml
weather_metrics_logwatch: True
```

Example Playbook
----------------

```yml
- hosts: pi
  roles:
    - { role: weather_metrics_logwatch,
        when: weather_metrics_logwatch is defined and weather_metrics_logwatch}
```

