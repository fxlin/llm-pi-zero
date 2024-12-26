## LLM on Pi Zero

This project is a simple ePaper UI for rendering LLM inference results on a Pi Zero. 
The UI is designed to be simple and low power, with a focus on readability and minimalism. The UI is designed to be used with the [RWKV](https://pypi.org/project/rwkv/) library, but can be easily adapted to other LLM inference libraries.

![image](https://github.com/user-attachments/assets/256335ae-d119-4793-bdc9-f9fd652511e2)

https://raw.githubusercontent.com/fxlin/llm-pi-zero/main/rwkv-demo-powermeter.mp4

https://github.com/user-attachments/assets/98b9d58a-7660-4d4d-97ee-e885c9d1ae21

## Hardware

- Orange Pi Zero 2W (4GB) - $35 [Amazon](https://www.amazon.com/gp/product/B0CHM7HN8P/ref=ppx_yo_dt_b_asin_title_o00_s00?ie=UTF8&th=1)
- Waveshare 2.13inch Touch e-Paper Display - $27 [Amazon](https://www.amazon.com/dp/B0BZDVZ7NR?ref=ppx_yo2ov_dt_b_fed_asin_title&th=1)
  - 2in13_V4, 250x122
  - https://www.waveshare.com/wiki/2.13inch_Touch_e-Paper_HAT_Manual

Whole system ~= 2.5 Watt when busy, ~= 1 Watt when idle (can be optimized)

**Total:** ~$65

While the ePaper is not specifically designed for the Orange Pi, it has good pin compatibility with the Raspberry Pi Zero 2W. Most changes involve adjusting the SPI (for display) and I2C (for touch) bus numbers. Refer to `epdconfig_ori.py` for details.

### Optional

- Orange Pi Zero 2W Extension Board - $15 [Amazon](https://www.amazon.com/gp/product/B0CHMTT4XP/ref=ppx_yo_dt_b_asin_title_o00_s00?ie=UTF8&th=1) - For ease of development
- USB Power Tester - $20 [Amazon](https://www.amazon.com/dp/B07JYVPLLJ?ref=ppx_yo2ov_dt_b_fed_asin_title)

### Also tested 

- **Raspberry Pi 5**

### TODO

- **Raspberry Pi Zero 2W** - Should work, but untested


## Software

### SD card prep
Grab a blank SD card (I used 32GB). 
Before flash the image, manually create one partitions on the card, with size (total_size - 128 MB). 
The idea is tht we will create a small FAT partition later for configuration/logs/prompts, etc. 

### Flash OS 

OS image: Orangepizero2w_1.0.2_ubuntu_jammy_server_linux6.1.31

Flash the OS image to the first partition. Try boot and login. If evereything works OK, create the 2nd partition with FAT32, label "fat"; mount it under /mnt/fat, e.g. 

```
/dev/mmcblk0p2  /mnt/fat  auto  defaults  0  0
```

Use orangepi-config or raspi-config to enable SPI and I2C accesses.
Cf the opi user manual. 

Here is my selection that works:
![image](https://github.com/user-attachments/assets/d1af70e9-b3d0-4be5-a19a-c1bf87d3800c)

(if the program launches then quits, it could be b/c of that it failed to open the touch device on i2c. so check the selection)

Check if touch interface can be detected (I2C addr: 0x14)
```
root@orangepizero2w: i2cdetect -y 3
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- 14 -- -- -- -- -- -- -- -- -- -- --
```

**A bug?**: Pi Sugar 3 (which also connects to the same I2C pins, addr 0x57, 0x68) can interfere with the touch screen's I2C communication. 
In this case, gt.GT_Init() will fail and throw IOError. Without examing what was wrong with Pi Sugar 3, simply masking Pi Sugar's I2C pins (using plastic tape) fixed the problem.😂

### Run All Commands Below as Root

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

## install wiringpi (with opi customizations)
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

### check wiringpi
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
will send a hardcoded message to the UI for rendering.


### test the UI with LLM

#### RWKV
```
pip install torch
# https://pypi.org/project/rwkv/
pip install rwkv
```

Download a model from Hugging Face(https://huggingface.co/BlinkDL) like this one (https://huggingface.co/BlinkDL/rwkv-4-pile-169m/blob/main/RWKV-4-Pile-169M-20220807-8023.pth).

My model paths are /data/models/pi-deployment/ 

## Finish up

Enable the service to start on boot
```
cp launch.sh /boot/
# so that it can be easily modified from PC/Mac

cp pi-demo.service /etc/systemd/system/
systemctl enable pi-demo
# launch it right now
systemctl start pi-demo.service
```

To save memory, disable the desktop
```
systemctl disable lightdm.service
```

### To load 1.5B model or larger
During model load (fp16), the amount of memory needed (~5GB) will far exceed the "steady stage" memory during inference (~2.2GB), so the device with 4GB of DRAM will OOM. 
opi zero + Ubunut 22 by default has zram swap on (using memory comperssion for swapping), which exacerbates this situation. 

While some pytorch tricks may be played to aggressively GC memory during model loading (TBD), 
we can use disk swap in lieu of zram, which allows model to load (slow, but will eventually load):

```
# execute as root

fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
# Make It Permanent
echo '/swapfile swap swap defaults 0 0' | tee -a /etc/fstab

swapoff /dev/zram0
systemctl stop zram-config
systemctl disable zram-config

# check
swapon --show
```
At the end, 1.5B model can run at 0.7 token/sec. No fast but better than OOM. 

11/16/24: i8 wouldn't need this trick, but is 3x slower than fp16 (even with NEON fp32i8); so I consider it less preferred. 


