#!/usr/bin/env python

# This file is part of PyEMMA.
#
# Copyright (c) 2015, 2014 Computational Molecular Biology Group, Freie Universitaet Berlin (GER)
#
# MSMTools is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""EMMA: Emma's Markov Model Algorithms

EMMA is an open source collection of algorithms implemented mostly in
`NumPy <http://www.numpy.org/>`_ and `SciPy <http://www.scipy.org>`_
to analyze trajectories generated from any kind of simulation
(e.g. molecular trajectories) via Markov state models (MSM).

"""

from __future__ import print_function, absolute_import

import sys
import os
import versioneer
import warnings
from io import open

DOCLINES = __doc__.split("\n")

CLASSIFIERS = """\
Development Status :: 5 - Production/Stable
Environment :: Console
Environment :: MacOS X
Intended Audience :: Science/Research
License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)
Natural Language :: English
Operating System :: MacOS :: MacOS X
Operating System :: POSIX
Operating System :: Microsoft :: Windows
Programming Language :: Python :: 2.7
Programming Language :: Python :: 3
Topic :: Scientific/Engineering :: Bio-Informatics
Topic :: Scientific/Engineering :: Chemistry
Topic :: Scientific/Engineering :: Mathematics
Topic :: Scientific/Engineering :: Physics

"""
from setup_util import lazy_cythonize
try:
    from setuptools import setup, Extension, find_packages
except ImportError as ie:
    print("PyEMMA requires setuptools. Please install it with conda or pip.")
    sys.exit(1)

###############################################################################
# Extensions
###############################################################################
def extensions():
    """How do we handle cython:
    1. when on git, require cython during setup time (do not distribute
    generated .c files via git)
     a) cython present -> fine
     b) no cython present -> install it on the fly. Extensions have to have .pyx suffix
    This is solved via a lazy evaluation of the extension list. This is needed,
    because build_ext is being called before cython will be available.
    https://bitbucket.org/pypa/setuptools/issue/288/cannot-specify-cython-under-setup_requires

    2. src dist install (have pre-converted c files and pyx files)
     a) cython present -> fine
     b) no cython -> use .c files
    """
    USE_CYTHON = False
    try:
        from Cython.Build import cythonize
        USE_CYTHON = True
    except ImportError:
        warnings.warn('Cython not found. Using pre cythonized files.')

    # setup OpenMP support
    from setup_util import detect_openmp
    openmp_enabled, needs_gomp = detect_openmp()

    import mdtraj
    from numpy import get_include as _np_inc
    np_inc = _np_inc()

    pybind_inc = os.path.join(os.path.dirname(__file__), 'pybind11', 'include')
    assert os.path.exists(pybind_inc)

    exts = []

    lib_prefix = 'lib' if sys.platform.startswith('win') else ''

    clustering_module = \
        Extension('pyemma.coordinates.clustering._ext',
                  sources=['pyemma/coordinates/clustering/src/clustering_module.cpp'],
                  include_dirs=[
                      mdtraj.capi()['include_dir'],
                      np_inc,
                      pybind_inc,
                      'pyemma/coordinates/clustering/include',
                  ],
                  language='c++',
                  libraries=[lib_prefix+'theobald'],
                  library_dirs=[mdtraj.capi()['lib_dir']],
                  extra_compile_args=['-std=c++11', '-O3', '-fvisibility=hidden'])

    covar_module = \
        Extension('pyemma._ext.variational.estimators.covar_c._covartools',
                  sources=['pyemma/_ext/variational/estimators/covar_c/covartools.cpp'],
                  include_dirs=['pyemma/_ext/variational/estimators/covar_c/',
                                np_inc,
                                pybind_inc,
                                ],
                  extra_compile_args=['-std=c++11', '-O3', '-fvisibility=hidden'])

    eig_qr_module = \
        Extension('pyemma._ext.variational.solvers.eig_qr.eig_qr',
                  sources=['pyemma/_ext/variational/solvers/eig_qr/eig_qr.pyx'],
                  include_dirs=['pyemma/_ext/variational/solvers/eig_qr/', np_inc],
                  extra_compile_args=['-std=c99', '-O3'])

    orderedset = \
        Extension('pyemma._ext.orderedset._orderedset',
                  sources=['pyemma/_ext/orderedset/_orderedset.pyx'],
                  include_dirs=[np_inc],
                  extra_compile_args=['-O3'])

    exts += [clustering_module,
             covar_module,
             eig_qr_module,
             orderedset
             ]

    if not USE_CYTHON:
        # replace pyx files by their pre generated c code.
        for e in exts:
            new_src = []
            for s in e.sources:
                new_src.append(s.replace('.pyx', '.c'))
            e.sources = new_src
    else:
        exts = cythonize(exts)

    if openmp_enabled:
        warnings.warn('enabled openmp')
        omp_compiler_args = ['-fopenmp']
        omp_libraries = ['-lgomp'] if needs_gomp else []
        omp_defines = [('USE_OPENMP', None)]
        for e in exts:
            e.extra_compile_args += omp_compiler_args
            e.extra_link_args += omp_libraries
            e.define_macros += omp_defines

    return exts


def get_cmdclass():
    versioneer_cmds = versioneer.get_cmdclass()

    sdist_class = versioneer_cmds['sdist']
    class sdist(sdist_class):
        """ensure cython files are compiled to c, when distributing"""

        def run(self):
            # only run if .git is present
            if not os.path.exists('.git'):
                print("Not on git, can not create source distribution")
                return

            try:
                from Cython.Build import cythonize
                print("cythonizing sources")
                cythonize(extensions())
            except ImportError:
                warnings.warn('sdist cythonize failed')
            return sdist_class.run(self)

    versioneer_cmds['sdist'] = sdist

    from setuptools.command.test import test as TestCommand

    class PyTest(TestCommand):
        user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

        def initialize_options(self):
            TestCommand.initialize_options(self)
            self.pytest_args = ['pyemma']

        def run_tests(self):
            # import here, cause outside the eggs aren't loaded
            import pytest
            errno = pytest.main(self.pytest_args)
            sys.exit(errno)

    versioneer_cmds['test'] = PyTest

    return versioneer_cmds


metadata = dict(
    name='pyEMMA',
    maintainer='Martin K. Scherer',
    maintainer_email='m.scherer@fu-berlin.de',
    author='The Emma team',
    author_email='info@emma-project.org',
    url='http://github.com/markovmodel/PyEMMA',
    license='LGPLv3+',
    description=DOCLINES[0],
    long_description=open('README.rst', encoding='utf8').read(),
    version=versioneer.get_version(),
    platforms=["Windows", "Linux", "Solaris", "Mac OS-X", "Unix"],
    classifiers=[c for c in CLASSIFIERS.split('\n') if c],
    keywords='Markov State Model Algorithms',
    # packages are found if their folder contains an __init__.py,
    packages=find_packages(),
    # install default emma.cfg into package.
    package_data=dict(pyemma=['pyemma.cfg']),
    cmdclass=get_cmdclass(),
    tests_require=['pytest'],
    # runtime dependencies
    install_requires=[
        'bhmm>=0.6,<0.7',
        'decorator>=4.0.0',
        'matplotlib',
        'mdtraj>=1.8.0',
        'msmtools>=1.2',
        'pathos',
        'progress-reporter',
        'psutil>=3.1.1',
        'pyyaml',
        'scipy>=0.11',
        'thermotools>=0.2.6',
        'numpy>=1.7.0',
    ],
    zip_safe=False,
)

# this is only metadata and not used by setuptools
metadata['requires'] = ['numpy', 'scipy']

# not installing?
if len(sys.argv) == 1 or (len(sys.argv) >= 2 and ('--help' in sys.argv[1:] or
                          sys.argv[1] in ('--help-commands',
                                          '--version',
                                          'clean'))):
    pass
else:
    # setuptools>=2.2 can handle setup_requires
    metadata['setup_requires'] = ['numpy>=1.7.0',
                                  'scipy',
                                  'mdtraj>=1.7.0',
                                  ]

    metadata['package_data'] = {
                                'pyemma': ['pyemma.cfg', 'logging.yml'],
                                'pyemma.coordinates.tests': ['data/*'],
                                'pyemma.msm.tests': ['data/*'],
                                'pyemma.datasets': ['*.npz'],
                                'pyemma.util.tests': ['data/*'],
                                }

    # when on git, we require cython
    if os.path.exists('.git'):
        warnings.warn('using git, require cython')
        metadata['setup_requires'] += ['cython>=0.22']

        # init submodules
        import subprocess
        modules = ['pybind11', ]
        cmd = "git submodule update --init {mod}"
        for m in modules:
            subprocess.check_call(cmd.format(mod=m).split(' '))

    # only require numpy and extensions in case of building/installing
    metadata['ext_modules'] = lazy_cythonize(callback=extensions)

setup(**metadata)

