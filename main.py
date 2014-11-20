#! /usr/bin/env python3

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
__copyright__                   = "Copyright (c) 2013 Hard Consulting Corporation"
__license__                     = "GPLv3 (or later)"

"""
cpppo_positioner	-- Perform a single actuator position change

USAGE
    python -m cpppo_positioner ...

"""

__all__				= ['main']

# 
# main		-- Run the EtherNet/IP actuator positioner
# 
def main( argv=None, **kwds ):
    """Pass the desired argv (excluding the program name in sys.arg[0]; typically pass argv=None, which
    is equivalent to argv=sys.argv[1:], the default for argparse.  Requires at least one tag to be
    defined.
    """
    return 0
