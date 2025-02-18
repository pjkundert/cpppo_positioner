
# 
# Cpppo_positioner -- Actuator position control
# 
# Copyright (c) 2014, Hard Consulting Corporation.
# 
# Cpppo_positioner is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.  See the COPYING file at the top of the source tree.
# 
# Cpppo_positioner is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
# 

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

__author__                      = "Perry Kundert"
__email__                       = "perry@hardconsulting.com"
__copyright__                   = "Copyright (c) 2014 Hard Consulting Corporation"
__license__                     = "Dual License: GPLv3 (or later) and Commercial (see LICENSE)"

__all__				= ["smc_modbus"]

import logging
import struct
import time

import cpppo
import serial
import tabulate

from cpppo.remote.pymodbus_fixes import modbus_client_rtu, Defaults
from cpppo.remote.plc_modbus import poller_modbus

#
# All the defaults supplied to smc_modbus().
# - Either modify these globals before invoking, or pass appropriate parameters
# 

PORT_MASTER			= 'ttyS0'  # eg. a symbolic link ttyS0 -> /dev/tty.usbserial-B0019I24
PORT_STOPBITS			= 1
PORT_BYTESIZE			= 8
PORT_PARITY			= serial.PARITY_NONE
PORT_BAUDRATE			= 38400
PORT_TIMEOUT			= 0.075		# RS-485 I/O timeout

POLL_RATE			= .5		# Nyquist Rate for 1Hz Updates


# 
# 00001 - Y - Coils (I/O)
# 10001 - X - Discrete Inputs
# 40001 - D - Holding Registers
# 
data				= cpppo.dotdict()

# Y Coils I/O Internal Flags (state change flags).  Read/write.
# 
# When Read
# Displays the instruction state when in serial driving mode.
# (ON: 1, OFF: 0)
# When Write
# Gives instructions to controller.
# Only valid when in serial driving mode.
# (ON: 1, OFF: 0)
# Coils are indexed from int('00001')
data.Y10_IN0			= {}
data.Y10_IN0.addr		= 1 + 0x10 # == 17
data.Y11_IN1			= {}
data.Y11_IN1.addr		= 1 + 0x11
data.Y12_IN2			= {}
data.Y12_IN2.addr		= 1 + 0x12
data.Y13_IN3			= {}
data.Y13_IN3.addr		= 1 + 0x13
data.Y14_IN4			= {}
data.Y14_IN4.addr		= 1 + 0x14
data.Y15_IN5			= {}
data.Y15_IN5.addr		= 1 + 0x15

# When Read
# Displays the instruction state when in serial driving mode.
# (ON: 1, OFF: 0)
# When Write
# Gives instructions to controller.
# Only valid when in serial driving mode.
# (ON: 1, OFF: 0)
data.Y18_HOLD			= {}
data.Y18_HOLD.addr		= 1 + 0x18
data.Y19_SVON			= {}
data.Y19_SVON.addr		= 1 + 0x19
data.Y1A_DRIVE			= {}
data.Y1A_DRIVE.addr		= 1 + 0x1a
data.Y1B_RESET			= {}
data.Y1B_RESET.addr		= 1 + 0x1b
data.Y1C_SETUP			= {}
data.Y1C_SETUP.addr		= 1 + 0x1c
# Move to -'ve direction by JOG operation. (1: move, 2: stop) 
data.Y1D_JOG_MINUS		= {}
data.Y1D_JOG_MINUS.addr		= 1 + 0x1d
# Move to +'ve direction by JOG operation. (1: move, 2: stop) 
data.Y1E_JOG_PLUS		= {}
data.Y1E_JOG_PLUS.addr		= 1 + 0x1e

# The driving input mode (parallel/ serial) is switched in Y30.
# 
# 0: Parallel input driving mode (parallel output end normal operation)
# 1: Serial input driving mode (parallel output end output prohibited) 
# 
# When Y30 is specified from 0 to 1, the parallel input state before the instruction is
# continued. Conversely, when Y30 is specified from 1 to 0, the state of the parallel input terminal
# is reflected immediately.
data.Y30_INPUT_INVALID		= {}
data.Y30_INPUT_INVALID.addr	= 1 + 0x30 # == 49 (round up to 0x3f == 64)


# X Discrete Inputs Internal Flags (status flags).  Read only.

# As internal processing of controller (regardless of parallel/ serial), ON when the functions on
# the left are output
data.X40_OUT0			= {}
data.X40_OUT0.addr		= 10001 + 0x40 # == 10065
data.X41_OUT1			= {}
data.X41_OUT1.addr		= 10001 + 0x41
data.X42_OUT2			= {}
data.X42_OUT2.addr		= 10001 + 0x42
data.X43_OUT3			= {}
data.X43_OUT3.addr		= 10001 + 0x43
data.X44_OUT4			= {}
data.X44_OUT4.addr		= 10001 + 0x44
data.X45_OUT5			= {}
data.X45_OUT5.addr		= 10001 + 0x45

# As internal processing of controller (regardless of parallel/ serial), ON when the functions on
# the left are output But unlike parallel I/O driving, ESTOP and ALARM signals have positive logic.
# 
# E-STOP: ON when EMG stops.
# ALARM: ON when alarm is generated. 
data.X48_BUSY			= {}
data.X48_BUSY.addr		= 10001 + 0x48
data.X49_SVRE			= {}
data.X49_SVRE.addr		= 10001 + 0x49
data.X4A_SETON			= {}
data.X4A_SETON.addr		= 10001 + 0x4a
data.X4B_INP			= {}
data.X4B_INP.addr		= 10001 + 0x4b
data.X4C_AREA			= {}
data.X4C_AREA.addr		= 10001 + 0x4c
data.X4D_WAREA			= {}
data.X4D_WAREA.addr		= 10001 + 0x4d
data.X4E_ESTOP			= {}
data.X4E_ESTOP.addr		= 10001 + 0x4e
data.X4F_ALARM			= {}
data.X4F_ALARM.addr		= 10001 + 0x4f # == 10080


# D Holding Registers The state of the electrical actuator (current location, etc.)
data.current_position		= {}		# 0.01mm
data.current_position.addr	= 40001 + 0x9000# == 76865 or 436865
data.current_position.format	= 'i'		# 32-bit signed integer
data.current_speed		= {}		# 
data.current_speed.addr		= 40001 + 0x9002
data.current_thrust		= {}
data.current_thrust.addr	= 40001 + 0x9003
data.target_position		= {}
data.target_position.addr	= 40001 + 0x9004
data.target_position.format	= 'i'
data.driving_data_no		= {}
data.driving_data_no.addr	= 40001 + 0x9006

# Running with specified data
# 1   - Set internal flag Y30 (input invalid flag)
# 2   - Write 1 to internal flag Y19 (SVON)
# 2a  -   and confirm internal flag X49 (SVRE) has become "1"
# 3   - Write 1 to internal flag Y1C (SETUP)
# 3a  -   and confirm internal flag X4A (SETON) has become "1"
# 4   - Write data to D9102-D9110
# 5   - Write Operation Start instruction "1" to D9100 (returns to 0 after processed)

data.operation_start		= {}		# 1: Starts operation according to 9102-9110
data.operation_start.addr	= 40001 + 0x9100
STEP_DATA_BEG		= 40001 + 0x9102# 0x9101 unused!
data.movement_mode		= {}		# 1: absolute, 2: relative
data.movement_mode.addr		= 40001 + 0x9102
data.speed			= {}		# 1-65535 mm/s
data.speed.addr			= 40001 + 0x9103
data.position			= {}		# +/-214783647 .01 mm
data.position.addr		= 40001 + 0x9104
data.position.format		= 'i'		# signed 32-bit integer
data.acceleration		= {}		# 1-65535 mm/s^2
data.acceleration.addr		= 40001 + 0x9106
data.deceleration		= {}		# 1-65535 mm/s^2
data.deceleration.addr		= 40001 + 0x9107
data.pushing_force		= {}		# 0-100 %
data.pushing_force.addr		= 40001 + 0x9108
data.trigger_level		= {}		# 0-100 %
data.trigger_level.addr		= 40001 + 0x9109
data.pushing_speed		= {}		# 1-65535 mm/s
data.pushing_speed.addr		= 40001 + 0x910a
data.moving_force		= {}		# 0-300 %
data.moving_force.addr		= 40001 + 0x910b
data.area_1			= {}		# +/-2147483647 0.01mm
data.area_1.addr		= 40001 + 0x910c
data.area_1.format		= 'i'
data.area_2			= {}		# +/-2147483647 0.01mm
data.area_2.addr		= 40001 + 0x910e
data.area_2.format		= 'i'
data.in_position		= {}		# 1-2147483647 0.01mm
data.in_position.addr		= 40001 + 0x9110# == 77137 or 437137
data.in_position.format		= 'i'		# == 77138 or 437138 (4 bytes, 2 words!)
STEP_DATA_END		= 40001 + 0x9111


class smc_modbus( modbus_client_rtu ):
    """Drive a set of SMC actuators via direct Modbus/RTU protocol to the individual actuator
    processors.  

    """
    TIMEOUT			= 5.0		# Positioning timeout (forever, if changed to None)

    def __init__( self, address=PORT_MASTER, timeout=PORT_TIMEOUT, baudrate=PORT_BAUDRATE,
                  stopbits=PORT_STOPBITS, bytesize=PORT_BYTESIZE, parity=PORT_PARITY,
                  rate=POLL_RATE ):
        Defaults.Timeout	= timeout	# RS-485 I/O timeout

        super( smc_modbus, self, ).__init__(
            port=address, stopbits=stopbits, bytesize=bytesize,
            parity=parity, baudrate=baudrate, timeout=timeout )

        self.pollers		= {} # {unit#: <poller_modbus>,}
        self.rate		= rate

    def close( self ):
        """Shut down all poller_modbus threads before closing serial port.  We might be getting
        fired from within one of the Threads, so don't sweat a join failure"""
        for uid,poller in self.pollers.items():
            poller.done		= True
        for uid,poller in self.pollers.items():
            try:
                poller.join( timeout=1 )
            except RuntimeError:
                pass
        super( smc_modbus, self ).close()

    __del__			= close

    def __repr__( self ):
        row			= {}
        for uid,unit in self.pollers.items():
            row.setdefault( '', [] ).append( unit.description )
            for k,v in self.status( actuator=uid ).items():
                row.setdefault( k, [] ).append( v )
        out			= []
        for label in sorted( row ):
            out.append( "%20s: %s" % ( label, ''.join( "%8s" % ( col ) for col in row[label] )))
        return "SMC Modbus/RTU Gateway" + ( ":\n" if out else "" ) + "\n".join( out )

    def unit( self, uid ):
        """Return the poller to access data for the given unit uid."""
        if uid not in self.pollers:
            self.pollers[uid]	= poller_modbus( "SMC %s" % ( uid ), client=self,
                                                 multi=True, unit=uid, rate=self.rate )
        return self.pollers[uid]
    
    def status( self, actuator=1 ):
        """Decode the raw position data, status and control indicators, returning all status values as a
        dictionary.  Will return None for any values not yet polled (or when communications fails).

        """
        unit			= self.unit( uid=actuator )
        result			= {}

        # Roughly equivalent to dict key iteration, rather than dotdict full-depth keys            
        for k in data.iterkeys( depth=0 ):
            addr		= data[k].addr
            format		= data[k].get( 'format' )
            values		= [ unit.read( data[k].addr ) ]
            if format is None:
                # Simple data value (eg. Coil, Discrete, simple value)
                result[k]	= values[0]
                continue
            # A 'struct' format; get all necessary values from subsequent addresses
            assert 40001 <= addr <= 100000 or 400001 <= addr, "Must be a Holding Register address to support data format"
            while 2 * len( values ) < struct.calcsize( format ):
                addr	       += 1
                values.append( unit.read( addr ))
            if any( v is None for v in values ):
                result[k]	= None
                continue

            # Got all required values.  Decode each host-ordered 16-bit register into l, and then 
            # encode in desired format.  Here's an example:
            # 
            # Sent: Read position data (D9000)
            #     01 03 90 00 00 02 E9 0B
            # Reply:
            #     01 03 04 00 00 3A 98 E9 39
            # 3A98h = 15000 --> 150.00mm

            # So, output each 16-bit register in big-endian order (assumes biggest end of target
            # format comes in first register), and then unpack big-endian buffer into target format.
            buffer		= b''.join( struct.pack( '>H', v ) for v in values )
            result[k]		= struct.unpack( '>'+format, buffer )[0]

        return result

    def check( self, predicate, deadline=None ):
        """Check if 'predicate' comes True before 'deadline', every self.rate seconds"""
        done			= predicate()
        start			= cpppo.timer()
        while not done and ( deadline is None or cpppo.timer() < deadline ):
            time.sleep( self.rate if deadline is None
                        else min( self.rate, max( 0, deadline - cpppo.timer() )))
            if logging.getLogger().isEnabledFor( logging.INFO ):
                logging.info( "After {dur:7.2f}s of {ded}:\n{tab}".format(
                    dur		= cpppo.timer() - start,
                    ded		= None if not deadline else round( deadline - start, 2 ),
                    tab		= tabulate.tabulate( self.status().items(), headers=["I/O", "Value"], tablefmt='orgtbl' )
                ))
            done		= predicate()
        return done

    def outputs( self, actuator, *flags ):
        """Set one or more 'flag' matching 'NAME' (or clear it, if all lower case 'name' used).  Only
        Y... (Coils) may be written.  The available flags are:
        
            IN[0-5]
            HOLD
            SVON
            DRIVE
            RESET
            SETUP
            JOG_MINUS
            JOG_PLUS
            INPUT_INVALID

        """
        unit			= self.unit( uid=actuator )
        for f in flags:
            NAM			= f.upper()
            nam			= f.lower()
            key			= [ k for k in data.iterkeys( depth=0 )
                                    if k.startswith( 'Y' ) and k.endswith( NAM ) ]
            assert len( key ) == 1 and f in (NAM,nam), "invalid/ambiguous key name %s: %r" % ( f, key )
            val			= bool( f == NAM )
            logging.detail( "%s/%-8s <== %s", unit.description, f, val )
            unit.write( data[key[0]].addr, val )
        return self.status( actuator=actuator )

    def complete( self, actuator=1, svoff=False, timeout=None ):
        """Ensure that any prior operation on the actuator is complete w/in timeout; return True iff the
        current operation is detected as being complete.

        According to the documentation, the absence of the X4B "INP" flag should indicate
        completion, (see LEC Modbus RTU op Manual.pdf, section 4.4).  However, this does not work,
        and the X48 "BUSY" flag seems to serve this purpose; perhaps it is a documentation error.
    
        If 'svoff' is True, we'll also turn off the servo (clear Y19_SVON) if we detect completion.

        """
        begin			= cpppo.timer()
        if timeout is None:
            timeout		= self.TIMEOUT
        unit			= self.unit( uid=actuator )
        # Loop on True/None; terminate only on False; X48_BUSY contains 0/False when complete
        complete		= self.check(
            predicate=lambda: unit.read( data.X48_BUSY.addr ) == False,
            deadline=None if timeout is None else begin + timeout )
        ( logging.warning if not complete else logging.detail )(
            "Complete: actuator %3d %s", actuator, "success" if complete else "failure" )
        if svoff and complete:
            logging.detail( "ServoOff: actuator %3d", actuator )
            unit.write( data.Y19_SVON.addr, 0 )
        return complete

    def position( self, actuator=1, timeout=TIMEOUT, home=True, noop=False, svoff=False, **kwds ):
        """Begin position operation on 'actuator' w/in 'timeout'.  

        :param home: Return to home position before any other movement
        :param noop: Do not perform final activation

        Running with specified data

        1   - Set internal flag Y30 (input invalid flag)
        2   - Write 1 to internal flag Y19 (SVON)
        2a  -   and confirm internal flag X49 (SVRE) has become "1"
        3   - Write 1 to internal flag Y1C (SETUP)
        3a  -   and confirm internal flag X4A (SETON) has become "1"
        4   - Write data to D9102-D9110
        5   - Write Operation Start instruction "1" to D9100 (returns to 0 after processed)

        If no positioning kwds are provided, then no new position is configured.  If 'noop' is True,
        everything except the final activation is performed.

        """
        begin			= cpppo.timer()
        if timeout is None:
            timeout		= self.TIMEOUT
        assert self.complete( actuator=actuator, svoff=svoff, timeout=timeout ), \
            "Previous actuator position incomplete within timeout %r" % timeout
        status			= self.status( actuator=actuator )
        if not kwds:
            return status

        # Previous positioning complete, and possibly new position keywords provided.
        logging.detail( "Position: actuator %3d setdata: %r", actuator, kwds )
        unit			= self.unit( uid=actuator )

        # 1: set INPUT_INVALID; enabled operating instructions by serial communication
        unit.write( data.Y30_INPUT_INVALID.addr, 1 )

        # 2: set SVON (servo on), check SVRE
        if timeout:
            assert cpppo.timer() <= begin + timeout, \
                "Failed to complete positioning SVON/SVRE within timeout"
        unit.write( data.Y19_SVON.addr, 1 )
        svre			= self.check(
            predicate=lambda: unit.read( data.Y19_SVON.addr ) and unit.read( data.X49_SVRE.addr ),
            deadline=None if timeout is None else begin + timeout )
        assert svre, \
            "Failed to set SVON True and read SVRE True"

        # 3: Return to home? set SETUP, check SETON.  Otherwise, clear SETUP.  It is very unclear
        #    whether we need to do this, and/or whether we need to clear it afterwards.
        if home:
            if timeout:
                assert cpppo.timer() <= begin + timeout, \
                    "Failed to complete positioning SETUP/SETON within timeout"
            unit.write( data.Y1C_SETUP.addr, 1 )
            seton			= self.check(
                predicate=lambda: unit.read( data.Y1C_SETUP.addr ) and unit.read( data.X4A_SETON.addr ),
                deadline=None if timeout is None else begin + timeout )
            if not seton:
                logging.warning( "Failed to set SETUP True and read SETON True" )
            # assert seton, \
            #    "Failed to set SETUP True and read SETON True"
        else:
            unit.write( data.Y1C_SETUP.addr, 0 )
        
        # 4: Write any changed position data.  The actuator doesn't accept individual register
        # writes, so we use multiple register writes for each value.
        for k,v in kwds.items():
            assert k in data, \
                "Unrecognized positioning keyword: %s == %r" % ( k, v )
            assert STEP_DATA_BEG <= data[k].addr <= STEP_DATA_END, \
                "Invalid positioning keyword: %s == %r; not within position data address range" % ( k, v )
            format		= data[k].get( 'format' )
            if format:
                # Create a big-endian buffer.  This will be some multiple of register size.  Then,
                # unpack it into some number of 16-bit big-endian registers (this will be a tuple).
                buf		= struct.pack( '>'+format, v )
                values		= [ struct.unpack_from( '>H', buf[o:] )[0] for o in range( 0, len( buf ), 2 ) ]
            else:
                values		= [ v ]
            if timeout:
                assert cpppo.timer() <= begin + timeout, \
                    "Failed to complete positioning data update within timeout"
            logging.normal( "Position: actuator %3d updated: %16s: %8s (== %s)", actuator, k, v, values )
            unit.write( data[k].addr, values )

        # 5: set operation_start to 0x0100 (1 in high-order bytes) unless 'noop'
        # - returns to 0 after operation starts (see 10.2 Running with specified data)
        if not noop:
            unit.write( data.operation_start.addr, 0x0100 )
            unit.forget( data.operation_start.addr )  # Ensure we check freshly polled data
            started			= self.check(
                predicate=lambda: unit.read( data.operation_start.addr ) == 0x0000,
                deadline=None if timeout is None else begin + timeout )
            assert started, \
                "Failed to detect positioning start within timeout"

        return self.status( actuator=actuator )
