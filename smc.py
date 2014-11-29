
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

__author__                      = "Perry Kundert"
__email__                       = "perry@hardconsulting.com"
__copyright__                   = "Copyright (c) 2014 Hard Consulting Corporation"
__license__                     = "GPLv3 (or later)"

__all__				= ["smc_lec_gen1"]

import logging

import cpppo
from cpppo.server.enip import client
        
class smc_lec_gen1( client.connector ):
    """Drive an SMC actuator via the SMC LEC-GEN1 gateway's actuator data state-machine.

    """
    def __init__( self, config=None, **kwds ):
        super( smc_lec_gen1, self ).__init__( **kwds )
        if config is None:
            config		= {}
        self.path_in		= client.parse_path( config.pop( 'in',  '@0x1FF/1/1' ))
        self.path_out		= client.parse_path( config.pop( 'out', '@0x1FF/1/2' ))
        self.depth		= int(   config.pop( 'depth',    1     ))
        self.multiple		= bool(  config.pop( 'multiple', False ))
        self.timeout		= float( config.pop( 'timeout',  1.0   ))

        # Read the IN and OUT attributes, and ensure the Gateway looks OK
        self.IN,self.OUT	= None,None
        try:
            self.IN,self.OUT	= ( val
                                    for idx,dsc,req,rpy,sts,val in
                                    self.pipeline(
                                        operations=client.parse_operations(
                                            [ client.format_path( self.path_in  ) + "[0-255]",
                                              client.format_path( self.path_out ) + "[0-255]" ]),
                                        depth=self.depth, multiple=self.multiple ))
        except Exception as exc:
            logging.warning( "Failed to read IN: %s, OUT: %s Attributes; %s ",
                             client.format_path( self.path_in ), client.format_path( self.path_out ), exc )
        assert self.IN and len( self.IN ) == 256, \
            "Failed to retrieve  IN: %s Attribute: %s" % ( client.format_path( self.path_in ), self.IN )
        assert self.OUT and len( self.OUT ) == 256, \
            "Failed to retrieve OUT: %s Attribute: %s" % ( client.format_path( self.path_out ), self.OUT )
        logging.normal( " IN: %s", self.IN )
        logging.normal( "OUT: %s", self.OUT )

    def complete( self, actuator=0, timeout=None ):
        """Ensure that any prior operation on the actuator is complete."""
        pass # TODO: Implement completion detection state machine

    def position( self, actuator=0, timeout=None, **kwds ):
        logging.detail( "Position: actuator %3d: %r", actuator, kwds )
        begin			= cpppo.timer()
        self.complete( actuator=actuator, timeout=timeout )

        pass # TODO: Implement positioning state machine

