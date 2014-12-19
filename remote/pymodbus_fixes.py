
# 
# Cpppo -- Communication Protocol Python Parser and Originator
# 
# Copyright (c) 2013, Hard Consulting Corporation.
# 
# Cpppo is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.  See the LICENSE file at the top of the source tree.
# 
# Cpppo is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
# 

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

__author__                      = "Perry Kundert"
__email__                       = "perry@hardconsulting.com"
__copyright__                   = "Copyright (c) 2013 Hard Consulting Corporation"
__license__                     = "Dual License: GPLv3 (or later) and Commercial (see LICENSE)"

"""
remote.pymodbus_fixes -- PyModbus has some issues that need fixing
"""
__all__				= ['modbus_server_tcp', 'modbus_server_rtu', 'modbus_rtu_framer_collecting',
                                   'modbus_client_timeout', 'modbus_client_rtu', 'modbus_client_tcp']
import logging
import os
import select
import socket
import sys
import threading
import time
import traceback

import cpppo

# We need to monkeypatch ModbusTcpServer's SocketServer.serve_forever to be
# Python3 socketserver interface-compatible.  When pymodbus is ported to Python3, this
# will not be necessary in the Python3 implementation.
assert sys.version_info.major < 3, "pymodbus is not yet Python3 compatible"
from pymodbus.server.sync import ModbusTcpServer, ModbusSerialServer, ModbusSingleRequestHandler
from SocketServer import _eintr_retry

from pymodbus.transaction import ModbusSocketFramer, ModbusRtuFramer
from pymodbus.constants import Defaults
from pymodbus.client.sync import ModbusTcpClient, ModbusSerialClient
from pymodbus.factory import ClientDecoder
from pymodbus.exceptions import *
from pymodbus.pdu import (ExceptionResponse, ModbusResponse)


class modbus_rtu_framer_collecting( ModbusRtuFramer ):
    """Unfortunately, the standard ModbusSerialServer uses the PySerial Serial.read
    as an equivalent to Socket.recv.  It is not semantically equivalent.  The
    Socket.recv will block and then return all the data available (up to and
    including 1024 bytes) before timeout, which will eventually include a
    complete transaction.  The Serial.read will block 'til its either achieves
    its target number of bytes or times out.

    If ModbusSerialServer instead invoked the recv method with its default
    number of bytes (1, for Serial.read), then this might work; we would
    receive, frame and respond to an incoming request as soon as its last byte
    arrived.  However, ModbusSerialServer calls it with 1024, forcing
    Serial.read to time out -- every request always takes at least
    Defaults.Timeout to arrive (awaiting the next byte after the termination of
    the request, which never arrives)!

    Therefore, we need to patch ModbusSerialServer._build_handler to provide a
    semantically correct recv.  It differs from ModbusSerialClient in that
    receiving nothing is not an error.

    Neither of these are quite right for serial communications, especially
    Modbus/RTU as implemented by ModbusRtuFramer.  Since it discards any
    partially received packet, the recv method must:

    - await the start of a packet
      - in the RTU simulator, with no timeout (or a long timeout)
    - once receiving, continue receiving 'til a full request is read
      - a space of >=1.5 character periods indicates end of the request
      - a worst-case timeout of greater than the maximum request size (eg. double?)

    The standard serial read semantics with a VMIN of 1 (wait 'til at least one
    symbol is received), and a VTIME of 1/baudrate*1.5 would do this perfectly
    -- if VTIME wasn't in units of 1/10th seconds!  This is much too long: at
    115200bps, 1.5 character times (about 10 bits/character) is ~1.5/11520 or
    0.00013 seconds.  The minimum inter-request time is ~3.5/11520 or 0.0003
    seconds!

    So, we must implement such timeouts using select/poll (or, ideally, the
    lower-level RS485-specific IOCTLs, but these are not available except on the
    latest kernels and only in some UART kernel modules.)

    However, the underlying UART receive to select/poll activation may (often
    will) be significantly delayed due to kernel scheduling!  So, not even
    significantly increasing the inter-character timeout to a multiple of the
    inter-message timeout works reliably.  We simply cannot depend on user-level
    timeouts to detect the end of an RS-485 Modbus/RTS frame!

    We have to detect it statistically.

    After each group of UART input is received immediately when available (with
    *no* inter-character timeout at all), we will attempt to detect a frame.  If
    no frame is available, there are several possibilities:

    1) The frame is incomplete
    2) The frame is corrupt
    3) Some of the leading characters are spurious (noise)

    We can't (of course) know for certain.  However, most often the frame will
    just be incomplete (especially at low baud rates), so we should just wait
    for more characters.  But, we don't want to get locked up on corrupt frames
    or noise, so we don't want to wait forever!  We could use timing (eg. if its
    a long time since last data, throw it out).  But that's hacky, and depends
    on baudrate, which we don't know in the ModbusRtuFramer.

    What is *unlikely* is that there is *another* correct message hidden within
    the valid message.  Just finding a correct CRC for some arbitrary chunk of
    data is P(1/65536).  Finding a full frame with a correct CRC is probably
    pretty unlikely.

    So, keep collecting characters -- never throw them out 'til we find a frame.
    However, each time we get a block of new data, search through it for a valid
    frame.  When one is found, throw out the leading characters (they are noise,
    or an old, corrupted frame), and return the valid frame!

    """
    def processIncomingPacket(self, data, callback):
        '''Exactly like the base-class ModbusRtuFramer, except we just break out if no
        frame is found.  We could have hacked a way to pop out via
        .isFrameReady() returning False just after a .resetFrame() but that
        would be very subtle...

        '''
        self.addToFrame(data)
        while self.isFrameReady():
            if self.checkFrame():
                result = self.decoder.decode(self.getFrame())
                if result is None:
                    raise ModbusIOException("Unable to decode response")
                self.populateResult(result)
                self.advanceFrame()
                callback(result)  # defer or push to a thread?
            else: break

    def checkFrame( self ):
        saved			= self._ModbusRtuFramer__buffer
        try:
            for start in range( 0, max( 1, len( saved ) - 4 )):
                self._ModbusRtuFramer__buffer = saved[start:]
                if super( modbus_rtu_framer_collecting, self ).checkFrame():
                    # Found a frame!  Update saved if we had to advance due to noise
                    logging.info( "Found valid frame at %d/%d bytes", start, len( saved ))
                    if start:
                        saved	= saved[start:]
                    return True
        finally:
            # Restore base-class .__buffer to original/updated 'saved' on *all* exits
            self._ModbusRtuFramer__buffer = saved
        return False


class modbus_server_tcp( ModbusTcpServer ):
    """Augments the stock pymodbus ModbusTcpServer with the Python3 'socketserver'
    class periodic invocation of the .service_actions() method from within the
    main serve_forever loop.  This allows us to perform periodic service:

        class our_modbus_server( ModbusTcpServerActions ):
            def service_actions( self ):
                logging.info( "Doing something every ~<seconds>" )


        # Start our modbus server, which spawns threads for each new client
        # accepted, and invokes service_actions every ~<seconds> in between.
        modbus = ModbusTcpServerActions()
        modbus.serve_forever( poll_interval=<seconds> )


    The serve_forever implementation comes straight from Python3 socketserver,
    which is basically an enhancement of Python2 SocketServer.

    """
    def serve_forever( self, poll_interval=.5 ):
        self._BaseServer__is_shut_down.clear()
        try:
            while not self._BaseServer__shutdown_request:
                r,w,e 		= _eintr_retry( select.select, [self], [], [], poll_interval )
                if self in r:
                    self._handle_request_noblock()

                self.service_actions()  # <<< Python3 socketserver added this
        finally:
            self._BaseServer__shutdown_request = False
            self._BaseServer__is_shut_down.set()

    def service_actions( self ):
        """Override this to receive service every ~poll_interval s."""
        pass


class modbus_server_rtu( ModbusSerialServer ):
    def _build_handler( self ):

        def recv( size=1024 ):
            begun		= time.time()
            logging.debug( "Receive begins  in %7.3f/%7.3fs", time.time() - begun, self.socket._timeout )
            read		= bytearray()
            r,w,e		= select.select( [self.socket.fd], [], [], self.socket._timeout )
            while r and len( read ) < size:
                # Still readable, and size not yet satisfied; get the next one
                buf		= os.read( self.socket.fd, 1 )
                if not buf:
                    raise SerialException('device reports readiness to read but returned no data (device disconnected or multiple access on port?)')
                read.extend( buf )
                logging.debug( "Receive reading in %7.3f/%7.3fs; %d bytes", time.time() - begun,
                               self.socket._timeout, len( read ))
                # Something has been read!  No more waiting
                r,w,e		= select.select( [self.socket.fd], [], [], 0 )
    
            logging.debug( "Receive success in %7.3f/%7.3fs; %d bytes", time.time() - begun,
                           self.socket._timeout, len( read ))
            return bytes( read )

        request			= self.socket
        request.send		= request.write
        request.recv		= recv
        handler			= ModbusSingleRequestHandler( request, (self.device, self.device), self )
        return handler


class modbus_client_timeout( object ):
    """Enforces a strict timeout on a complete transaction, including connection and I/O.  The
    beginning of a transaction is indicated by assigning a timeout to the transaction property.  At
    any point, the remaining time available is computed by accessing the transaction property.

    If .timeout is set to True/0, uses Defaults.Timeout around the entire transaction.  If
    transaction is never set or set to None, Defaults.Timeout is always applied to every I/O
    operation, independently (the original behaviour).

    Otherwise, the specified non-zero timeout is applied to the entire transaction.

    If a mutual exclusion lock on a <client> instance is desired (eg. if multiple Threads may be
    attempting to access this client simultaneously, eg. in the case where several independent
    Threads are accessing several slaves via multi-drop serial), it may be obtained using:

        with <client>:
            ...

    Note that such locks will *not* respond to any remaining transaction timeout!

    """
    def __init__( self, *args, **kwargs ):
        super( modbus_client_timeout, self ).__init__( *args, **kwargs )
        self._started	= None
        self._timeout	= None
        self._lock	= threading.Lock()

    @property
    def timeout( self ):
        """Returns the Defaults.Timeout, if no timeout = True|#.# (a hard timeout) has been specified."""
        if self._timeout in (None, True):
            logging.debug( "Transaction timeout default: %.3fs" % ( Defaults.Timeout ))
            return Defaults.Timeout
        now		= cpppo.timer()
        eta		= self._started + self._timeout
        if eta > now:
            logging.debug( "Transaction timeout remaining: %.3fs" % ( eta - now ))
            return eta - now
        logging.debug( "Transaction timeout expired" )
        return 0
    @timeout.setter
    def timeout( self, timeout ):
        """When a self.timeout = True|0|#.# is specified, initiate a hard timeout around the following
        transaction(s).  This means that any connect and/or read/write (_recv) must complete within
        the specified timeout (Defaults.Timeout, if 'True' or 0), starting *now*.  Reset to default
        behaviour with self.timeout = None.

        """
        if timeout is None:
            self._started = None
            self._timeout = None
        else:
            self._started = cpppo.timer()
            self._timeout = ( Defaults.Timeout
                              if ( timeout is True or timeout == 0 )
                              else timeout )

    def __enter__( self ):
        self._lock.acquire( True )
        return self

    def __exit__( self, typ, val, tbk ):
        self._lock.release()
        return False


class modbus_client_tcp( modbus_client_timeout, ModbusTcpClient ):

    def connect(self):
        """Duplicate the functionality of connect (handling optional .source_address attribute added
        in pymodbus 1.2.0), but pass the computed remaining timeout.

        """
        if self.socket: return True
        logging.debug( "Connecting to (%s, %s)", getattr( self, 'host', '(serial)' ), self.port )
        begun			= cpppo.timer()
        timeout			= self.timeout # This computes the remaining timeout available
        try:
            self.socket		= socket.create_connection( (self.host, self.port),
                                    timeout=timeout, source_address=getattr( self, 'source_address', None ))
        except socket.error as exc:
            logging.debug('Connection to (%s, %s) failed: %s' % (
                self.host, self.port, exc ))
            self.close()
        finally:
            logging.debug( "Connect completed in %.3fs" % ( cpppo.timer() - begun ))

        return self.socket != None

    def _recv( self, size ):
        """On a receive timeout, closes the socket and raises a ConnectionException.  Otherwise,
        returns the available input"""
        if not self.socket:
            raise ConnectionException( self.__str__() )
        begun			= cpppo.timer()
        timeout			= self.timeout # This computes the remaining timeout available
        logging.debug( "Receive begins  in %7.3f/%7.3fs", cpppo.timer() - begun, timeout )
        r,w,e			= select.select( [self.socket], [], [], timeout )
        if r:
            logging.debug( "Receive reading in %7.3f/%7.3fs", cpppo.timer() - begun, timeout )
            result		= super( modbus_client_timeout, self )._recv( size )
            logging.debug( "Receive success in %7.3f/%7.3fs", cpppo.timer() - begun, timeout )
            return result

        self.close()
        logging.debug( "Receive failure in %7.3f/%7.3fs", cpppo.timer() - begun, timeout )
        raise ConnectionException("Receive from (%s, %s) failed: Timeout" % (
                getattr( self, 'host', '(serial)' ), self.port ))

    def __repr__( self ):
        return "<%s: %s>" % ( self, self.socket.__repr__() if self.socket else "closed" )


class modbus_client_rtu( modbus_client_timeout, ModbusSerialClient ):
    """Implement semantically correct serial recv.

    TODO: force use of modbus_rtu_framer_collecting for method='rtu', while
    trying to retain the original (broken) 'method="..."' framer selection.

    """
    def __init__( self, method='ascii', framer=None,  **kwargs ):
        '''Initialize a serial client instance.  This is exceedingly gross, but we can't
        easily fix the ModbuSerialClient.__init__ (see BaseModubsClient in
        pymodbus/pymodbus/client/sync.py).  Let it run, then fix the self.framer
        later...  We know that self.transaction is OK, because framer isn't a
        ModbusSocketFramer.

        The methods to connect are::

          - ascii
          - rtu
          - binary

        '''
        # If a 'framer' is supplied, use it (and come up with a self.method name)
        super( modbus_client_rtu, self ).__init__( method=method, **kwargs )

        if framer is not None:
            assert not isinstance( self.framer, ModbusSocketFramer )
            assert not isinstance( framer, ModbusSocketFramer )
            self.method		= framer.__name__
            self.framer		= framer( ClientDecoder() )
            logging.debug( "Fixing ModbusSerialClient framer: %s",  self.method )
        

    def connect( self ):
        """Reconnect to the serial port, if we've been disconnected (eg. due to poll failure).  Since the
        connect will either immediately succeed or fail, we won't bother implementing a timeout.

        """
        if self.socket: return True
        logging.debug( "Connecting to (%s, %s)", getattr( self, 'host', '(serial)' ), self.port )
        connected		= super( modbus_client_rtu, self ).connect()
        logging.debug( "%r: inter-char timeout: %s", self,
                   self.socket.getInterCharTimeout() if self.socket else None )
        return connected

    def _recv( self, size ):
        """Replicate the approximate semantics of a socket recv; return what's available.  However,
        don't return Nothing (indicating an EOF).  So, wait for up to remaining 'self.timeout'
        for something to show up, but return immediately with whatever is there.

        We'll do it simply -- just read one at a time from the serial port.  We could find out how
        many bytes are available using the TIOCINQ ioctl, but this won't work on non-Posix systems.
        We can't just use the built-in Serial's read method and adjust its own _timeout to reflect
        our own remaining timeout -- we must only block 'til we have at least one character, and
        then continue reading 'til no more input is immediately available; there is no way to invoke
        Serial.read to indicate that.

        """
        if not self.socket:
            raise ConnectionException( self.__str__() )
        begun			= cpppo.timer()
        timeout			= self.timeout # This computes the remaining timeout available
        logging.debug( "Receive begins  in %7.3f/%7.3fs", cpppo.timer() - begun, timeout )
        
        read			= bytearray()
        remains			= timeout
        r,w,e			= select.select( [self.socket.fd], [], [], timeout )
        while r and len( read ) < size:
            # Still readable, and size not yet satisfied; get the next one
            buf			= os.read( self.socket.fd, 1 )
            if not buf:
                break # reports readable, but nothing there...  Disconnected hardware?  Report later.
            read.extend( buf )
            logging.debug( "Receive reading in %7.3f/%7.3fs; %d bytes", cpppo.timer() - begun, timeout,
                       len( read ))
            r,w,e		= select.select( [self.socket.fd], [], [], 0 ) # Something read! No more waiting

        if len( read ):
            logging.debug( "Receive success in %7.3f/%7.3fs; %d bytes", cpppo.timer() - begun, timeout,
                       len( read ))
            return bytes( read )

        # Nothing within timeout; potential client failure, disconnected hardware.  Force a re-open
        self.close()
        logging.debug( "Receive failure in %7.3f/%7.3fs", cpppo.timer() - begun, timeout )
        raise ConnectionException("Receive from (%s, %s) failed: Timeout" % (
                getattr( self, 'host', '(serial)' ), self.port ))
        
