import pexpect 
import time 
import argparse
import itertools as it
from TAP.Simple import *
import re
import itertools as it

all_params = {  
				"encryption":["yes","no"],
				"compression":["no","zstd_compression","gzip_compression"],
				"emulation":[ "ahci-hd","virtio-blk", "nvme"],
				"sector-size" : ["512","4096"],
			  }


config_vars = {
   "dump_config_vars" : {
			"gzip_compression": " -z",
			"zstd_compression" : " -Z",
			"encryption": " -k public.pem"
},
   "dump_device":"/dev/gpt/swapfs",
   "undump_config_vars" : {
			"gzip_compression": "gunzip /var/crash/vmcore.0.gz",
			"zstd_compression" : "zstd --decompress /var/crash/vmcore.0.zst",
			"encryption": "decryptcore -p private.pem -k /var/crash/key.0 -e /var/crash/vmcore_encrypted.0 -c /var/crash/vmcore.0"
}
   
}

boot_vars = {
	"cpu": "2",
	"memory": "1G",
	"device" : "/root/GSOC/FreeBSD-13.0-CURRENT-amd64.raw",
	"name" : "freebsd",
	"emulation" : "ahci-hd",
	"sector-size": 4096
}
emulation = {
	"ahci-hd" : " -s 4:0,ahci-hd,dumpdev,",
	"nvme" : " -s 4:0,nvme,dumpdev,",
	"virtio-blk" : ","
}
sectorsize ={
	"ahci-hd" : "sectorsize=",
	"nvme" : "sectsz=",
	"virtio-blk" : "sectorsize="
}


def set_dump_cmd(config_vars, parameters):
	cmd = "dumpon"
	for flag in parameters["dump_flags"]:
		cmd = cmd + config_vars["dump_config_vars"][flag]
	if "dump_device" in config_vars:
		cmd = cmd + " "+ config_vars["dump_device"]
	else:
		cmd = cmd + "/dev/gpt/swapfs"
	return cmd


def set_undump_cmd(config_vars, parameters):
	cmd_list = {}
	if "encryption" in parameters["dump_flags"]:
		cmd = ""
		cmd = cmd + config_vars["undump_config_vars"]["encryption"]
		cmd_list["decryption"] = cmd
	for flag in parameters["dump_flags"]:
		cmd = ""
		if(flag != "encryption"):
			cmd = cmd + config_vars["undump_config_vars"][flag]
			cmd_list["decompression"] = cmd
	return cmd_list



if __name__ == "__main__":
	varnames=sorted(all_params)
	combinations = [dict(zip(varnames, prod)) for prod in it.product(*(all_params[varname] for varname in varnames))]
	for parameter in combinations:
		for i in boot_vars:
			if i in parameter:
				boot_vars[i] = parameter[i]
		print(parameter)
		config_parameters={"dump_flags":[]}
		if(parameter["encryption"] == "yes"):
			config_parameters["dump_flags"].append("encryption")
		if(parameter["compression"] != "no"):
			config_parameters["dump_flags"].append(parameter["compression"])
		pexpect.run("bhyveload -c stdio -m 1G -d FreeBSD-13.0-CURRENT-amd64.raw freebsd")
		time.sleep(20)
		pexpect.run("truncate -s 4G dumpdev")
		time.sleep(5)
		ok = TAP.Builder.create(4).ok
		command_line = "bhyve -c " + str(boot_vars["cpu"]) + " -m " + boot_vars["memory"] + " -H -A -P -g 0 -s 0:0,hostbridge -s 1:0,lpc -s 2:0,virtio-net,tap0 -l com1,stdio -s 3:0,virtio-blk,FreeBSD-13.0-CURRENT-amd64.raw" + emulation[boot_vars["emulation"]] + sectorsize[boot_vars["emulation"]]  + str(boot_vars["sector-size"]) + " " + boot_vars["name"]
		print(command_line)
		child = pexpect.spawn(command_line)
		child.logfile = open("temp_log1.txt", "wb")
		child.expect('login', timeout = 1000)
		child.sendline('root')
		child.expect('root@freebsd:~ #')
		child.sendline('dumpon /dev/null')
		child.expect('root@freebsd:~ #')
		child.sendline('openssl genrsa -out private.pem 4096')
		child.expect('root@freebsd:~ #')
		child.sendline('openssl rsa -in private.pem -outform PEM -pubout -out public.pem')
		dump_cmd = set_dump_cmd(config_vars, config_parameters)
		child.expect('root@freebsd:~ #',timeout = 1000)
		child.sendline(dump_cmd)
		child.expect('root@freebsd:~ #',timeout = 1000)
		ok(child.before.decode("utf-8").strip() == dump_cmd,  "minidump passed")
		child.sendline('sysctl debug.kdb.panic=1')
		child.expect('db> ', timeout = 1000)
		child.sendline('continue')
		time.sleep(10)
		child.close()
		code = child.exitstatus
		if(code == 0):
			pexpect.run("bhyveload -c stdio -m 1G -d FreeBSD-13.0-CURRENT-amd64.raw freebsd")
			time.sleep(20)
			child = pexpect.spawn(command_line)
			child.logfile = open("temp_log2.txt", "wb")
			child.expect('login',timeout = 1000)
			child.sendline('root')
			child.expect('root@freebsd:~ #', timeout = 1000)
			child.sendline('savecore /var/crash /dev/gpt/swapfs')
			ok(child.after == b'root@freebsd:~ #',  "savecore passed")
			cmd = set_undump_cmd(config_vars, config_parameters)
			child.expect('root@freebsd:~ #',timeout = 1000)
			k = len(cmd)
			for i in cmd:
				if(i == 'decryption'):
					child.sendline(cmd[i])
					child.expect('root@freebsd:~ #',timeout = 1000)
					ok(re.search("[ERROR]", child.before.decode("utf-8").strip()) == None, "decryption minidump passed")
				elif(i == 'decompression'):
					child.sendline(cmd[i])
					child.expect('root@freebsd:~ #',timeout = 1000)
					ok(re.search("zstd: |gzip: ", child.before.decode("utf-8").strip()) == None, "decompression minidump passed")
				else:
					pass
			child.sendline('stat /var/crash/vmcore.0')
			child.expect('root@freebsd:~ #',timeout = 1000)
			child.sendline('kgdb /boot/kernel/kernel  /var/crash/vmcore.0')
			child.expect('(kgdb)')
			child.sendline('quit')
			child.expect('root@freebsd:~ #',timeout = 1000)
			child.sendline('rm -rf /var/crash/*')
			child.expect('root@freebsd:~ #',timeout = 1000)
			child.sendline('poweroff')
			time.sleep(10)
			child.close()



