from enum import Enum
from dataclasses import dataclass
from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo


@dataclass
class BaseType:
    display_name: str
    command_value: str

class BoardType(BaseType, Enum):
#   Format : (Display Name, Command value)
    ESP32 = ("ESP32" , "esp32")
    # ESP32_S2 = ("ESP32 S2", "esp32s2")
    # ESP32_S3 = ("ESP32 S3", "esp32s3")
    # ESP32_C3 = ("ESP32 C3", "esp32c3")
    # ESP32_C6 = ("ESP32 C6", "esp32c6")

class FilesystemType(BaseType, Enum):
#   Format : (Display Name, Command value)
    LITTLEFS = ("LittleFS", "lfs")
    # SPIFFS   = ("SPIFFS",   "spiffs")
    # FATFS    = ("FatFS",    "fat")

class BaudrateType(BaseType, Enum):
#   Format : (Display Name, Command value)
    FAST    = ("921600",  921600)
    STANDARD = ("460800", 460800)
    LEGACY   = ("115200", 115200)

def serial_port_enumerator(detailed: bool = False):
    ports : list[ListPortInfo] = list_ports.comports()
    if detailed:
        return ports
    else:
        data = [BaseType(f"{port.device} - ({port.description})", port.device) for port in ports]
        return data

def get_partition_table():
    pass

get_partition_table()