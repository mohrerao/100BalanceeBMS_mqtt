Installation instruction for ESP32 dev board
1. Flash esp32 with firmware. You can refer to https://docs.micropython.org/en/latest/esp32/tutorial/intro.html for flashing the firmware
2. Enable wifi and configure your wifi ssid and password. Refer https://docs.micropython.org/en/latest/esp32/quickref.html#networking for configuring wifi.
3. Update your mqtt host address and password
4. now copy main.py to your esp32. You can use thonny as it is easy to install, configure and update files on esp32. 
4. Connect 100BalanceBMS to your esp32 using a RS485 to TTL Serial Port Converter Adapter Communication Module. 
5. Now you should be able to create sensors for the topics published. 