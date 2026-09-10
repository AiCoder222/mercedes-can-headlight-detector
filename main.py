#!/usr/bin/env python3
"""
Mercedes CAN Bus Automatic Headlight Detector
Decodes and detects automatic headlight status from Mercedes vehicles
"""

import can
import struct
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HeadlightMode(Enum):
    """Headlight operating modes"""
    OFF = 0x00
    PARKING = 0x01
    LOW_BEAM = 0x02
    HIGH_BEAM = 0x03
    AUTO = 0x04
    UNKNOWN = 0xFF


class HeadlightStatus(Enum):
    """Headlight status indicators"""
    OFF = 0x00
    ON = 0x01
    FAULT = 0x02
    NOT_AVAILABLE = 0xFF


@dataclass
class HeadlightData:
    """Structured headlight data from CAN bus"""
    mode: HeadlightMode
    status: HeadlightStatus
    brightness_level: int  # 0-100%
    auto_mode_active: bool
    ambient_light_level: int  # 0-255
    rain_detected: bool
    daytime_running_lights: bool
    left_headlight_ok: bool
    right_headlight_ok: bool
    timestamp: float


class MercedesCANDecoder:
    """Mercedes CAN bus decoder for headlight systems"""
    
    # Common Mercedes CAN IDs for headlight data
    HEADLIGHT_STATUS_ID = 0x340  # Primary headlight status
    LIGHTING_CONTROL_ID = 0x341  # Lighting control info
    AMBIENT_LIGHT_ID = 0x342     # Ambient light sensor
    COMFORT_TELEMETRY_ID = 0x345 # Comfort functions
    
    def __init__(self, channel: str = 'can0', bitrate: int = 500000):
        """
        Initialize CAN bus connection
        
        Args:
            channel: CAN interface (e.g., 'can0', 'PCAN_USBBUS1')
            bitrate: CAN bus bitrate (500000 for Mercedes)
        """
        self.channel = channel
        self.bitrate = bitrate
        self.bus = None
        self.headlight_data = None
        
    def connect(self) -> bool:
        """Establish CAN bus connection"""
        try:
            self.bus = can.interface.Bus(channel=self.channel, bitrate=self.bitrate)
            logger.info(f"Connected to CAN bus on {self.channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to CAN bus: {e}")
            return False
    
    def disconnect(self):
        """Close CAN bus connection"""
        if self.bus:
            self.bus.shutdown()
            logger.info("CAN bus connection closed")
    
    def decode_headlight_status(self, data: bytes) -> HeadlightData:
        """
        Decode headlight status from CAN message
        
        Byte layout:
        [0] - Mode (bits 0-3), Auto Mode (bit 4), Status (bits 5-7)
        [1] - Brightness Level (0-100)
        [2] - Ambient Light Level (0-255)
        [3] - Flags: Rain (bit 0), DRL (bit 1), L-OK (bit 2), R-OK (bit 3)
        [4] - Reserved
        [5] - Reserved
        [6] - Reserved
        [7] - Checksum
        """
        if len(data) < 8:
            logger.warning("Invalid data length for headlight status")
            return None
        
        try:
            # Byte 0: Mode and Status
            byte0 = data[0]
            mode_raw = byte0 & 0x0F
            auto_mode_active = bool((byte0 >> 4) & 0x01)
            status_raw = (byte0 >> 5) & 0x07
            
            # Byte 1: Brightness
            brightness = data[1]
            
            # Byte 2: Ambient light
            ambient_light = data[2]
            
            # Byte 3: Flags
            byte3 = data[3]
            rain_detected = bool(byte3 & 0x01)
            drl_active = bool((byte3 >> 1) & 0x01)
            left_ok = bool((byte3 >> 2) & 0x01)
            right_ok = bool((byte3 >> 3) & 0x01)
            
            # Convert raw values to enums
            mode = HeadlightMode(mode_raw) if mode_raw < len(HeadlightMode) else HeadlightMode.UNKNOWN
            status = HeadlightStatus(status_raw) if status_raw < len(HeadlightStatus) else HeadlightStatus.NOT_AVAILABLE
            
            return HeadlightData(
                mode=mode,
                status=status,
                brightness_level=min(brightness, 100),
                auto_mode_active=auto_mode_active,
                ambient_light_level=ambient_light,
                rain_detected=rain_detected,
                daytime_running_lights=drl_active,
                left_headlight_ok=left_ok,
                right_headlight_ok=right_ok,
                timestamp=0
            )
        except Exception as e:
            logger.error(f"Error decoding headlight status: {e}")
            return None
    
    def process_can_message(self, msg: can.Message) -> Optional[HeadlightData]:
        """Process incoming CAN message"""
        if msg.arbitration_id == self.HEADLIGHT_STATUS_ID:
            return self.decode_headlight_status(msg.data)
        return None
    
    def listen(self, timeout: Optional[float] = None):
        """Listen for CAN messages and process headlight data"""
        if not self.bus:
            logger.error("CAN bus not connected")
            return
        
        logger.info("Listening for Mercedes headlight data...")
        
        try:
            for msg in self.bus:
                headlight_data = self.process_can_message(msg)
                
                if headlight_data:
                    self.headlight_data = headlight_data
                    self.print_headlight_status()
        except KeyboardInterrupt:
            logger.info("Listening stopped by user")
        except Exception as e:
            logger.error(f"Error during CAN bus listen: {e}")
    
    def print_headlight_status(self):
        """Print formatted headlight status output"""
        if not self.headlight_data:
            return
        
        data = self.headlight_data
        
        output = f"""
╔════════════════════════════════════════════════════╗
║         MERCEDES AUTOMATIC HEADLIGHT STATUS        ║
╠════════════════════════════════════════════════════╣
║ Mode:                    {data.mode.name:<30} ║
║ Status:                  {data.status.name:<30} ║
║ Brightness Level:        {data.brightness_level}%{' '*28} ║
║ Auto Mode Active:        {str(data.auto_mode_active):<30} ║
║ Ambient Light Level:     {data.ambient_light_level}/255{' '*25} ║
║ Rain Detected:           {str(data.rain_detected):<30} ║
║ Daytime Running Lights:  {str(data.daytime_running_lights):<30} ║
║ Left Headlight Status:   {"OK" if data.left_headlight_ok else "FAULT":<30} ║
║ Right Headlight Status:  {"OK" if data.right_headlight_ok else "FAULT":<30} ║
╚════════════════════════════════════════════════════╝
"""
        print(output)
    
    def get_current_status(self) -> Dict:
        """Get current headlight status as dictionary"""
        if not self.headlight_data:
            return {}
        
        data = self.headlight_data
        return {
            'mode': data.mode.name,
            'status': data.status.name,
            'brightness_level': data.brightness_level,
            'auto_mode_active': data.auto_mode_active,
            'ambient_light_level': data.ambient_light_level,
            'rain_detected': data.rain_detected,
            'daytime_running_lights': data.daytime_running_lights,
            'left_headlight_ok': data.left_headlight_ok,
            'right_headlight_ok': data.right_headlight_ok
        }


def main():
    """Main execution function"""
    # Initialize decoder
    decoder = MercedesCANDecoder(channel='can0', bitrate=500000)
    
    # Connect to CAN bus
    if not decoder.connect():
        logger.error("Failed to initialize CAN connection")
        return
    
    try:
        # Start listening for headlight data
        decoder.listen()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        decoder.disconnect()


if __name__ == '__main__':
    main()
