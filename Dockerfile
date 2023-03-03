FROM python:3.9-bullseye

RUN apt-get update \
 && apt-get install -y \
    vlc

RUN pip install \
      fake_rpi \
      python-vlc \
      sshkeyboard

COPY sample-tunes /app/tunes
COPY src /app/src

CMD python3 /app/src/car_tunes.py /app/tunes /app/status
