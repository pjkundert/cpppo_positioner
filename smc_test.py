import json
import os
import pytest
import time

import cpppo
from cpppo.modbus_test import start_modbus_simulator

from . import smc

import logging
cpppo.log_cfg['level']		= logging.DETAIL
logging.basicConfig( **cpppo.log_cfg )

#
# Set eg. SERIAL_TEST=ttyV to specific the correct target serial ports:
#
# $ python3 ./ttyV-setup.py &
# $ SERIAL_TEST=ttyV make test
#
PORT_BASE			= os.environ.get( "SERIAL_TEST", "ttyS" )

#
# For the purposes of testing, we could change the global smc.PORT_MASTER to our testing port, but
# that would cause problems if this smc_test.py file ever got loaded during production.  So, we'll
# ensure the start_modbus_simulator starts on the correct PORT_SLAVE_# TTYs, and we pass the
# 'address' parameter when we start the smc_modbus clients!
#
PORT_MASTER			= "{PORT_BASE}0".format( PORT_BASE=PORT_BASE )

PORT_SLAVE_1			= "{PORT_BASE}1".format( PORT_BASE=PORT_BASE )
PORT_SLAVE_2			= "{PORT_BASE}2".format( PORT_BASE=PORT_BASE )
PORT_SLAVES			= {
    PORT_SLAVE_1: [1,3],
    PORT_SLAVE_2: [2,4],
}


def simulated_actuator( tty ):
    """Start a simulator on a serial device PORT_SLAVE, reporting as the specified slave(s) (any slave
    ID, if 'slave' keyword is missing or None); parse whether device successfully opened.  Pass any
    remaining kwds as config options.

    TODO: Implement RS485 inter-character and pre/post request timeouts properly.  Right now, the
    simulator just waits forever for the next character and tries to frame requests.  It should fail
    a request if it ever sees an inter-character delay of > 1.5 character widths, and it also
    expects certain delays before/after requests.

    """
    return start_modbus_simulator(
        '-vvv', '--log', '.'.join( [
            'smc_test', 'modbus_sim', 'log', 'actuator_'+'_'.join( map( str, PORT_SLAVES[tty] )) ] ),
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
            'slaves':	PORT_SLAVES[tty],
            'timeout':  smc.PORT_TIMEOUT,
            'ignore_missing_slaves': True,
        } )
    )


@pytest.fixture( scope="module" )
def simulated_actuator_1( request ):
    command,address		= simulated_actuator( PORT_SLAVE_1 )
    request.addfinalizer( command.kill )
    return command,address


@pytest.fixture( scope="module" )
def simulated_actuator_2( request ):
    command,address		= simulated_actuator( PORT_SLAVE_2 )
    request.addfinalizer( command.kill )
    return command,address


def test_smc_basic( simulated_actuator_1, simulated_actuator_2 ):

    command,address		= simulated_actuator_1
    command,address		= simulated_actuator_2

    positioner			= smc.smc_modbus( address=PORT_MASTER )

    # Test polling of actuator 1
    status 			= None
    now				= cpppo.timer()
    while cpppo.timer() < now + 1 and (
            not status
            or status['current_position'] is None ):
        time.sleep( .1 )
        status			= positioner.status( actuator=1 )
        logging.info( f"Status after {cpppo.timer()-now:7.1}s: {json.dumps(status, indent=4)}" )
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



    # Stock pymodbus fails (cannot handle RS-485 multi-drop).
    # - Install github.com/pjkundert/pymodbus.git@fix/decode to test
    '''
    # Initiate polling of actuator 2
    assert positioner.status( actuator=2 )['current_position'] is None
    time.sleep( 4 )
    # but the unmodified actuator should still now be polling a 0...
    assert positioner.status( actuator=2 )['current_position'] == 0
    '''

    positioner.close()


def test_smc_position( simulated_actuator_1, simulated_actuator_2 ):

    command,address		= simulated_actuator_1
    command,address		= simulated_actuator_2

    positioner			= smc.smc_modbus( PORT_MASTER )

    # No position data; should just check that previous positioning complete (it will always be
    # complete, because the positioner (simulator) drives Status X4B_INP False)
    unit			= positioner.unit( uid=1 )  # noqa: F841

    '''
    # Cannot write Status (read-only)...
    unit.write( smc.data.X4B_INP.addr, True ) # Positioning incomplete
    waits.waitfor( positioner.status()['X4B_INP'] is True, "positioner polled", timeout=1 )
    try:
        status			= positioner.position( actuator=1, timeout=.1 )
        assert False, "Should have failed to detect positioning completion"
    except Exception as exc:
        assert 'failure' in str( exc )
    unit.write( smc.data.X4B_INP.addr, False ) # Positioning complete
    waits.waitfor( positioner.status()['X4B_INP'] is False, "positioner polled", timeout=1 )
    '''
    status			= positioner.position( actuator=1, timeout=5 )

    assert status['X48_BUSY'] == False, "Should have detected positioning complete: %r" % ( status )
    positioner.close()
