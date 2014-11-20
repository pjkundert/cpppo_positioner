from setuptools import setup
import os, sys

here = os.path.abspath( os.path.dirname( __file__ ))
exec( open( 'version.py', 'r' ).read() )

console_scripts			= [
    'cpppo_positioner		= cpppo_positioner.main:main',
]

install_requires		= open( os.path.join( here, "requirements.txt" )).readlines()
# The argparse module wasn't included 'til Python 2.7, but is available for prior versions.
if sys.version_info[0:2] < (2,7):
    install_requires.append( "argparse" )

setup(
    name			= "cpppo_positioner",
    version			= __version__,
    tests_require		= [ "pytest" ],
    install_requires		= install_requires,
    packages			= [ 
        "cpppo_positioner",
    ],
    package_dir			= {
        "cpppo_positioner":		".", 
    },
    entry_points		= {
        'console_scripts': 	console_scripts,
    },
    include_package_data	= True,
    author			= "Perry Kundert",
    author_email		= "perry@hardconsulting.com",
    description			= "Actuator position control via EtherNet/IP",
    long_description		= """\
Control SMC positioning actuators via the LEC-GEN1 EtherNet/IP CIP Gateway.
""",
    license			= "GPLv3",
    keywords			= "SMC position actuator controller EtherNet/IP",
    url				= "https://github.com/pjkundert/cpppo_positioner",
    classifiers			= [
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Environment :: Console",
        "Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator",
    ],
)
