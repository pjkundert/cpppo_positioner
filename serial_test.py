import errno
import fcntl
import json
import logging
import minimalmodbus
import os
import pytest
import re
import serial
import signal
import subprocess
import subprocess
import sys
import time
import traceback


import cpppo
from remote.pymodbus_fixes import modbus_client_rtu, modbus_rtu_framer_collecting
from remote.plc_modbus import poller_modbus
from pymodbus.constants import Defaults

logging.basicConfig(
    #level=logging.WARNING,
    level=logging.DETAIL,
    #level=logging.INFO,
    #level=logging.DEBUG,
    datefmt='%m-%d %H:%M:%S',
    format='%(asctime)s.%(msecs).03d %(thread)16x %(name)-8.8s %(levelname)-8.8s %(funcName)-10.10s %(message)s' )

PORT_MASTER			= "/dev/ttyS1"
PORT_SLAVES			= {
    "/dev/ttyS0": [2,4],
    "/dev/ttyS2": [1,3],
}

PORT_STOPBITS			= 1
PORT_BYTESIZE			= 8
PORT_PARITY			= serial.PARITY_NONE
PORT_BAUDRATE			= 115200
PORT_TIMEOUT			= 1.5

# Configure minimalmodbus to use the specified port serial framing

minimalmodbus.STOPBITS		= PORT_STOPBITS
minimalmodbus.BYTESIZE		= PORT_BYTESIZE
minimalmodbus.PARITY		= PORT_PARITY
minimalmodbus.BAUDRATE		= PORT_BAUDRATE
minimalmodbus.TIMEOUT		= PORT_TIMEOUT

RTU_WAIT			= 2.0  # How long to wait for the simulator
RTU_LATENCY			= 0.05 # poll for command-line I/O response 
RTU_TIMEOUT			= 0.1  # latency while simulated slave awaits next incoming byte


class nonblocking_command( object ):
    """Set up a non-blocking command producing output.  Read the output using:

        collect 		= ''
        while True:
            if command is None:
                # Restarts command on failure, for example
                command 	= nonblocking_command( ... )

            try:
                data 		= command.stdout.read()
                logging.debug( "Received %d bytes from command, len( data ))
                collect        += data
            except IOError as exc:
                if exc.errno != errno.EAGAIN:
                    logging.warning( "I/O Error reading data: %s" % traceback.format_exc() )
                    command	= None
                # Data not presently available; ignore
            except:
                logging.warning( "Exception reading data: %s", traceback.format_exc() )
                command		= None

            # do other stuff in loop...

    The command is killed when it goes out of scope.
    """
    def __init__( self, command ):
        shell			= type( command ) is not list
        self.command		= ' '.join( command ) if not shell else command
        logging.info( "Starting command: %s", self.command )
        self.process		= subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            preexec_fn=os.setsid, shell=shell )

        fd 			= self.process.stdout.fileno()
        fl			= fcntl.fcntl( fd, fcntl.F_GETFL )
        fcntl.fcntl( fd, fcntl.F_SETFL, fl | os.O_NONBLOCK )

    @property
    def stdout( self ):
        return self.process.stdout

    def kill( self ):
        logging.info( 'Sending SIGTERM to PID [%d]: %s', self.process.pid, self.command )
        try:
            os.killpg( self.process.pid, signal.SIGTERM )
        except OSError as exc:
            logging.info( 'Failed to send SIGTERM to PID [%d]: %s', self.process.pid, exc )
        else:
            logging.info( "Waiting for command (PID [%d]) to terminate", self.process.pid )
            self.process.wait()

        logging.info("Command (PID [%d]) finished with status [%d]: %s", self.process.pid, self.process.returncode, self.command )

    __del__			= kill


def start_modbus_simulator( options ):
    command			= nonblocking_command( [
        os.path.join( '.', 'bin', 'modbus_sim.py' ), 
    ] + list( options ))

    begun			= cpppo.timer()
    address			= None
    data			= ''
    while address is None and cpppo.timer() - begun < RTU_WAIT:
        # On Python2, socket will raise IOError/EAGAIN; on Python3 may return None 'til command started.
        try:
            raw			= command.stdout.read()
            logging.debug( "Socket received: %r", raw)
            if raw:
                data  	       += raw.decode( 'utf-8' )
        except IOError as exc:
            logging.debug( "Socket blocking...")
            assert exc.errno == errno.EAGAIN, "Expected only Non-blocking IOError"
        except Exception as exc:
            logging.warning("Socket read return Exception: %s", exc)
        if not data:
            time.sleep( RTU_LATENCY )
        while data.find( '\n' ) >= 0:
            line,data		= data.split('\n', 1)
            logging.info( "%s", line )
            m			= re.search( "address = (.*)", line )
            if m:
                try:
                    host,port	= m.group(1).split(':')
                    address	= host,int(port)
                    logging.normal( "Modbus/TCP Simulator started after %7.3fs on %s:%d",
                                    cpppo.timer() - begun, address[0], address[1] )
                except:
                    assert m.group(1).startswith( '/' )
                    address	= m.group(1)
                    logging.normal( "Modbus/RTU Simulator started after %7.3fs on %s",
                                    cpppo.timer() - begun, address )
                break
    return command,address


def simulated_modbus_rtu( tty ):
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
            'serial_test', 'modbus_sim', 'log', os.path.basename( tty )] ),
        #'--evil', 'delay:.0-.1',
        '--address', tty,
        '    1 -  1000 = 0',
        '40001 - 41000 = 0',
        # Configure Modbus/RTU simulator to use specified port serial framing
        '--config', json.dumps( {
            'stopbits': PORT_STOPBITS,
            'bytesize': PORT_BYTESIZE,
            'parity':   PORT_PARITY,
            'baudrate': PORT_BAUDRATE,
            'slaves':	PORT_SLAVES[tty],
            'timeout':  RTU_TIMEOUT, # TODO: implement meaningfully; basically ignored
            'ignore_missing_slaves': True,
        } )
    ] )
    
@pytest.fixture(scope="module")
def simulated_modbus_rtu_ttyS0():
    return simulated_modbus_rtu( "/dev/ttyS0" )

@pytest.fixture(scope="module")
def simulated_modbus_rtu_ttyS2():
    return simulated_modbus_rtu( "/dev/ttyS2" )


def test_rs485_basic( simulated_modbus_rtu_ttyS0 ):
    """Use MinimalModbus to test RS485 read/write. """
    groups			= subprocess.check_output( ['groups'] )
    assert 'dialout' in groups, \
        "Ensure that the user is in the dialout group; run 'addgroup %s dialout'" % (
            os.environ.get( 'USER', '(unknown)' ))

    command,address		= simulated_modbus_rtu_ttyS0

    comm			= minimalmodbus.Instrument( port=PORT_MASTER, slaveaddress=2 )
    comm.debug			= True
    val				= comm.read_register( 1 )
    assert val == 0
    comm.write_register( 1, 99 )
    val				= comm.read_register( 1 )
    assert val == 99
    comm.write_register( 1, 0 )


def await( pred, what="predicate", delay=1.0, intervals=10 ):
    """Await the given predicate, returning: (success,elapsed)"""
    begun			= cpppo.timer()
    truth			= False
    for _ in range( intervals ):
        truth			= pred()
        if truth:
            break
        time.sleep( delay/intervals )
    now				= cpppo.timer()
    elapsed			= now - begun
    logging.info( "After %7.3f/%7.3f %s %s" % (
        elapsed, delay, "detected" if truth else "missed  ", what ))
    return truth,elapsed

def test_rs485_poll( simulated_modbus_rtu_ttyS0 ):
    """Multiple poller_modbus instances may be polling different slave RTUs at different unit IDs.

    """

    command,address		= simulated_modbus_rtu_ttyS0
    Defaults.Timeout		= PORT_TIMEOUT
    client			= modbus_client_rtu( framer=modbus_rtu_framer_collecting,
        port=PORT_MASTER, stopbits=PORT_STOPBITS, bytesize=PORT_BYTESIZE,
        parity=PORT_PARITY, baudrate=PORT_BAUDRATE )

    unit			= 2
    plc				= poller_modbus( "RS485 unit %s" % ( unit ), client=client, unit=unit, rate=.25 )
    try:
        plc.write( 1, 0 )
        plc.write( 40001, 0 )

        plc.poll( 40001 )

        success,elapsed		= await( lambda: plc.read( 40001 ) is not None, "40001 polled" )
        assert success
        assert elapsed < 1.0
        assert plc.read( 40001 ) == 0
    
        assert plc.read(     1 ) == None
        assert plc.read( 40002 ) == None
        success, elapsed	= await( lambda: plc.read( 40002 ) is not None, "40002 polled" )
        assert success
        assert elapsed < 1.0
        assert plc.read( 40002 ) == 0
        success,elapsed		= await( lambda: plc.read(     1 ) is not None, "00001 polled" )
        assert success
        assert elapsed < 1.0
        assert plc.read(     1 ) == 0

        plc.write( 40001, 99 )
        success,elapsed		= await( lambda: plc.read( 40001 ) == 99, "40001 polled" )
        assert success
        assert elapsed < 1.0
        
        # See if we converge on our target poll time
        count			= plc.counter
        while plc.counter < count + 20:
            logging.normal( "%s at poll %d: Load: %s ", plc.description, plc.counter, plc.load )
            time.sleep( .5 )
        logging.normal( "%s at poll %d: Load: %s ", plc.description, plc.counter, plc.load )

    except Exception as exc:
        logging.warning( "%s poller failed: %s", plc.description, traceback.format_exc() )
        raise
    finally:
        logging.info( "Stopping plc polling" )
        plc.done		= True
        await( lambda: not plc.is_alive(), "%s poller done" % ( plc.description ))

def test_rs485_multi( simulated_modbus_rtu_ttyS0,  simulated_modbus_rtu_ttyS2 ):

    command,address		= simulated_modbus_rtu_ttyS0
    command,address		= simulated_modbus_rtu_ttyS2
    Defaults.Timeout		= PORT_TIMEOUT
    client			= modbus_client_rtu( framer=modbus_rtu_framer_collecting,
        port=PORT_MASTER, stopbits=PORT_STOPBITS, bytesize=PORT_BYTESIZE,
        parity=PORT_PARITY, baudrate=PORT_BAUDRATE )

    slaves			= [1,2,3,4]
    plc				= {}
    for unit in slaves:
        plc[unit]		= poller_modbus( "RS485 unit %s" % ( unit ), client=client, unit=unit, rate=.25 )

    try:
        for unit in slaves:
            plc[unit].write(     1,  0 )
            plc[unit].write( 40001,  0 )
            plc[unit].poll(  40001 )

        # See if we converge on our target poll time
        count			= plc[slaves[0]].counter
        while any( plc[unit].counter < count + 20 for unit in slaves ):
            for unit in slaves:
                logging.normal( "%s at poll %d: Load: %s ", plc[unit].description, plc[unit].counter, plc[unit].load )
            time.sleep( .5 )
        for unit in slaves:
            logging.normal( "%s at poll %d: Load: %s ", plc[unit].description, plc[unit].counter, plc[unit].load )


        for unit in slaves:
            success,elapsed	= await( lambda: plc[unit].read( 40001 ) is not None, "%d/40001 polled" % ( unit ))
            assert success
            assert elapsed < 1.0
            assert plc[unit].read( 40001 ) == 0

        # Haven't polled 1 or 40002 yet
        for unit in slaves:
            assert plc[unit].read(     1 ) == None
            assert plc[unit].read( 40002 ) == None
        for unit in slaves:
            success, elapsed	= await( lambda: plc[unit].read( 40002 ) is not None, "%d/40002 polled" % ( unit ))
            assert success
            assert elapsed < 1.0
            assert plc[unit].read( 40002 ) == 0

            success,elapsed	= await( lambda: plc[unit].read(     1 ) is not None, "%d/00001 polled" % ( unit ))
            assert success
            assert elapsed < 1.0
            assert plc[unit].read(     1 ) == 0

        for unit in slaves:
            plc[unit].write( 40001,   99 )
            success,elapsed	= await( lambda: plc[unit].read( 40001 ) == 99, "%d/40001 polled" % ( unit ))
            assert success
            assert elapsed < 1.0

    except Exception as exc:
        logging.warning( "poller failed: %s", traceback.format_exc() )
        raise
    finally:
        logging.info( "Stopping plc polling" )
        for unit in slaves:
            plc[unit].done	= True
        for unit in slaves:
            await( lambda: not plc[unit].is_alive(), "%s poller done" % ( plc[unit].description ))
