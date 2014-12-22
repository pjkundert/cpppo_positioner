
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

__all__				= ["smc_lec_gen1"]

import logging
import struct

import cpppo
import serial

from .remote.pymodbus_fixes import modbus_client_rtu, modbus_rtu_framer_collecting
from .remote.plc_modbus import poller_modbus

PORT_MASTER			= '/dev/ttyS1'
PORT_STOPBITS			= 1
PORT_BYTESIZE			= 8
PORT_PARITY			= serial.PARITY_NONE
PORT_BAUDRATE			= 115200
PORT_TIMEOUT			= 1.5

POLL_RATE			= .25


# 
# 00000 - Y - Coils (I/O)
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
data.Y10_IN0			= {}
data.Y10_IN0.addr		= 00000 + 0x10
data.Y11_IN1			= {}
data.Y11_IN1.addr		= 00000 + 0x11
data.Y12_IN2			= {}
data.Y12_IN2.addr		= 00000 + 0x12
data.Y13_IN3			= {}
data.Y13_IN3.addr		= 00000 + 0x13
data.Y14_IN4			= {}
data.Y14_IN4.addr		= 00000 + 0x14
data.Y15_IN5			= {}
data.Y15_IN5.addr		= 00000 + 0x15

# When Read
# Displays the instruction state when in serial driving mode.
# (ON: 1, OFF: 0)
# When Write
# Gives instructions to controller.
# Only valid when in serial driving mode.
# (ON: 1, OFF: 0)
data.Y18_HOLD			= {}
data.Y18_HOLD.addr		= 00000 + 0x18
data.Y19_SVON			= {}
data.Y19_SVON.addr		= 00000 + 0x19
data.Y1A_DRIVE			= {}
data.Y1A_DRIVE.addr		= 00000 + 0x1a
data.Y1B_RESET			= {}
data.Y1B_RESET.addr		= 00000 + 0x1b
data.Y1C_SETUP			= {}
data.Y1C_SETUP.addr		= 00000 + 0x1c
# Move to -'ve direction by JOG operation. (1: move, 2: stop) 
data.Y1D_JOG_MINUS		= {}
data.Y1D_JOG_MINUS.addr		= 00000 + 0x1d
# Move to +'ve direction by JOG operation. (1: move, 2: stop) 
data.Y1E_JOG_PLUS		= {}
data.Y1E_JOG_PLUS.addr		= 00000 + 0x1e

# The driving input mode (parallel/ serial) is switched in Y30.
# 
# 0: Parallel input driving mode (parallel output end normal operation)
# 1: Serial input driving mode (parallel output end output prohibited) 
# 
# When Y30 is specified from 0 to 1, the parallel input state before the instruction is
# continued. Conversely, when Y30 is specified from 1 to 0, the state of the parallel input terminal
# is reflected immediately.
data.Y30_INPUT_INVALID		= {}
data.Y30_INPUT_INVALID.addr	= 00000 + 0x30


# X Discrete Inputs Internal Flags (status flags).  Read only.

# As internal processing of controller (regardless of parallel/ serial), ON when the functions on
# the left are output
data.X40_OUT0			= {}
data.X40_OUT0.addr		= 10001 + 0x40
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
data.X4F_ALARM.addr		= 10001 + 0x4f


# D Holding Registers The state of the electrical actuator (current location, etc.)
data.current_position		= {}		# 0.01mm
data.current_position.addr	= 40001 + 0x9000
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
data.in_position.addr		= 40001 + 0x9110
data.in_position.format		= 'i'


class smc_modbus( modbus_client_rtu ):
    """Drive a set of SMC actuators via direct Modbus/RTU protocol to the individual actuator
    processors.  

    """
    def __init__( self, address=PORT_MASTER, timeout=PORT_TIMEOUT, baudrate=PORT_BAUDRATE,
                  stopbits=PORT_STOPBITS, bytesize=PORT_BYTESIZE, parity=PORT_PARITY,
                  rate=POLL_RATE ):
        super( smc_modbus, self, ).__init__(
            framer=modbus_rtu_framer_collecting, port=address, stopbits=stopbits, bytesize=bytesize,
            parity=parity, baudrate=baudrate )

        self.pollers		= {} # {unit#: <poller_modbus>,}
        self.rate		= rate


    def unit( self, uid ):
        """Return the poller to access data for the given unit uid"""
        if uid not in self.pollers:
            self.pollers[uid]	= poller_modbus( "SMC actuator %s" % ( uid ), client=self,
                                                 unit=uid, rate=self.rate )
        return self.pollers[uid]
    

    def status( self, actuator=0 ):
        """Decode the raw position data, status and control indicators.  Will return None for any values not
        yet polled."""
        actuator		= self.unit( uid=actuator )
        result			= {}
        for k in super( cpppo.dotdict, data ).keys(): # Use dict key iteration, rather than dotdict full-depth keys
            addr		= data[k].addr
            format		= data[k].get( 'format' )
            values		= [ actuator.read( data[k].addr ) ]
            if format is None:
                # Simple data value (eg. Coil, Discrete, simple value)
                result[k]	= values[0]
                continue
            # A 'struct' format; get all necessary values from subsequent addresses
            assert addr >= 40001, "Must be a Holding Register address to support data format"
            while 2 * len( values ) < struct.calcsize( format ):
                addr	       += 1
                values.append( actuator.read( addr ))
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
        
        

    COMPLETE_LATENCY			= 0.1
    def complete( self, actuator=0, timeout=None ):
        """Ensure that any prior operation on the actuator is complete."""
        incomplete		= True
        begin			= cpppo.timer()

        actuator		= self.unit( uid=actuator )
        while not incomplete and timeout and cpppo.timer() < begin + timeout:
            incomplete		= actuator.read( data.X4B_INP.addr ) # returns 0/False when complete
            time.sleep( min( COMPLETE_LATENCY,
                             max( 0.0, begin + timeout - cpppo.timer() ))
                        if timeout
                        else COMPLETE_LATENCY )
        ( logging.warning if incomplete else logging.detail )(
            "Complete: actuator %3d %s: %r", actuator, "success" if complet else "failure",  kwds )


    def position( self, actuator=0, timeout=None, **kwds ):
        """Begin position operation on 'actuator' w/in 'timeout'. 

        Running with specified data

        1   - Set internal flag Y30 (input invalid flag)
        2   - Write 1 to internal flag Y19 (SVON)
        2a  -   and confirm internal flag X49 (SVRE) has become "1"
        3   - Write 1 to internal flag Y1C (SETUP)
        3a  -   and confirm internal flag X4A (SETON) has become "1"
        4   - Write data to D9102-D9110
        5   - Write Operation Start instruction "1" to D9100 (returns to 0 after processed)
        """
        logging.detail( "Position: actuator %3d started: %r", actuator, kwds )


