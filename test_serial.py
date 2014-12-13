import minimalmodbus
import serial
import subprocess
import sys
import os

PORT_MASTER			= "/dev/ttyS1"
PORT_SLAVE			= "/dev/ttyS0"

minimalmodbus.STOPBITS		= 1
minimalmodbus.BYTESIZE		= 8
minimalmodbus.PARITY		= serial.PARITY_NONE
minimalmodbus.BAUDRATE		= 4800
minimalmodbus.TIMEOUT		= 0.5



def test_serial_rs485():
    """Use MinimalModbus to test RS485 read/write. """
    
    groups			= subprocess.check_output( ['groups'] )
    assert 'dialout' in groups, \
        "Ensure that the user is in the dialout group; run 'addgroup %s dialout'" % (
            os.environ.get( 'USER', '(unknown)' ))

    comm			= minimalmodbus.Instrument( port=PORT_MASTER, slaveaddress=1 )
    comm.debug			= True
    val				= comm.read_register( 1 )
    assert val == 0
