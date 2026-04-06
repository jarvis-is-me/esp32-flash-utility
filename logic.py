from enum import Enum
from dataclasses import dataclass
from struct import unpack

from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo

from esptool.cmds import (
attach_flash,
read_flash,
reset_chip,
run_stub,
)

from esptool.targets import ESP32ROM

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


@dataclass
class ESPConfigType:
    board: BoardType
    baudrate: BaudrateType
    port: str

class PartitionType(Enum):
    APP = 0x00
    DATA = 0x01
    BOOTLOADER = 0x02
    PARTITION_TABLE = 0x03

class PartitionSubType(Enum):
    """
    a partition subtype has a lot of possible types including custom types
    we cant add enumerators for all of them
    """
    FATFS = 0x81
    SPIFFS = 0x82
    LITTLEFS = 0x83

    # To be used when the partition sub type is not one of the relevant ones
    INVALID = 0xFF

@dataclass
class PartitionTableEntry:
    """
    Represents 1 entry in a partition table (32 bytes)
    First two bytes are magic bytes , which are always 0x50AA
    Rest of the 30 bytes are distributed as below members
    """
    # First two bytes are magic bytes
    type: PartitionType         # 1 byte
    subtype: PartitionSubType   # 1 byte
    offset: int                 # 4 bytes, typically 0x8000
    size: int                   # 4 bytes
    label: str                  # 16 bytes
    flags: int                  # 4 bytes

    # Default constant to be used anywhere so we don't hardcode 0x50AA anywhere.
    # This is not related to any instance, but just a symbolic constant
    DEFAULT_MAGIC: int = 0x50AA


def serial_port_enumerator(detailed: bool = False):
    """
    Gets a list of current serial ports
    :param detailed: set to true if you want the actual port objects and not a string representation to be used in a combo box
    :return: if detailed is set to false function returns a list[BaseType] objects which contain string information about a port
             if detailed is set to true function returns a list[ListPortInfo] objects which are references to actual ports and will give a bit more information
    """
    ports : list[ListPortInfo] = list_ports.comports()
    if detailed:
        return ports
    else:
        data = [BaseType(f"{port.device} - ({port.description})", port.device) for port in ports]
        return data

def parse_raw_partition_table_entry(raw_entry: bytes) -> PartitionTableEntry:
    """
    Parses a single chunk of 32 bytes into a PartitionTableEntry object.
    NOTE : values are **little endian**
    :return: PartitionTableEntry
    """
    assert len(raw_entry) == 32 # The partition entry must be exactly 32 bytes including the starting magic bits

    # type_t so that it doesn't clash with internal type
    magic, type_t, subtype, offset, size, label, flags = unpack("<HBBII16sI", raw_entry)

    type_t = PartitionType(type_t)

    try:
        subtype = PartitionSubType(subtype)
    except ValueError:
        subtype = PartitionSubType.INVALID

    label = label.rstrip(b'\x00').decode('utf-8')

    return PartitionTableEntry(type_t, subtype, offset, size, label, flags)

def get_partition_table(config :ESPConfigType, offset: int):
    """
    Reads partition table from the given offset
    :param config: Information about the target ESP needed for connecting over serial
    :param offset: The offset in memory where the partition table is located
    :return: a list of PartitionTableEntry
    """
    raw_data = None
    partition_table: list[PartitionTableEntry] = []

    if config.board == BoardType.ESP32:
        with ESP32ROM(config.port) as esp:
            esp.connect()  # Connect to the ESP chip, needed when ESP32ROM is instantiated directly
            esp = run_stub(esp)  # Run the stub loader (optional)
            attach_flash(esp)  # Attach the flash memory chip, required for flash operations
            raw_data = read_flash(esp, offset, 0x1000)  # 0x1000 is the size of partition table including the MD5 checksum
            reset_chip(esp, "hard-reset")  # Reset the board

    for i in range(0,len(raw_data),32):
        magic = unpack("<H", raw_data[i:i+2])[0]
        if magic == PartitionTableEntry.DEFAULT_MAGIC :
            partition_table.append( parse_raw_partition_table_entry( raw_data[i:i+32]) )
        else:
            break

    return partition_table

def get_filesyste_data():
    

get_partition_table(ESPConfigType(BoardType.ESP32, BaudrateType.FAST, "COM5"), 0x8000)