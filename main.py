from machine import UART, Pin
import time
import ustruct
import ubinascii
import json
from umqtt.simple import MQTTClient

# MQTT Configuration
MQTT_BROKER = "192.168.31.37"
MQTT_USER = "test"
MQTT_PASSWORD = "pass"
MQTT_CLIENT_ID = "ESP32_Modbus_Client"
MQTT_TOPIC_BASE = "100BalanceBMS/"
client = 0

# UART Configuration for Modbus
UART_PORT = 2  # UART2
TX_PIN = 17
RX_PIN = 16
BAUDRATE = 9600
client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, user = MQTT_USER, password = MQTT_PASSWORD)
# Initialize UART
uart = UART(UART_PORT, baudrate=BAUDRATE, tx=Pin(TX_PIN), rx=Pin(RX_PIN), stop=1, parity=None, timeout=100)

# MQTT Connect function
def connect_mqtt():
    try:
        client.connect()
    except Exception as e:
        print(f"Failed to connect to  MQTT broker: {e}")
        
# MQTT Publish Function        
def publish_mqtt(topic, message):
    try:
        client.publish(topic, str(message))
    except Exception as e:
        print(f"Failed to publish MQTT message: {e}")

# MQTT disconnect function
def disconnect_mqtt():
    try:
        client.disconnect()
    except Exception as e:
        print(f"Failed to disconnect to  MQTT broker: {e}")


# Calculate CRC for Modbus Command
def compute_crc(data):
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

# Send Modbus Command and Get Response
def send_modbus_command(command):
    try:
        crc = compute_crc(command)
        crc_bytes = ustruct.pack('<H', crc)
        full_command = command + crc_bytes
        uart.write(full_command)
        print(f"Sent: {ubinascii.hexlify(full_command).decode()}")
        time.sleep(0.1)
        response = uart.read()
        if response:
            print(f"Received: {ubinascii.hexlify(response).decode()}")
            return response
        else:
            print("No response received.")
            return None
    except Exception as e:
        print(f"Error sending Modbus command: {e}")
        return None

# Decode Modbus Response
def decode_response(response):
    try:
        if len(response) < 5:
            print("Invalid response length.")
            return
        #Connect to MQTT
        connect_mqtt()
        slave_address = response[0]
        function_code = response[1]
        byte_count = response[2]
        data = response[3:-2]

        print(f"Slave Address: {slave_address}, Function Code: {function_code}, Byte Count: {byte_count}")
        print("====================================================")
        print(f"Register Data:")
        print("----------------------------------------------------")
        tempsensor = 0
        power = 0
        cell_voltages = {}
        voltage = 0
        current = 0
        soc = 0
        rem_capacity = 0
        timeToGo = 0
        for i in range(0, byte_count-2, 2):
            register_index = i // 2 + 1
            register_value = ustruct.unpack('>H', data[i:i+2])[0]
            print(f"Register{register_index}: {register_value}")
            
            # Handle specific register decoding
            if 1 <= register_index <= 16:
                voltage = round(register_value * 0.001, 3)
                cell_voltages[f"Cell{register_index}"] = voltage
                publish_mqtt(f"{MQTT_TOPIC_BASE}Cell{register_index}Voltage", voltage)
                print(f"Cell{register_index}Voltage: {voltage}")
            if 49 <= register_index <= 52:
                tempsensor = tempsensor + 1
                publish_mqtt(f"{MQTT_TOPIC_BASE}BatteryTemp{tempsensor}", register_value-40)
                print(f"BatteryTemperature{tempsensor}: {register_value - 40}")
            elif register_index == 57:
                voltage = round(register_value * 0.1, 2)
                publish_mqtt(f"{MQTT_TOPIC_BASE}BatteryVoltage", voltage)
                print(f"BatteryVoltage: {voltage}")
            elif register_index == 58:
                current = round((register_value - 30000) * 0.1, 2)
                publish_mqtt(f"{MQTT_TOPIC_BASE}Current", current)
                print(f"Current: {current}")
            elif register_index == 59:
                soc = round(register_value / 10, 2)
                publish_mqtt(f"{MQTT_TOPIC_BASE}SOC", soc)
                print(f"SOC: {soc}")
            elif register_index == 76:
                rem_capacity = round(register_value * 0.1, 2)
                publish_mqtt(f"{MQTT_TOPIC_BASE}RemainingCapacity", rem_capacity)
                print(f"RemainingCapacity: {rem_capacity}")
            elif register_index == 89:
                power = register_value
                timeToGo = (rem_capacity-15) * 16 * 3.2 * 60 * 60 / power 
                publish_mqtt(f"{MQTT_TOPIC_BASE}TimeToGo", timeToGo)
                publish_mqtt(f"{MQTT_TOPIC_BASE}BatteryZeroTime", f"{int(timeToGo//3600)}hrs {int(timeToGo%60)}secs")
                print(f"TimeToGo: {timeToGo //3600} hrs {timeToGo%60} secs")
                if (current < 0):
                  power = power * -1
                publish_mqtt(f"{MQTT_TOPIC_BASE}Power", power)
                print(f"Power: {power}")
            if register_index == 89 and current < 0:
                publish_mqtt(f"{MQTT_TOPIC_BASE}PowerOut", power)
                print(f"PowerOut: {power}")
            elif register_index == 89 and current > 0:
                publish_mqtt(f"{MQTT_TOPIC_BASE}PowerIn", power)
                print(f"PowerIn: {power}")
            if (register_index == 91):
               mos_temp = round(register_value-40, 2)
               publish_mqtt(f"{MQTT_TOPIC_BASE}MosTemperature", mos_temp)
               print(f"MosTemperature: {mos_temp}")
            elif (register_index == 100):
               publish_mqtt(f"{MQTT_TOPIC_BASE}BatteryState", json.dumps({"Dc": {"Power": power, \
               "Voltage": voltage}, "Soc": soc, "Capacity": rem_capacity, "TimeToGo": timeToGo, \
               "Voltages": cell_voltages,  "Info": {"MaxChargeVoltage": 55.2, "MaxChargeCurrent": 80, "MaxDischarge": 100}, "System": {"MOSTemperature": mos_temp}}))
        #Close MQTT connection
        disconnect_mqtt()
    except Exception as e:
        print(f"Error decoding response: {e}")

# Main Loop
def main():
    modbus_command = bytes.fromhex("81 03 00 00 00 7F")
    while True:
        # Close previous MQTT connections if open
        disconnect_mqtt()
        response = send_modbus_command(modbus_command)
        if response:
            decode_response(response)
        time.sleep(10)  # Adjust polling interval as needed

if __name__ == "__main__":
    main()
