#!/usr/bin/env python3

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
__license__                     = "Dual License: GPLv3 (or later) and Commercial (see LICENSE)"

import sys
import os

if __name__ == "__main__" and __package__ is None:
    # Ensure that importing works (whether cpppo_positioner installed or not) with:
    #   python -m cpppo_positioner ...
    #   ./cpppo_positioner/__main__.py ...
    #   ./__main__.py ...
    __package__			= "cpppo_positioner"
try:
    from cpppo_positioner.main import main
except ImportError:
    sys.path.append( os.path.dirname( os.path.dirname( os.path.abspath( __file__ ))))
    from cpppo_positioner.main import main

sys.exit( main() )
