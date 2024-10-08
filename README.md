# car_tunes
Simple MP3 player for in-car music

## Packages

Raspbian packages required:
- `python3`
- `python3-pip`
- `vlc`
- `python3-rpi.gpio`

Python packages with `pip3 install ...`:
- `python-vlc`

## Setup

Auto-running on start-up is achieved by adding the following to `~/.bashrc`:
```
sudo mount -o ro /dev/sda1 /mnt
if [ -f /mnt/car_tunes.py ]; then
    echo "Updating..."
    rm -f ~/car_tunes.old.py
    if [ -f ~/car_tunes.py ]; then
        mv ~/car_tunes.py ~/car_tunes.old.py
    fi
    cp /mnt/car_tunes.py ~/car_tunes.py
    echo "Updated."
    sleep 1s
fi
python3 ~/car_tunes.py /mnt ~/status
```

Auto-login on startup is configured through `sudo raspi-config`:
- Boot Options
- Desktop/CLI
- Console Autologin

Include scripts for controlling backlight:
- `/usr/local/bin/backlight_on.sh`:
```
sudo -E sh -c 'echo 0 > /sys/class/backlight/rpi_backlight/bl_power'
```

- `/usr/local/bin/backlight_off.sh`:
```
sudo -E sh -c 'echo 1 > /sys/class/backlight/rpi_backlight/bl_power'
```