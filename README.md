## ePaper UI for rendering LLM inference on Pi Zero 

https://github.com/user-attachments/assets/98b9d58a-7660-4d4d-97ee-e885c9d1ae21

## Hardware

- [x] Orange Pi Zero 2W (4GB), $35 [Amazon](https://www.amazon.com/gp/product/B0CHM7HN8P/ref=ppx_yo_dt_b_asin_title_o00_s00?ie=UTF8&th=1)
- [x] Waveshare 2.13inch Touch e-Paper Display $27 [Amazon](https://www.amazon.com/dp/B0BZDVZ7NR?ref=ppx_yo2ov_dt_b_fed_asin_title&th=1), 
Total: ~$65

Optional:
- [x] Orange Pi Zero 2W extension board, $15. for ease of developent [Amazon](https://www.amazon.com/gp/product/B0CHMTT4XP/ref=ppx_yo_dt_b_asin_title_o00_s00?ie=UTF8&th=1)
- [x] USB power tester. $20 [Amazon](https://www.amazon.com/dp/B07JYVPLLJ?ref=ppx_yo2ov_dt_b_fed_asin_title)

Planned:
- [ ] Raspberry Pi Zero 2W (should work, untested)

### Run all commands below as root

```
sudo su
```

reason: wiringpi (see below) requires root to work
(tried non root, tedious. not worth the effort)

### Initialization python virtual env

```
apt-get install python3-dev
python3 -m venv rootenv
source rootenv/bin/activate
```

### verify pip is good
````
which pip
# should point to rootenv/
````

## install wiringpi
For accessing GPIO of opi0. 

**CANNOT DO THIS** ~~pip3 install wiringpi~~

must build from source, which is much newer (4.0.2)

cf "3.21. How to install and use wiringOP-Python" manual pp 166, briefly

```
apt-get -y install git swig python3-dev python3-setuptools

git clone --recursive https://github.com/orangepi-xunlong/wiringOP-Python -b next
cd wiringOP-Python
git submodule update --init --remote
python3 generate-bindings.py > bindings.i
python3 setup.py install
```

### check
```
python3 -c "import wiringpi; help(wiringpi)"
#should show version 4.0.2
```

```
python3 -c "import wiringpi; \
from wiringpi import GPIO; wiringpi.wiringPiSetup() ; \
wiringpi.pinMode(2, GPIO.OUTPUT) ; "
# shouldn't see any errors, e.g. complain about gpio access right 
```

### install other dependneices 
```
pip install spidev
pip install gpiozero
pip install lgpio
pip install psutil
pip install Pillow
pip install smbus
```

### install the epaper lib (dev mode)

```
cd llm-epaper-demo
```

```
pip install -e Touch_e-Paper_Code/python
```

### test the UI without any LLM

```
EMU=1 python3 pi-demo.py
```
will send a hardcoded message to 
