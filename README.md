# Economizer RCx Agent

![Eclipse VOLTTRON 10.0.4rc](https://img.shields.io/badge/Eclipse%20VOLTTRON-10.0.4rc-red.svg)
![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)
[![Passing?](https://github.com/eclipse-volttron/volttron-economizer-rcx/actions/workflows/run-tests.yml/badge.svg)](https://github.com/VOLTTRON/volttron-economizer-rcx/actions/workflows/run-tests.yml)
[![pypi version](https://img.shields.io/pypi/v/volttron-economizer-rcx.svg)](https://pypi.org/project/volttron-economizer-rcx/)

Economizer Agent helps in the re-tuning process and addresses some of the issues
associated with RCx. RCx is known to save energy consumption , but the process
used is not cost-effective.  Economizer Agent and it's diagnostics allow continuous
re-tuning and problem identification which can lower the costs of RCx

## Requirements

* python >= 3.10
* volttron >= 10.0

## Documentation

More detailed documentation can be found on [ReadTheDocs](https://eclipse-volttron.readthedocs.io/). The RST source
of the documentation for this agent is located in the "docs" directory of this repository.

## Installation

Before installing, VOLTTRON should be installed and running.  Its virtual environment should be active.
Information on how to install of the VOLTTRON platform can be found
[here](https://github.com/eclipse-volttron/volttron-core).

Install and start the Economizer RCx Agent (assuming the vip identity "economizer.ahu1").

```shell
   vctl config store economizer.ahu1 config <path/to/config/file>
   vctl install volttron-economizer-rcx --vip-identity economizer.ahu1 --tag economizer --start
```

View the status of the installed agent

```shell
vctl status
```

## Development

Please see the following for contributing guidelines [contributing](https://github.com/eclipse-volttron/volttron-core/blob/develop/CONTRIBUTING.md).

Please see the following helpful guide about [developing modular VOLTTRON agents](https://github.com/eclipse-volttron/volttron-core/blob/develop/DEVELOPING_ON_MODULAR.md)
