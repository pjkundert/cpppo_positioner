import json
import time

import pytest

import smc
import cpppo
from cpppo.modbus_test import start_modbus_simulator
from cpppo.tools import await

'''
import logging
cpppo.log_cfg['level']		= logging.DETAIL
logging.basicConfig( **cpppo.log_cfg )
'''

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
            'smc_test', 'modbus_sim', 'log', 'actuator_'+'_'.join( map( str, slaves )) ] ),
        #'--evil', 'delay:.0-.1',
        '--address', tty,
        '    17 -     64 = 0',	# Coil           0x10   - 0x30   (     1 +) (rounded to 16 bits)
        ' 10065 -  10080 = 0',	# Discrete Input 0x40   - 0x4F   ( 10001 +)
        ' 76865 -  77138 = 0',	# Holding Regs   0x9000 - 0x9111 ( 40001 +)
        # Configure Modbus/RTU simulator to use specified port serial framing
        '--config', json.dumps( {
            'stopbits': smc.PORT_STOPBITS,
            'bytesize': smc.PORT_BYTESIZE,
            'parity':   smc.PORT_PARITY,
            'baudrate': smc.PORT_BAUDRATE,
            'slaves':	slaves,
            'timeout':  0.1, # TODO: implement meaningfully; basically ignored
            'ignore_missing_slaves': True,
        } )
    ] )
    
@pytest.fixture( scope="module" )
def simulated_actuator_1():
    return simulated_actuator( "/dev/ttyS2", slaves=[1,3] )

@pytest.fixture( scope="module" )
def simulated_actuator_2():
    return simulated_actuator( "/dev/ttyS0", slaves=[2,4] )

def test_smc_basic( simulated_actuator_1, simulated_actuator_2 ):

    command,address		= simulated_actuator_1
    command,address		= simulated_actuator_2

    positioner			= smc.smc_modbus()

    '''
    # Initiate polling of actuator 2
    assert positioner.status( actuator=2 )['current_position'] is None
    '''

    # Test polling of actuator 1
    status 			= None
    now				= cpppo.timer()
    while cpppo.timer() < now + 1 and (
            not status
            or status['current_position'] is None ):
        time.sleep( .1 )
        status			= positioner.status( actuator=1 )
    assert status['current_position'] == 0

    # Modify actuator 1 current position
    unit			= positioner.unit( uid=1 )
    unit.write( 40001 + 0x9000, 0x0000 )
    unit.write( 40001 + 0x9001, 0x3a98 )
    
    # make certain it gets polled correctly with updated value
    now				= cpppo.timer()
    status			= None
    while cpppo.timer() < now + 1 and (
            not status
            or status['current_position'] != 15000 ):
        time.sleep( .1 )
        status			= positioner.status( actuator=1 )
    assert status['current_position'] == 15000

    '''
    # but the unmodified actuator should still now be polling a 0...
    assert positioner.status( actuator=2 )['current_position'] is 0
    '''
    positioner.close()

def test_smc_position( simulated_actuator_1 ):

    command,address		= simulated_actuator_1

    positioner			= smc.smc_modbus()

    # No position data; should just check that previous positioning complete (it will always be
    # complete, because the positioner (simulator) drives Status X4B_INP False)
    unit			= positioner.unit( uid=1 )

    '''
    # Cannot write Status (read-only)...
    unit.write( smc.data.X4B_INP.addr, True ) # Positioning incomplete
    await.waitfor( positioner.status()['X4B_INP'] is True, "positioner polled", timeout=1 )
    try:
        status			= positioner.position( actuator=1, timeout=.1 )
        assert False, "Should have failed to detect positioning completion"
    except Exception as exc:
        assert 'failure' in str( exc )
    unit.write( smc.data.X4B_INP.addr, False ) # Positioning complete
    await.waitfor( positioner.status()['X4B_INP'] is False, "positioner polled", timeout=1 )
    '''
    status			= positioner.position( actuator=1, timeout=5 )

    assert status['X4B_INP'] == False, "Should have detected positioning complete: %r" % ( status )
    positioner.close()
