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

import cpppo

PORT_MASTER			= "/dev/ttyS1"
PORT_SLAVE			= "/dev/ttyS0"

PORT_STOPBITS			= 1
PORT_BYTESIZE			= 8
PORT_PARITY			= serial.PARITY_NONE
PORT_BAUDRATE			= 19200
PORT_TIMEOUT			= 1.5

# Configure minimalmodbus to use the specified port serial framing

minimalmodbus.STOPBITS		= PORT_STOPBITS
minimalmodbus.BYTESIZE		= PORT_BYTESIZE
minimalmodbus.PARITY		= PORT_PARITY
minimalmodbus.BAUDRATE		= PORT_BAUDRATE
minimalmodbus.TIMEOUT		= PORT_TIMEOUT

RTU_WAIT			= 2.0  # How long to wait for the simulator
RTU_LATENCY			= 0.05 # poll for command-line I/O response 
RTU_SLAVES			= 1


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
@pytest.fixture(scope="module")
def simulated_modbus_rtu():
    """Start a simulator on a serial device PORT_SLAVE, reporting as the specified
    slave(s) (any slave ID, if 'slave' keyword is missing or None); parse
    whether device successfully opened.  Pass any remaining kwds as config
    options.

    """
    command			= nonblocking_command( [
        os.path.join( '.', 'bin', 'modbus_sim.py' ), 
        '-vvv', '--log', '.'.join( [
            'serial_test', 'modbus_sim', 'log', os.path.basename( PORT_SLAVE )] ),
        #'--evil', 'delay:.0-.1',
        '--address', PORT_SLAVE,
        '    1 -  1000 = 0',
        '40001 - 41000 = 0',
        # Configure Modbus/RTU simulator to use specified port serial framing
        '--config', json.dumps( {
            'stopbits': PORT_STOPBITS,
            'bytesize': PORT_BYTESIZE,
            'parity':   PORT_PARITY,
            'baudrate': PORT_BAUDRATE,
            'slaves':	RTU_SLAVES,
        } )
    ] )

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
            logging.warning( "%s", data )
            m			= re.search( "address = (.*)", line )
            if m:
                try:
                    host,port	= m.group(1).split(':')
                    address[1]	= int( address[1] )
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


def test_rs485( simulated_modbus_rtu ):
    """Use MinimalModbus to test RS485 read/write. """
    command,address		= simulated_modbus_rtu
    logging.warning( "Started Modbus Server on: %s", address )
    groups			= subprocess.check_output( ['groups'] )
    assert 'dialout' in groups, \
        "Ensure that the user is in the dialout group; run 'addgroup %s dialout'" % (
            os.environ.get( 'USER', '(unknown)' ))

    comm			= minimalmodbus.Instrument( port=PORT_MASTER, slaveaddress=1 )
    comm.debug			= True
    val				= comm.read_register( 1 )
    assert val == 0
    comm.write_register( 1, 99 )
    val				= comm.read_register( 1 )
    assert val == 99
    comm.write_register( 1, 0 )
