#! /usr/bin/env python

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

"""
cpppo_positioner	-- Perform a single actuator position change

USAGE
    python -m cpppo_positioner ...
    cpppo_positioner ...

"""

__all__				= ['main']

import argparse
import itertools
import json
import logging
import os
import signal
import sys
import time
import traceback

import cpppo

# The default address to connect to.  Obviously, 'localhost' is unlikely to be the target actuator
# gateway (except under test scenarios), but 44818 is the standard EtherNet/IP port.
address				= ('localhost',44818)


# Signal Handling

# To support re-opening a log file from within a signal handler, we need an atomic method to safely
# close a FileHandler's self.stream (an open file), while it is certain to not be in use.  Under
# Python2/3, FileHandler.close acquires locks preventing a race condition with FileHandler.emit.

# There is an opportunity for race conditions while traversing logging.root.handlers here, iff the
# root Logger's handlers are being added or deleted by this (or another) Thread, which we don't do.

# More importantly, however, since logging uses threading.RLock, this procedure must be run in a
# separate thread, or by the main thread but NOT inside the signal handler!  Since the main thread
# could hold the lock when it arrives here as a result of the signal, then the locks will be
# ineffective -- which is perhaps a good thing, otherwise we would deadlock, instead of just
# crash...  So, set a flag when the signal occurs, and arrange to check the flag from time to time
# when the incoming socket is idle.

logging_levelmap		= {
    0: logging.WARNING,
    1: logging.NORMAL,
    2: logging.DETAIL,
    3: logging.INFO,
    4: logging.DEBUG,
}

uptime_basis			= cpppo.timer()
uptime_signalled		= False
shutdown_signalled		= False
logrotate_signalled		= False
levelmap_change			= 0 # may become +'ve/-'ve

def uptime_request( signum, frame ):
    global uptime_signalled
    uptime_signalled		= True

def shutdown_request( signum, frame ):
    global shutdown_signalled
    shutdown_signalled		= True

def logrotate_request( signum, frame ):
    global logrotate_signalled
    logrotate_signalled		= True

def loglevelup_request( signum, frame ):
    global levelmap_change
    levelmap_change	       += 1

def logleveldn_request( signum, frame ):
    global levelmap_change
    levelmap_change	       -= 1

def signal_service():
    """Service known signals.  When logging, default to logat NORMAL, but ensure the
    message is seen if higher (eg. WARNING).  Support being in unknown logging
    levels when in/decreasing.

    """
    global levelmap_change
    if levelmap_change:
        rootlog			= logging.getLogger()
        actual			= rootlog.getEffectiveLevel()
        closest			= min( logging_levelmap.values(), key=lambda x:abs(x-actual) )
        highest			= max( logging_levelmap.keys() )
        for i,lvl in logging_levelmap.items():
            if lvl == closest:
                key		= i + levelmap_change
                break
        desired			= logging_levelmap.get( key, logging.DEBUG if key > highest else logging.ERROR )
        if actual != desired:
            rootlog.setLevel( desired )
        levelmap_change		= 0

    global logrotate_signalled
    global uptime_signalled
    if logrotate_signalled:
        logrotate_signalled	= False
        uptime_signalled	= True

        rootlog			= logging.getLogger()
        actual			= rootlog.getEffectiveLevel()
        rootlog.log( max( logging.NORMAL, actual ), "Rotating log files due to signal" )
        for hdlr in logging.root.handlers:
            if isinstance( hdlr, logging.FileHandler ):
                hdlr.close()

    global uptime_basis
    if uptime_signalled:
        uptime_signalled	= False
        uptime			= cpppo.timer() - uptime_basis

        rootlog			= logging.getLogger()
        actual			= rootlog.getEffectiveLevel()
        rootlog.log( max( logging.NORMAL, actual ), "Uptime: %3d:%02d:%06.3f",
                     int( uptime // 3600 ), int( uptime % 3600 // 60 ), uptime % 60 )


# 
# main		-- Run the EtherNet/IP actuator positioner
# 
def main( argv=None, idle_service=None, **kwds ):
    """Pass the desired argv (excluding the program name in sys.arg[0]; typically pass argv=None, which
    is equivalent to argv=sys.argv[1:], the default for argparse.  Requires at least one tag to be
    defined.

    Takes a sequence of blocks of actuator position information (in JSON format), either from the
    command-line, or (if '-' provided) from stdin.

    """
    ap				= argparse.ArgumentParser(
        description = "Transmit position to actuators.",
        epilog = "" )

    ap.add_argument( '-g', '--gateway', default='smc.smc_lec_gen1',
                     help="Gateway module.class for positioning actuator (default: smc.smc_lec_gen1)" )
    ap.add_argument( '-c', '--config', default=None,
                     help="Gateway module.class configuration JSON (default: None)" )
    ap.add_argument( '-v', '--verbose', default=0, action="count",
                     help="Display logging information." )
    ap.add_argument( '-a', '--address', default=( "%s:%d" % address ),
                     help="EtherNet/IP interface[:port] of actuator gateway to connect to (default: %s:%d)" % address )
    ap.add_argument( '-l', '--log',
                     help="Log file, if desired" )
    ap.add_argument( '-t', '--timeout', default=1,
                     help="Gateway I/O timeout" )

    ap.add_argument( 'position', nargs="+",
                     help="Any JSON position dictionaries, or numeric delays (in seconds)")

    args			= ap.parse_args( argv )

    # Deduce interface:port address to connect, and correct types (default is address, above)
    conn			= args.address.split(':')
    assert 1 <= len( conn ) <= 2, "Invalid --address [<interface>]:[<port>}: %s" % args.address
    conn			= ( str( conn[0] ) if conn[0] else address[0],
                                    int( conn[1] ) if len( conn ) > 1 and conn[1] else address[1] )

    # Set up logging level (-v...) and --log <file>
    cpppo.log_cfg['level']	= ( logging_levelmap[args.verbose] 
                                    if args.verbose in logging_levelmap
                                    else logging.DEBUG )

    # Chain any provided idle_service function with log rotation; these may (also) consult global
    # signal flags such as logrotate_request, so execute supplied functions before logrotate_perform
    idle_service		= [ idle_service ] if idle_service else []
    if args.log:
        # Output logging to a file, and handle UNIX-y log file rotation via 'logrotate', which sends
        # signals to indicate that a service's log file has been moved/renamed and it should re-open
        cpppo.log_cfg['filename']= args.log
        signal.signal( signal.SIGHUP, logrotate_request )

    logging.basicConfig( **cpppo.log_cfg )

    signal.signal( signal.SIGTERM, shutdown_request )
    if hasattr( signal, 'SIGUSR1' ):
        signal.signal( signal.SIGUSR1, loglevelup_request )
    if hasattr( signal, 'SIGUSR2' ):
        signal.signal( signal.SIGUSR2, logleveldn_request )
    if hasattr( signal, 'SIGURG' ):
        signal.signal( signal.SIGURG,  uptime_request )

    idle_service.append( signal_service )

    # Load the specified Gateway module.class, and ensure class is present; include the module's own
    # directory to get the locally specified ones.
    sys.path.append( os.path.dirname( __file__ ))
    mod,cls			= args.gateway.split('.')
    __import__( mod, globals(), locals(), [], 0 )
    gateway_module		= sys.modules[mod]
    assert hasattr( gateway_module, cls ), "Gateway module %s missing target class: %s" % ( mod, cls )
    gateway_class		= getattr( gateway_module, cls )

    # Parse any Gateway configuration JSON supplied
    gateway_config		= {}
    if args.config:
        try:
            gateway_config	= json.loads( args.config )
            assert isinstance( gateway_config, dict ), \
                "Gateway configuration JSON must produce a dictionary"
        except Exception as exc:
            logging.warning( "Invalid Gateway config: %s; %s", args.config, exc )
            raise

    # Read and process JSON position and delay inputs; '-' means read from sys.stdin 'til EOF.  Can be mixed, eg:
    # 
    #     '{ <initial position> }' '# a comment, followed by a delay' 1.5 - '{ <final position> }'

    if '-' in args.position:
        # Collect input from sys.stdin 'til EOF, at position of '-' in argument list
        minus			= args.position.index('-')
        positer			= itertools.chain( args.position[:minus], sys.stdin, args.position[minus+1:] )
    else:
        positer			= iter( args.position )

    start			= cpppo.timer()
    count,success		= 0,0
    gateway			= None # None --> never, False --> failed, truthy --> connected
    while not shutdown_signalled:
        # Perform all idle_services, and get next position, terminate loop when done
        map( lambda f: f(), idle_service )
        try:
            pos			= next( positer )
        except StopIteration:
            break

        # Ignore whitespace and comments
        inp			= pos.strip()
        if inp.startswith( '#' ):
            inp			= ''
        if not inp:
            continue

        # A non-empty non-comment input in 'inp'; parse it as JSON into 'dat'; allow numeric and dict
        try:
            dat			= json.loads( inp )
        except Exception as exc:
            logging.warning( "Invalid position data: %s; %s", inp, exc )
            continue
        if isinstance( dat, cpppo.natural.num_types ):
            logging.normal( "Delaying: %7.3fs", dat )
            time.sleep( dat )
            continue
        if not isinstance( dat, dict ):
            logging.warning( "Unknown position type: %s: %r", type(dat), dat )
            continue

        # A position dict in 'dat'; attempt to position to it.  We'll wait forever to establish a
        # connection to the gateway, but attempt each positioning command only once.
        logging.normal( "Position: %r", dat )
        count		       += 1
        while not gateway:
            try:
                if not gateway:
                    if gateway is None:
                        logging.detail( "Gateway:  %s:%d...", conn[0], conn[1] )
                    gateway	= gateway_class( config=gateway_config,
                                                 host=conn[0], port=conn[1], timeout=args.timeout )
                    logging.normal( "Gateway:  %s:%d connected", conn[0], conn[1] )
            except Exception as exc:
                ( logging.warning if gateway is None else logging.detail )(
                    "Gateway:  %s:%d connection failed: %s\n%s", conn[0], conn[1], exc,
                    traceback.format_exc() )
                gateway		= False
                time.sleep( .1 ) # avoid tight loop on connection failures

        # Have a gateway; issue the positioning command
        try:
            gateway.position( **dat )
            success	       += 1
        except Exception as exc:
            logging.warning( "Position: %r failure; closing gateway: %s\n%s", exc, traceback.format_exc() )
            gateway.close()
            gateway		= None
        
    logging.normal( "Completed %d/%d actuator positions in %7.3fs", success, count, cpppo.timer() - start )
    return 0 if success == count else 1
