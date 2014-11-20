
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
from cpppo.server.enip.client import (client, await)

class connector( client ):
    """Register a connection to an EtherNet/IP controller."""
    def __init__( self, host, port=None, io_timeout=1, **kwds ):
        self.io_timeout		= io_timeout
        super( connector, self ).__init__( host=host, port=port, **kwds )

        begun			= cpppo.timer()
        try:
            request		= self.register( timeout=self.io_timeout )
            elapsed_req		= cpppo.timer() - begun
            data,elapsed_rpy	= await( self, timeout=max( 0, self.io_timeout - elapsed_req ))

            assert data is not None, "Failed to receive any response"
            assert 'enip.status' in data, "Failed to receive EtherNet/IP response"
            assert data.enip.status == 0, "EtherNet/IP response indicates failure: %s" % data.enip.status
            assert 'enip.CIP.register' in data, "Failed to receive Register response"

            self.session	= data.enip.session_handle
        except Exception as exc:
            logging.warning( "Connect:  Failure in %7.3fs/%7.3fs: %s", cpppo.timer() - begun, exc )
            raise

        logging.detail( "Connect:  Success in %7.3fs/%7.3fs", elapsed_req + elapsed_rpy, self.io_timeout )

    def close( self ):
        self.conn.close()

    def __del__( self ):
        self.close()

        
class smc_lec_gen1( connector ):
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

