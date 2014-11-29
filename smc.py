
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

    def complete( self, actuator=0, timeout=None ):
        """Ensure that any prior operation on the actuator is complete."""
        pass # TODO: Implement completion detection state machine

    def position( self, actuator=0, timeout=None, **kwds ):
        logging.detail( "Position: actuator %3d: %r", actuator, kwds )
        begin			= cpppo.timer()
        self.complete( actuator=actuator, timeout=timeout )

        pass # TODO: Implement positioning state machine

