import json
import logging
import os
import time

import pytest
import cpppo

import smc
from .serial_test import start_modbus_simulator, RTU_TIMEOUT, await

logging.basicConfig(
    #level=logging.WARNING,
    level=logging.DETAIL,
    #level=logging.INFO,
    #level=logging.DEBUG,
    datefmt='%m-%d %H:%M:%S',
    format='%(asctime)s.%(msecs).03d %(thread)16x %(name)-8.8s %(levelname)-8.8s %(funcName)-10.10s %(message)s' )

def simulated_actuator( tty, slaves ):
    """Start a simulator on a serial device PORT_SLAVE, reporting as the specified slave(s) (any slave
    ID, if 'slave' keyword is missing or None); parse whether device successfully opened.  Pass any
    remaining kwds as config options.

    TODO: Implement RS485 inter-character and pre/post request timeouts properly.  Right now, the
    simulator just waits forever for the next character and tries to frame requests.  It should fail
    a request if it ever sees an inter-character delay of > 1.5 character widths, and it also
    expects certain delays before/after requests.

    """
    return start_modbus_simulator( options=[
        '-vvv', '--log', '.'.join( [
            'serial_test', 'modbus_sim', 'log', 'actuator_'+'_'.join( map( str, slaves )) ] ),
        #'--evil', 'delay:.0-.1',
        '--address', tty,
        '    17 -     49 = 0', # Coil           0x10   - 0x30   (     1 +)
        '100065 - 100080 = 0', # Discrete Input 0x40   - 0x4F   (100001 +)
        '436865 - 437121 = 0', # Holding Regs   0x9000 - 0x9110 (400001 +)
        # Configure Modbus/RTU simulator to use specified port serial framing
        '--config', json.dumps( {
            'stopbits': smc.PORT_STOPBITS,
            'bytesize': smc.PORT_BYTESIZE,
            'parity':   smc.PORT_PARITY,
            'baudrate': smc.PORT_BAUDRATE,
            'slaves':	slaves,
            'timeout':  RTU_TIMEOUT, # TODO: implement meaningfully; basically ignored
            'ignore_missing_slaves': True,
        } )
    ] )
    
@pytest.fixture(scope="module")
def simulated_actuator_1():
    return simulated_actuator( "/dev/ttyS0", slaves=[1] )

@pytest.fixture(scope="module")
def simulated_actuator_2():
    return simulated_actuator( "/dev/ttyS2", slaves=[2] )

def test_smc_basic( simulated_actuator_1, simulated_actuator_2 ):
    command,address		= simulated_actuator_1
    command,address		= simulated_actuator_2

    positioner			= smc.smc_modbus()

    status 			= None
    now				= cpppo.timer()
    while cpppo.timer() < now + 1 and (
            not status
            or status['current_position'] is None ):
        time.sleep( .1 )
        status			= positioner.status( actuator=1 )
    assert status['current_position'] == 0

    poller			= positioner.unit( uid=1 )
    poller.write( 400001 + 0x9000, 0x0000 )
    poller.write( 400001 + 0x9001, 0x3a98 )
    
    now				= cpppo.timer()
    while cpppo.timer() < now + 1 and (
            not status
            or status['current_position'] != 15000 ):
        time.sleep( .1 )
        status			= positioner.status( actuator=1 )
    assert status['current_position'] == 15000
