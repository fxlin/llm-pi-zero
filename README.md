LLM on Pi Zero


### Run all commands below as root

sudo su

apt-get install python3-dev

python3 -m venv rootenv

source rootenv/bin/activate

### verify pip is good
````
which pip
# should point to rootenv/
````

### dependneices 

```
pip install spidev
pip install gpiozero
pip install lgpio
pip install psutil
pip install Pillow
pip install smbus
```

## wiringpi
For accessing GPIO of opi0. 

**CANNOT DO THIS** 

~~pip3 install wiringpi~~

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