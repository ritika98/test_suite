# Kernel Dump Regression Test - Suite

## Introduction
The aim of the test-suite is to create a framework for recovering and testing those kernel dumps for a different set of configuration variables or code paths while logging every test case separately in a log file and later analyzing which code paths failed.
The test script generates a combination of all the possible combination of the configuration variables and prints the results in the Test Anything Protocol Format.
Configuration variables which are integrated in the test file:
1. Compression (gzip/zstd)
2. Encryption
3. Emulated storage device (virtio-blk/ahci-hd/nvme)
4. Block size (512/4096)
5. Architecture (arm64/amd64/i386)
## Quick Start
### 1. Clone this file
```bashrc
$ https://github.com/ritika98/test_suite.git
```
### 2. Requirements
You are supposed  to install some dependencies before getting out hands with these codes.
Python 3.8 or later with all [requirements.txt](https://github.com/ritika98/test_suite/blob/master/requirements.txt) dependencies installed. To install run:
```bash
$ pip install -r requirements.txt
```
### 3. Usage
```bash
$ python run.py -> log.txt
```
Logs will be generated in the file log.txt
