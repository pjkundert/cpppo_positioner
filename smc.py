
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

try:
    from future_builtins import zip
except ImportError:
    pass		# Already there in Python 3

import cpppo
from cpppo.server.enip import client



class smc_lec_gen1( client.connector ):
    """Drive an SMC actuator via the SMC LEC-GEN1 gateway's actuator data state-machine.

    """
    IN				= '@0x1FF/1/1'
    OUT				= '@0x1FF/1/2'
    def __init__( self, config=None, **kwds ):
        begun			= cpppo.timer()
        super( smc_lec_gen1, self ).__init__( **kwds )
        logging.normal( "SMC LEC-GEN1 Gateway connection in %7.3fs", cpppo.timer() - begun )

        if config is None:
            config		= {}
        self.IN_path		= client.parse_path( config.pop( 'in',  self.IN ))
        self.OUT_path		= client.parse_path( config.pop( 'out', self.OUT ))
        self.depth		= int(   config.pop( 'depth',    1     ))
        self.multiple		= bool(  config.pop( 'multiple', False ))
        self.timeout		= float( config.pop( 'timeout',  5.0   ))
        self.latency		= float( config.pop( 'latency',  0.1   ))
        assert not config, \
            "Unknown config parameters: %r" % ( config )

        # Actuators are numbered from 1-12.  We will contain both the status (from IN) and control
        # (to OUT) data in the same dict; self.actuator[1] = {...}.  These always reflect ground
        # truth -- the contents of the IN and OUT arrays.
        self.actuator		= dict([ (act,{}) for act in range( 1,12+1 ) ])
        self.status		= {} #  IN[250-253]
        self.control		= {} # OUT[250-253]

        # Read the IN/OUT attribute, decode them into .actuator, status and control (reporting
        # changes), to ensure the Gateway I/O looks OK.
        self.operate()
        logging.normal( "SMC LEC-GEN1 Gateway up-to-date in %7.3fs", cpppo.timer() - begun )

    def decode( self, IN, OUT ):
        """Decode the raw IN/OUT data, updating the self.actuator, status and control indicators."""
        pass

    def operate( self, operations=None ):
        """Perform the specified I/O operations and then read all Gateway actuator IN and OUT data,
        ensuring that the raw data is OK."""
        if operations is None:
            operations		= []
            
        operations.extend(
            client.parse_operations([
                client.format_path( self.IN_path  ) + "[0-255]",
                client.format_path( self.OUT_path ) + "[0-255]" ]))

        results			= []
        with self:
            for idx,dsc,req,rpy,sts,val in self.pipeline( operations=operations, depth=self.depth ):
                if sts:
                    # We can either check 'sts' (non-zero indicates some kind of error status), or we
                    # can check 'val' (non-Truthy indicates an unsuccessful response).  However, since a
                    # Read/Write Tag Fragmented can return a *partial* response (status code 0x06, with
                    # valid -- but partial -- Truthy data), and we don't want to ever see those, we'll
                    # check 'sts'.  If it is a non-zero status code (eg. 0x06, 0xFF) OR a status +
                    # extended status tuple (eg (0xFF, [0x2107]) ), it'll appear Truthy on failure.
                    raise Exception( "Failed operation %r, status: %s; request: %r" % ( dsc, sts, req ))
                results.append( val )
        
        OUT			= results.pop( -1 )
        logging.detail( "OUT[%3s]: %r", len( OUT ) if hasattr( OUT, '__len__' ) else '?', OUT )
        assert OUT and hasattr( OUT, '__len__' ) and len( OUT ) == 256, \
            "Failed to retrieve OUT: %s Attribute: %s" % ( client.format_path( OUT_path ), OUT )
        IN			= results.pop( -1 )
        logging.detail( " IN[%3s]: %r", len( IN  ) if hasattr( IN,  '__len__' ) else '?', IN )
        assert IN  and hasattr( IN,  '__len__' ) and len( IN  ) == 256, \
            "Failed to retrieve  IN: %s Attribute: %s" % ( client.format_path( IN_path ), IN )
        
        self.decode( IN=IN, OUT=OUT )
        return results
        
        

    def complete( self, actuator=0, timeout=None ):
        """Ensure that any prior operation on the actuator is complete."""
        pass # TODO: Implement completion detection state machine

    def position( self, actuator=0, timeout=None, **kwds ):
        logging.detail( "Position: actuator %3d: %r", actuator, kwds )
        begin			= cpppo.timer()
        self.complete( actuator=actuator, timeout=timeout )

        pass # TODO: Implement positioning state machine

