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
sudo mount /dev/sda1 /mnt
python3 ~/car_tunes.py /mnt ~/tmp
```

Auto-login on startup is configured through `sudo raspi-config`:
- Boot Options
- Desktop/CLI
- Console Autologin

