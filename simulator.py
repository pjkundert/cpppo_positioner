
# 
# Cpppo_positioner -- Actuator position control via EtherNet/IP
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

# 
# cpppo_positioner.simulator
# 
#     Intercept all EtherNet/IP CIP Attribute I/O, attempting to update the IN and OUT tables to
# reflect the status of a number of simulated SMC positioning actuators.  Specify the number of
# actuators to simulate.
# 
#     python -m cpppo_positioner.simulator 3
# 

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

__author__                      = "Perry Kundert"
__email__                       = "perry@hardconsulting.com"
__copyright__                   = "Copyright (c) 2014 Hard Consulting Corporation"
__license__                     = "GPLv3 (or later)"

import logging
import struct
import sys
import threading
import time

try:
    import reprlib
except:
    import repr as reprlib

import cpppo
from cpppo import history
from cpppo.server.enip import (device, parser, logix, client)
from cpppo.server.enip.main import main


# Globals (parsed from argument list) accessed by classes
gateway_actuator_count		= 3

# TODO: We don't know at this point what Class ID and Instance ID the SMC Gateway's IN and OUT
# Attributes need to be at...  Find out.
gateway_class_id		= 0x1FF # random
gateway_instance_id		= 1
gateway_attribute_id		= {}
gateway_attribute_id['IN']	= 1
gateway_attribute_id['OUT']	= 2
gateway_attribute_size		= 256
gateway				= None


class simulation( threading.Thread ):

    INITIAL			= 0
    UNUSED			= 1

    statename			= {			# Define additional states in derived class
        INITIAL:	"INITIAL",
    }
    statelogger			= {
        INITIAL:		logging.NORMAL,
    }

    def __init__( self, granularity=0.01, **kwds ):
        # Simulation state data
        self.lock		= threading.Lock()
        self.granularity	= granularity		# Run simulation w/ ~100th second granularity
        self._clock		= cpppo.timer()		# Advancing simulation time
        self._state_entered	= self._clock
        self._state		= self.INITIAL
        self.done		= False
        super( simulation, self ).__init__( **kwds )

    def join( self, timeout=None ):
        self.done		= True
        super( simulation, self ).join( timeout=timeout )

    # state
    # state = <new-state> [,<message>]
    # 
    # Report the current state, or change the state (w/ optional log message).  Reports the state
    # change according to the logging levels in self.statelogger for either <new-state> or (<cur-state>,<new-state>)
    @property
    def state( self ):
        return self._state
    @state.setter
    def state( self, value ):
        if type( value ) in (list,tuple):
            value,msg		= value
        else:
            msg			= None
        if self._state != value:
            # Find the right logger, by (<from>,<into>), then just <into>
            lev			= self.statelogger.get( (self._state,value) )
            if lev is None:
                lev		= self.statelogger.get( value )
            if logging.getLogger().isEnabledFor( lev ):
                logging.log( lev, "%s %-10s -> %-10s%s",
                              self, self.statename[self._state], self.statename[value],
                              ': ' + str( msg ) if msg is not None else '' )
            self._state		= value
            self._state_entered	= cpppo.timer()

    @property
    def current( self ):
        """ """
        now			= cpppo.timer()
        dur			= now - self._state_entered
        dt			= now - self._clock
        return self.state,dur,dt,now

    def advance( self ):
        """Override to implement specific simulator.  After processing and state changes, returns the
        current state and its duration, this simulation quantum's dt, and the newly advanced time.

        """
        state,dur,dt,self._clock= self.current
        return state,dur,dt,self._clock

    def run( self ):
        while not self.done:
            state,dur,dt,now	= self.current
            if dt < self.granularity:
                time.sleep( self.granularity - dt )
                continue
            # We have a dt (delta-t) >= granularity; advance simulation
            with self.lock:
                self.advance()


class smc_actuator( simulation ):

    INITIAL			= 0
    IDLE			= 1

    statename			= {
        INITIAL:	"INITIAL",
        IDLE:		"IDLE",
    }
    statelogger			= {
        INITIAL:		logging.NORMAL,
        IDLE:			logging.NORMAL,
        (INITIAL,IDLE):		logging.WARNING,
    }

    def __init__( self, **kwds ):
        # Actuator state data
        # bit masks                             offset
        self.out0		= False		#     0
        self.out1		= False
        self.out2		= False
        self.out3		= False
        self.out4		= False
        self.out5		= False

        self.busy		= False		#     1
        self.svre		= False
        self.seton		= False
        self.inp		= False
        self.area		= False
        self.warea		= False
        self.estop		= False
        self.alarm		= False

        # multi-byte data in big-endian order    offset bytes  range          units
        self.current_position	= 0		#     2     4  +/-2147483647  .01mm
        self.current_speed	= 0		#     6     2  0 to 65500     mm/s
        self.current_force	= 0		#     8     2  0 to 300       %
        self.target_position	= 0		#    10     4  +/-2147483647  .01mm
        self.alarm_values	= 0		#    14     4  4 x 0 to 255

        self.connect_station	= False
        self.abnormal_station	= False
        self.sending_completed	= False
        self.sending		= False

        # Simulation state data
        self.lock		= threading.Lock()
        self.granularity	= 0.01		# Run simulation w/ ~100th second granularity
        self._clock		= cpppo.timer()	# Advancing simulation time
        self._state_entered	= self._clock
        self._state		= self.INITIAL

        super( smc_actuator, self ).__init__( **kwds )


    def advance( self ):
        state,dur,dt,now	= self.current
        if state == self.INITIAL:
            self.current_speed	= 0
            self.current_force	= 0
            self.out0		= False
            self.out1		= False
            self.out2		= False
            self.out3		= False
            self.out4		= False
            self.out5		= False
            self.busy		= False
            self.svre		= False
            self.seton		= False
            self.inp		= False
            self.area		= False
            self.estop		= False
            self.alarm		= False
            self.connect_station=False
            self.abnormal_station=False
            self.sending_completed=False
            self.sending	= False
            if dur < .1:
                return
            self.state		= self.IDLE, "Initialization complete"

        if state == self.IDLE:
            self.connect_station=True
            self.abnormal_station=False
            self.sending_completed=False
            self.sending	= False

        return super( smc_actuator, self ).advance()

    def encode( self ):
        """Encode the present state (produce the 20 Gateway IN array elements), representing all of the
        actuator's current data, and the gateway Controller IF flags.

        """
        with self.lock:
            result		= b''
            result	       += struct.pack( '>B',				# one byte unsigned
                                                 0 
                                                 | 0 if not self.out0 else 1 << 0
                                                 | 0 if not self.out1 else 1 << 1
                                                 | 0 if not self.out2 else 1 << 2
                                                 | 0 if not self.out3 else 1 << 3
                                                 | 0 if not self.out4 else 1 << 4
                                                 | 0 if not self.out4 else 1 << 5 )
            result	       += struct.pack( '>B',
                                                 0
                                                 | 0 if not self.busy  else 1 << 0
                                                 | 0 if not self.svre  else 1 << 1
                                                 | 0 if not self.seton else 1 << 2
                                                 | 0 if not self.inp   else 1 << 3
                                                 | 0 if not self.area  else 1 << 4
                                                 | 0 if not self.warea else 1 << 5
                                                 | 0 if not self.estop else 1 << 6
                                                 | 0 if not self.alarm else 1 << 7 )
            result	       += struct.pack( '>i', self.current_position )	# big-endian signed 32-bit int
            result	       += struct.pack( '>H', self.current_speed )	# big-endian unsigned 16-bit int
            result	       += struct.pack( '>H', self.current_force )	# big-endian unsigned 16-bit int
            result	       += struct.pack( '>i', self.target_position )	# big-endian signed 32-bit int
            result	       += struct.pack( '>i', self.alarm_values	)	# big-endian signed 32-bit int
            result	       += struct.pack( '>B',
                                                 0
                                                 | 0 if not self.connect_station   else 1 << 0
                                                 | 0 if not self.abnormal_station  else 1 << 1 )
            result	       += struct.pack( '>B',
                                                 0
                                               | 0 if not self.sending_completed else 1 << 0
                                               | 0 if not self.sending           else 1 << 1 )
        assert len( result ) == 20
        return result


class smc_gateway( simulation ):
    """Start up the SMC Gateway simulator, and the specified number of positioning actuator
    simulators.

    """
    lock			= threading.Lock()

    IN				= simulation.UNUSED + 0
    OUT				= simulation.UNUSED + 1
    UNUSED			= simulation.UNUSED + 2

    def __init__( self, **kwds ):
        self._in		= [0] * 256
        self._out		= [0] * 256
        self.actuators		= []

        logging.warning( "Simulating %d SMC Positioning Actuators", gateway_actuator_count )
        while len( self.actuators ) < gateway_actuator_count:
            a                       = smc_actuator()
            a.daemon                = True
            a.start()
            self.actuators.append( a )
        super( smc_gateway, self ).__init__( **kwds )

    def join( self, timeout=None ):
        super( smc_gateway, self ).join( timeout=timeout )
        for a in self.actuators:
            a.join( timeout=timeout )

    def advance( self ):
        """Either update the next controller into the IN, or send an output from OUT to a controller.
        This simulates serial I/O via the RS-485 multi-drop Modbus link used to communicate with the
        1 to 12 SMC actuator motor controllers.

        As we cycle through reading actuator into the IN array, we check for any actuators in the
        OUT array that have signalled that they have data ready to send (OUT[3] == 1), but are not
        either sending (IN[19.1]) or sending_completed (IN[19.0]).

        """
        return super( smc_gateway, self ).advance()

    def _key_range( self, key ):
        if isinstance( key, slice ):
            beg,end,str		= key.indices( gateway_attribute_size )
            assert str == 1, "Unsupported slice stride: %d" % ( str )
        else:
            assert isinstance( key, int ), "Attempt to index with a non-int: %r" % key
            beg,end		= key,key+1
        return beg, end

    @cpppo.mutexmethod( 'lock' )
    def I_O__getitem__( self, key, which, data ):
        """Handle reading of either IN or OUT array; just return the current raw data. """
        beg,end			= self._key_range( key )
        if isinstance( key, slice ):
            val			= data[beg:end]
            logging.normal( "%3s[%3d-%-3d]  == %r", which, beg, end-1, reprlib.repr( val ))
            assert len( val ) == end - beg, "Incorrect result length: %d/%d" % ( len( val ), end - beg )
        else:
            val			= data[beg]
            logging.normal( "%3s[  %3d  ]  == %r", which, beg, reprlib.repr( val ))
            assert end-beg == 1, "Non-slice indexing resulted in multiple (%d) values" % ( end-beg )
        return val

    def IN__len__( self ):
        return gateway_attribute_size
    def IN__repr__( self ):
        return self.__class__.__name__ + ' IN  Attribute'
    def IN__getitem__( self, key ):
        return self.I_O__getitem__( key, 'IN', self._in )
    def IN__setitem__( self, key, val ):
        raise Exception( "Rejected attempt to write to the IN array; read-only" )

    def OUT__len__( self ):
        return gateway_attribute_size
    def OUT__repr__( self ):
        return self.__class__.__name__ + ' OUT Attribute'
    def OUT__getitem__( self, key ):
        return self.I_O__getitem__( key, 'OUT', self._out )
    @cpppo.mutexmethod( 'lock' )
    def OUT__setitem__( self, key, val ):
        assert isinstance( key, slice )
        beg,end			= self._key_range( key )

        logging.normal( "OUT[%3d-%-3d]  <= %r", beg, end-1, reprlib.repr( val ))

        # Writing to one of the 12 actuators?  Actuators numbered 1-12
        act			= beg // 20 + 1
        if 1 <= act <= 12:
            # Validate OUT Actuator writes
            assert (end-1) // 20 + 1 == act, \
                "Attempt to write outside Actuator %2d's space %d-%d" % (
                    act, (act-1)*20, (act-1)*20+19 )
        else:
            # Validate OUT Gateway unit control flags
            assert 250 <= beg <= 253 and 250 <= (end-1) <= 253, \
                "Attempt to write outside Gateway flag space 250-253"
            pass
        self._out[key]		= val
        
    def interface( self, which ):
        """Return a class that implements the interface required by a cpppo.server.enip.device Attribute,
        which vectors any I/O requests along to this instance.  Accepts the 'IN' or 'OUT'
        designator, and constructs a custom class instance with bound method targetting the
        appropriate local instance methods.

        """
        class forward( object ):
            __len__		= getattr( self, which + '__len__'  )
            __repr__		= getattr( self, which + '__repr__' )
            __getitem__		= getattr( self, which + '__getitem__' )
            __setitem__		= getattr( self, which + '__setitem__' )
        return forward()

# 
# Attribute_positioner -- intercept all EtherNet/IP Attribute I/O, and simulator actuators
# 
class Attribute_positioner( device.Attribute ):
    """
    Recognizes the tags IN (reading) and OUT (writing) only.  Supplies a 'default' of the 
    """
    def __init__( self, *args, **kwds ):

        with smc_gateway.lock:
            global gateway
            if gateway is None:
                gateway		= smc_gateway()
                gateway.daemon	= True
                gateway.start()

        # We haven't set up the Attribute yet (no self.name...); pick off the supplied name from the
        # first positional arg, from from the kwds['name']...
        name			= args[0] if args else kwds['name']
        assert name in ('IN','OUT'), \
            "Invalid tag names; only 'IN=SINT[256]' and 'OUT=SINT[256]' accepted"

        gateway_interface	= gateway.interface( name )
        logging.normal( "Connecting %3s Attribute I/O to SMC Gateway %s", name, gateway_interface )
        kwds['default']		= gateway_interface

        super( Attribute_positioner, self ).__init__( *args, **kwds )

        assert len( self ) == gateway_attribute_size \
            and isinstance( self.parser, parser.SINT ), \
            "Invalid tag size/type; only 'IN=SINT[256]' and 'OUT=SINT[256]' accepted"

        # Put ourself into the SMC Gateway Object at a specific Class, Instance and Atribute ID.
        assert not device.resolve_tag( self.name ), "The %s tag already exists" % self.name
        instance		= device.lookup( gateway_class_id, gateway_instance_id )
        assert instance, "SMC Gateway Object Instance not found"
        assert str( gateway_attribute_id[self.name] ) not in instance.attribute, \
            "SMC Gateway already has an attribute %s" % gateway_attribute_id[self.name]
        instance.attribute[str( gateway_attribute_id[self.name] )] = self
        device.redirect_tag( self.name, {
            'class':		gateway_class_id, 
            'instance': 	gateway_instance_id,
            'attribute':	gateway_attribute_id[self.name] })

        cls,ins,atr		= device.resolve_tag( self.name )
        logging.normal( "SMC Gateway Tag %-3s: Class %5d/0x%04x, Instance %3d, Attribute %5r",
                        self.name, cls, cls, ins, atr )

    def __getitem__( self, key ):
        try:
            value		= super( Attribute_positioner, self ).__getitem__( key )
            logging.info( "PLC I/O Read  Tag %20s[%5s-%-5s]: %s", self.name,
                          key.indices( len( self ))[0]   if isinstance( key, slice ) else key,
                          key.indices( len( self ))[1]-1 if isinstance( key, slice ) else key )
            return value
        except Exception as exc:
            logging.warning( "PLC I/O Read  Tag %20s[%5s-%-5s] Exception: %s", self.name,
                             key.indices( len( self ))[0]   if isinstance( key, slice ) else key,
                             key.indices( len( self ))[1]-1 if isinstance( key, slice ) else key,
                             exc )
            raise

    def __setitem__( self, key, value ):
        try:
            super( Attribute_positioner, self ).__setitem__( key, value )
            logging.info( "PLC I/O Write Tag %20s[%5s-%-5s]: %s", self.name,
                          key.indices( len( self ))[0]   if isinstance( key, slice ) else key,
                          key.indices( len( self ))[1]-1 if isinstance( key, slice ) else key )
            
        except Exception as exc:
            logging.warning( "PLC I/O Write Tag %20s[%5s-%-5s] Exception: %s", self.name,
                             key.indices( len( self ))[0]   if isinstance( key, slice ) else key,
                             key.indices( len( self ))[1]-1 if isinstance( key, slice ) else key,
                             exc )
            raise

if __name__ == "__main__": 

    # Some initial setup before the main loop; no logging set up yet...

    # Find the SMC Simulator related arguments, and pull them out of the sys.argv list
    if  len( sys.argv ) > 1 and sys.argv[1].isdigit():
        gateway_actuator_count	= int( sys.argv.pop( 1 ))
    elif '--actuators' in sys.argv:
        i			= sys.argv.index( '--actuators' )
        sys.argv.pop( i )
        gateway_actuator_count	= int( sys.argv.pop( i ))

    # Check for the IN= and OUT= attributes, and pull off any trailing @... designating the Class,
    # Instance and Attribute IDs of these Attributes.
    for att in gateway_attribute_id:
        tag			= None
        for arg in range( 1, len( sys.argv )):
            if sys.argv[arg].startswith( att + '=' ):
                tag		= sys.argv[arg]
                if '@' not in tag:
                    continue
                tag,ids		= tag.split( '@', 1 )
                sys.argv[arg]	= tag
                path		= client.parse_path( '@'+ids )
                assert len( path ) == 3 \
                    and 'class' in path[0] and 'instance' in path[1] and 'attribute' in path[2], \
                    "Tag %r CIP path %r must specify Class, Instance and Attribute ID" % (
                        tag, '@'+ids )
                if gateway_class_id != path[0]['class']:
                    gateway_class_id = path[0]['class']
                if gateway_instance_id != path[1]['instance']:
                    gateway_instance_id = path[1]['instance']
                if gateway_attribute_id[att] != path[2]['attribute']:
                    gateway_attribute_id[att] = path[2]['attribute']
        if tag is None:
            # The IN/OUT Attribute not specified; simulate it at the default size
            sys.argv.append( "%s=SINT[%d]" % ( att, gateway_attribute_size ))

    # Now that we have the SMC Gateway's CIP Class, Instance and Attribute IDs, create it
    class SMC_Gateway_Object( logix.Logix ):
        """An object that responds to Logix (Read/Write Tag [Fragmented]) requests."""
        class_id			= gateway_class_id

    SMC_Gateway_Object( name="SMC Gateway", instance_id=gateway_instance_id )

    sys.exit( main( attribute_class=Attribute_positioner ))
