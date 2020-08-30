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
				"emulation":[ "ahci","virtio-blk", "nvme"],
				"sector-size" : ["512","4096"],
				"architecture" : [ "amd64","i386","arm64"]

			  }

dump_device = {
	"bhyve" : {
		"ahci" : "/dev/ada0",
		"nvme" : "/dev/nvd0",
		"virtio-blk" : "/dev/vtbd1"
},
	"qemu" : {
		"ahci" : "/dev/ada0",
		"nvme" : "/dev/nda0",
		"virtio-blk" : "/dev/vtbd1"
		}
}


config_vars = {
   "dump_config_vars" : {
			"gzip_compression": " -z",
			"zstd_compression" : " -Z",
			"encryption": " -k public.pem"
},
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
	"emulation" : "ahci",
	"sector-size": 4096
}
emulation = {
	"bhyve":{
		"ahci" : " -s 4:0,ahci-hd,dumpdev,",
		"nvme" : " -s 4:0,nvme,dumpdev,",
		"virtio-blk" : " -s 4:0,virtio-blk,dumpdev,"
		},
	"qemu":{
		"ahci" : " -drive id=disk,file=dumpdev,if=none,id=nvme0 -device ahci,id=ahci -device ide-hd,drive=disk,bus=ahci.0",
		"nvme" : " -drive id=disk,file=dumpdev,if=none,id=nvme0 -device nvme,drive=disk,serial=deadbeaf1,num_queues=8",
		"virtio-blk" : ""
	}
}
sectorsize ={
	"bhyve":{
		"ahci" : "sectorsize=",
		"nvme" : "sectsz=",
		"virtio-blk" : "sectorsize="
		},
	"qemu":{
		"ahci" : "",
		"nvme" : ",physical_block_size=",
		"virtio-blk" : ",physical_block_size="
		}

}
arc = {
	"i386" : "FreeBSD-13.0-CURRENT-i386.raw",
	"amd64" : "FreeBSD-13.0-CURRENT-amd64.raw",
	"arm64" : "FreeBSD-13.0-CURRENT-arm64-aarch64.raw"
}

	
hypervisor = {
	"i386" : "bhyve",
	"amd64" : "bhyve",
	"arm64" : "qemu"
	
}
def set_dump_cmd(config_vars, parameters, dumpdeev):
	cmd = "dumpon"
	for flag in parameters["dump_flags"]:
		cmd = cmd + config_vars["dump_config_vars"][flag]
	cmd = cmd + " " + dumpdev
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
	count = 1
	varnames=sorted(all_params)
	combinations = [dict(zip(varnames, prod)) for prod in it.product(*(all_params[varname] for varname in varnames))]
	for parameter in combinations:
		for i in boot_vars:
			if i in parameter:
				boot_vars[i] = parameter[i]
		print("****************************************************************************")
		print("Test case ", count)
		for i in parameter :
			print(i + " : "+ parameter[i])
		config_parameters={"dump_flags":[]}
		if(parameter["encryption"] == "yes"):
			config_parameters["dump_flags"].append("encryption")
		if(parameter["compression"] != "no"):
			config_parameters["dump_flags"].append(parameter["compression"])
		dumpdev = dump_device[hypervisor[parameter["architecture"]]][parameter["emulation"]]
		if(parameter["architecture"] == "arm64"):
			if(parameter["emulation"]=="ahci"):
				command_line = "qemu-system-aarch64 -m " + boot_vars["memory"] + " -cpu max -M virt -bios QEMU_EFI.fd -nographic -drive format=raw,if=none,file=" + arc[parameter["architecture"]] + ",id=hd0 -device virtio-net-device,netdev=net0 -netdev user,id=net0 -device virtio-blk-device,drive=hd0" + emulation["qemu"][boot_vars["emulation"]] + " -drive if=none,file=dumpdev,id=hd1 -device virtio-blk-device,drive=hd1 -smp cpus=" + str(boot_vars["cpu"])
			else:
				command_line = "qemu-system-aarch64 -m " + boot_vars["memory"] + " -cpu max -M virt -bios QEMU_EFI.fd -nographic -drive format=raw,if=none,file=" + arc[parameter["architecture"]] + ",id=hd0 -device virtio-net-device,netdev=net0 -netdev user,id=net0 -device virtio-blk-device,drive=hd0" + emulation["qemu"][boot_vars["emulation"]] + sectorsize["qemu"][boot_vars["emulation"]] + str(boot_vars["sector-size"]) + " -drive if=none,file=dumpdev,id=hd1 -device virtio-blk-device,drive=hd1 -smp cpus=" + str(boot_vars["cpu"])
		else:
			pexpect.run("bhyvectl --destroy --vm=freebsd")
			time.sleep(2)
			load_cmd = "bhyveload -c stdio -m 1G -d " + arc[parameter["architecture"]] + " freebsd"
			pexpect.run(load_cmd)
			time.sleep(10)
			pexpect.run("truncate -s 4G dumpdev")
			time.sleep(2)
			command_line = "bhyve -c " + str(boot_vars["cpu"]) + " -m " + boot_vars["memory"] + " -H -A -P -g 0 -s 0:0,hostbridge -s 1:0,lpc -s 2:0,virtio-net,tap0 -l com1,stdio -s 3:0,virtio-blk,"+arc[parameter["architecture"]] + emulation["bhyve"][boot_vars["emulation"]] + sectorsize["bhyve"][boot_vars["emulation"]]  + str(boot_vars["sector-size"]) + " " + boot_vars["name"]
		# print("Boot Command : " + command_line)
		ok = TAP.Builder.create(6).ok
		child = pexpect.spawn(command_line)
		child.logfile = open("temp1.txt", "wb")
		index = child.expect(['login',pexpect.TIMEOUT, "mountroot>"], timeout = 2000)
		ok(index == 0, "VM Boot passed")
		if(index == 0):
			child.sendline('root')
			child.expect('root@freebsd:~ #')
			child.sendline('rm -rf /var/crash/*')
			child.expect('root@freebsd:~ #')
			child.sendline('dumpon /dev/null')
			child.expect('root@freebsd:~ #')
			child.sendline('openssl genrsa -out private.pem 4096')
			child.expect('root@freebsd:~ #')
			child.sendline('openssl rsa -in private.pem -outform PEM -pubout -out public.pem')
			child.expect('root@freebsd:~ #')
			child.sendline('fsync public.pem')
			child.expect('root@freebsd:~ #')
			child.sendline('fsync private.pem')
			dump_cmd = set_dump_cmd(config_vars, config_parameters, dumpdev)
			child.expect('root@freebsd:~ #',timeout = 1000)
			child.sendline(dump_cmd)
			child.expect('root@freebsd:~ #',timeout = 1000)
			ok(child.before.decode("utf-8").strip() == dump_cmd,  "minidump passed")
			child.sendline('sysctl debug.kdb.panic=1')
			child.expect('db> ', timeout = 1000)
			child.sendline('continue')
			time.sleep(10)
			if(parameter["architecture"] != "arm64"):
				child.close()
				pexpect.run("bhyvectl --destroy --vm=freebsd")
				time.sleep(2)
				load_cmd = "bhyveload -c stdio -m 1G -d " + arc[parameter["architecture"]] + " freebsd"
				pexpect.run(load_cmd)
				time.sleep(10)
				child = pexpect.spawn(command_line)
				child.logfile = open("temp2.txt", "wb")
			ind = child.expect(['login',pexpect.TIMEOUT, "mountroot>", 'IRQ Exception at 0x000000007F4A5440'],timeout = 2000)
			time.sleep(2)
			ok(ind == 0, "VM reboot passed")
			if(ind == 0):
				child.sendline('root')
				child.expect('root@freebsd:~ #', timeout = 1000)
				savecore_cmd = 'savecore /var/crash ' + dumpdev
				child.sendline(savecore_cmd)
				ok(child.after == b'root@freebsd:~ #',  "savecore passed")
				cmd = set_undump_cmd(config_vars, config_parameters)
				child.expect('root@freebsd:~ #',timeout = 1000)
				child.sendline('ls /var/crash/')
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
				time.sleep(20)
				child.close(force=True)
			elif(ind == 3):
				child.sendcontrol('C')
		if(parameter["architecture"] != "arm64"):
			pexpect.run("bhyvectl --destroy --vm=freebsd")
			time.sleep(2)
		count = count + 1
