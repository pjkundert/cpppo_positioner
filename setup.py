from setuptools import setup
import os

HERE				= os.path.abspath( os.path.dirname( __file__ ))

install_requires		= open( os.path.join( HERE, "requirements.txt" )).readlines()
tests_require			= open( os.path.join( HERE, "requirements-tests.txt" )).readlines()
options_require			= [ 'dev', ]
extras_require			= {
    option: list(
        # Remove whitespace, elide blank lines and comments
        ''.join( r.split() )
        for r in open( os.path.join( HERE, f"requirements-{option}.txt" )).readlines()
        if r.strip() and not r.strip().startswith( '#' )
    )
    for option in options_require
}
# Make python-slip39[all] install all extra (non-tests) requirements, excluding duplicates
extras_require['all']		= list( set( sum( extras_require.values(), [] )))

# Since setuptools is retiring tests_require, add it as another option (but not included in 'all')
extras_require['tests']		= tests_require


exec( open( 'version.py', 'r' ).read() )

entry_points			= dict(
    console_scripts		= [
        'cpppo_positioner	= cpppo_positioner.main:main',
    ]
)

package_dir			= dict(
    cpppo_positioner		= ".", 
)
packages			= [ 
    "cpppo_positioner",
]

setup(
    name			= "cpppo_positioner",
    version			= __version__,  # noqa: F821
    install_requires		= install_requires,
    tests_require		= tests_require,
    extras_require		= extras_require,
    packages			= packages,
    package_dir			= package_dir,
    entry_points		= entry_points,
    include_package_data	= True,
    author			= "Perry Kundert",
    author_email		= "perry@dominionrnd.com",
    description			= "Actuator position control via native RS485 serial Modbus/RTU",
    long_description		= """\
Control SMC positioning actuators via native RS485 serial Modbus/RTU protocol
""",
    license			= "Dual License; GPLv3 and Proprietary",
    keywords			= "SMC position actuator controller EtherNet/IP",
    url				= "https://github.com/pjkundert/cpppo_positioner",
    classifiers			= [
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Environment :: Console",
        "Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator",
    ],
)
