#!/usr/bin/env python3

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

# 
# cpppo_positioner.simulator
# 
#     Provision a simulated SMC controller on the specified serial port, responding to 1 or more
# actuator numbers.
# 
#     python -m cpppo_positioner.simulator /dev/ttyS0 1 2
# 

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

__author__                      = "Perry Kundert"
__email__                       = "perry@hardconsulting.com"
__copyright__                   = "Copyright (c) 2014 Hard Consulting Corporation"
__license__                     = "Dual License: GPLv3 (or later) and Commercial (see LICENSE)"

import sys
import os
import json

from cpppo.bin.modbus_sim import main as main_modbus_sim

if __name__ == "__main__" and __package__ is None:
    # Ensure that importing works (whether cpppo_positioner installed or not) with:
    #   python -m cpppo_positioner.simulator ...
    #   ./cpppo_positioner/simulator.py ...
    #   ./simulator.py ...
    __package__			= "cpppo_positioner"

try:
    from cpppo_positioner import smc
except ImportError:
    sys.path.append( os.path.dirname( os.path.dirname( os.path.abspath( __file__ ))))
    from cpppo_positioner import smc


if __name__ == "__main__": 

    # Some initial setup before the main loop; no logging set up yet...

    # Find the SMC Simulator related arguments, and pull them out of the sys.argv list
    
    # The first argument must be a device
    address			= ''
    if '--address' in sys.argv:
        i			= sys.argv.index( '--address' )
        sys.argv.pop( i )
        address			= sys.argv.pop( i )
    elif len( sys.argv ) > 1:
        address			= sys.argv.pop( 1 )
        
    # The actuator number(s) assigned to this simulator.
    actuators			= []
    while True:
        if '--actuator' in sys.argv:
            i			= sys.argv.index( '--actuator' )
            sys.argv.pop( i )
            actuators.append( int( sys.argv.pop( i )))
        elif len( sys.argv ) > 1 and sys.argv[1].isdigit():
            actuators.append( int( sys.argv.pop( 1 )))
        else:
            break
    assert address, \
        "Must supply a serial port --address name, eg. /dev/ttyS0"
    assert actuators, \
        "Must supply 1 or more --actuator <id> numbers, eg 1"

    # Does NOT simulate the behaviors of an SMC Actuator; just the required registers
    argv			= [
        '-vvv', '--log', '.'.join( [
            'simulator', 'log', 'actuator_'+'_'.join( map( str, actuators )) ] ),
        '--address', address,
        '    17 -     64 = 0',	# Coil           0x10   - 0x3F   (     1 +) (rounded to 16 bits)
        ' 10065 -  10081 = 0',	# Discrete Input 0x40   - 0x50   ( 10001 +)
        ' 76865 -  77376 = 0',	# Holding Regs   0x9000 - 0x911F ( 40001 +)
        # Configure Modbus/RTU simulator to use specified port serial framing
        '--config', json.dumps( {
            'stopbits': smc.PORT_STOPBITS,
            'bytesize': smc.PORT_BYTESIZE,
            'parity':   smc.PORT_PARITY,
            'baudrate': smc.PORT_BAUDRATE,
            'slaves':	actuators,
            'timeout':  smc.PORT_TIMEOUT,
            'ignore_missing_slaves': True,
        } )
    ]

    sys.exit( main_modbus_sim( argv=argv ))
