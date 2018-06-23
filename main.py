'''
Designs do not use constrianed I/O
Therefore they do not target a real dev board
Spit out JSON for easy result aggregation

Configurations of interest:
-yosys, icestorm
-yosys, vpr
-vendor, icecube
-yosys, icecube
-radiant?

Tested with one or two devices
-The largest device (8k)

Designs:
-SoC
-NES?
-LED blinky

Versions tested with
Radiant: 1.0 64-bit for Linux
Icecube: iCEcube2 2017-08 for Linux
'''

import os
import subprocess
import time
import collections
import json
import re
import sys
import glob

class Timed():
    def __init__(self, t, name):
        self.t = t
        self.name = name
        self.start = None

    def __enter__(self):
        self.start = time.time()

    def __exit__(self, type, value, traceback):
        end = time.time()
        self.t.add_runtime(self.name, end - self.start)

# couldn't get icestorm version
# filed https://github.com/cliffordwolf/icestorm/issues/163
def yosys_ver():
    # Yosys 0.7+352 (git sha1 baddb017, clang 3.8.1-24 -fPIC -Os)
    return subprocess.check_output("yosys -V", shell=True, universal_newlines=True).strip()

class Toolchain:
    def __init__(self):
        self.runtimes = collections.OrderedDict()
        self.toolchain = None
        self.verbose = False

        self.family = None
        self.device = None

        self.project_name = None
        self.srcs = None
        self.top = None
        self.out_dir = None

        with Timed(self, 'nop'):
            subprocess.check_call("true", shell=True, cwd=self.out_dir)

    def add_runtime(self, name, dt):
        self.runtimes[name] = dt

    def project(self, name, family, device, srcs, top, out_dir):
        self.family = family
        self.device = device

        self.project_name = name
        self.srcs = srcs
        self.top = top
        self.out_dir = out_dir

    def cmd(self, cmd, argstr):
        print("Running: %s %s" % (cmd, argstr))
        open("%s/%s.txt" % (self.out_dir, cmd), "w").write("Running: %s %s\n\n" % (cmd, argstr))
        with Timed(self, cmd):
            if self.verbose:
                subprocess.check_call("(%s %s) |&tee -a %s.txt; (exit $PIPESTATUS )" % (cmd, argstr, cmd), shell=True, cwd=self.out_dir)
            else:
                subprocess.check_call("(%s %s) >& %s.txt" % (cmd, argstr, cmd), shell=True, cwd=self.out_dir)

def icetime_parse(f):
    ret = {
        }
    for l in f:
        # Total path delay: 8.05 ns (124.28 MHz)
        m = re.match(r'Total path delay: .*s \((.*) (.*)\)', l)
        if m:
            assert m.group(2) == 'MHz'
            ret['max_freq'] = float(m.group(1)) * 1e6
    return ret

def icebox_stat(fn, out_dir):
    subprocess.check_call("icebox_stat %s >icebox_stat.txt" % fn, shell=True, cwd=out_dir)
    '''
    DFFs:     22
    LUTs:     24
    CARRYs:   20
    BRAMs:     0
    IOBs:      4
    PLLs:      0
    GLBs:      1
    '''
    ret = {}
    for l in open(out_dir + "/icebox_stat.txt"):
        # DFFs:     22
        m = re.match(r'(.*)s: *([0-9]*)', l)
        t = m.group(1)
        n = int(m.group(2))
        ret[t] = n
    assert 'LUT' in ret
    return ret

class Arachne(Toolchain):
    def __init__(self):
        Toolchain.__init__(self)
        self.toolchain = 'arachne'

    def yosys(self):
        yscript = "synth_ice40 -top %s -blif my.blif" % self.top
        self.cmd("yosys", "-p '%s' %s" % (yscript, ' '.join(self.srcs)))

    def run(self):
        with Timed(self, 'bit-all'):
            self.yosys()
            self.cmd("arachne-pnr", "-d 8k -P cm81 -o my.asc my.blif")
            self.cmd("icepack", "my.asc my.bin")

        self.cmd("icetime", "-tmd hx8k my.asc")

    def max_freq(self):
        return icetime_parse(open(self.out_dir + '/icetime.txt'))['max_freq']

    def resources(self):
        return icebox_stat("my.asc", self.out_dir)

    @staticmethod
    def arachne_version():
        '''
        $ arachne-pnr -v
        arachne-pnr 0.1+203+0 (git sha1 7e135ed, g++ 4.8.4-2ubuntu1~14.04.3 -O2)
        '''
        return subprocess.check_output("arachne-pnr -v", shell=True, universal_newlines=True).strip()

    def versions(self):
        return {
            'yosys': yosys_ver(),
            'arachne': Arachne.arachne_version(),
            }

class VPR(Toolchain):
    def __init__(self):
        Toolchain.__init__(self)
        self.toolchain = 'vpr'
        self.sfad_build = os.getenv("HOME") + "/symbiflow-arch-defs/tests/build/ice40-top-routing-virt-hx8k"

    def yosys(self):
        yscript = "synth_ice40 -top %s -nocarry; ice40_opt -unlut; abc -lut 4; opt_clean; write_blif -attr -cname -param my.eblif" % self.top
        self.cmd("yosys", "-p '%s' %s" % (yscript, ' '.join(self.srcs)))

    def run(self):
        with Timed(self, 'bit-all'):
            self.yosys()

            arch_xml = self.sfad_build + '/arch.xml'
            rr_graph = self.sfad_build + "/rr_graph.real.xml"
            # --fix_pins " + io_place
            #io_place = ".../symbiflow-arch-defs/tests/ice40/tiny-b2_blink//build-ice40-top-routing-virt-hx8k/io.place"
            self.cmd("vpr", arch_xml + " my.eblif --device hx8k-cm81 --min_route_chan_width_hint 100 --route_chan_width 100 --read_rr_graph " + rr_graph + " --debug_clustering on --pack --place --route")

            self.cmd("icebox_hlc2asc.py", "top.hlc > my.asc")
            self.cmd("icepack", "my.asc my.bin")

        self.cmd("icetime", "-tmd hx8k my.asc")

    def max_freq(self):
        return icetime_parse(open(self.out_dir + '/icetime.txt'))['max_freq']

    """
    @staticmethod
    def resource_parse(f):
        '''
        abanonded in favor of icebox_stat
        although maybe would be good to compare results?

        Resource usage...
            Netlist      0    blocks of type: EMPTY
            Architecture 0    blocks of type: EMPTY
            Netlist      4    blocks of type: BLK_TL-PLB
            Architecture 960    blocks of type: BLK_TL-PLB
            Netlist      0    blocks of type: BLK_TL-RAM
            Architecture 32    blocks of type: BLK_TL-RAM
            Netlist      2    blocks of type: BLK_TL-PIO
            Architecture 256    blocks of type: BLK_TL-PIO

        Device Utilization: 0.00 (target 1.00)
            Block Utilization: 0.00 Type: EMPTY
            Block Utilization: 0.00 Type: BLK_TL-PLB
            Block Utilization: 0.00 Type: BLK_TL-RAM
            Block Utilization: 0.01 Type: BLK_TL-PIO
        '''
        def waitfor(s):
            while True:
                l = f.readline()
                if not l:
                    raise Exception("EOF")
                if s.find(s) >= 0:
                    return
        waitfor('Resource usage...')
        while True:
            l = f.readline().strip()
            if not l:
                break
            # Netlist      2    blocks of type: BLK_TL-PIO
            # Architecture 256    blocks of type: BLK_TL-PIO
            parts = l.split()
            if parts[0] != 'Netlist':
                continue

        waitfor('Device Utilization: ')
    """

    def resources(self):
        return icebox_stat("my.asc", self.out_dir)

    @staticmethod
    def vpr_version():
        '''
        vpr  --version

        VPR FPGA Placement and Routing.
        Version: 8.0.0-dev+vpr-7.0.5-6027-g94a747729
        Revision: vpr-7.0.5-6027-g94a747729
        Compiled: 2018-06-21T16:45:11 (release build)
        Compiler: GNU 6.3.0 on Linux-4.9.0-5-amd64 x86_64
        University of Toronto
        vtr-users@googlegroups.com
        This is free open source code under MIT license.
        '''
        out = subprocess.check_output("vpr --version", shell=True, universal_newlines=True).strip()
        version = None
        revision = None
        for l in out.split('\n'):
            l = l.strip()
            if l.find('Version:') == 0:
                version = l
            if l.find('Revision:') == 0:
                revision = l
        assert version is not None
        assert revision is not None
        return version + ', ' + revision

    def versions(self):
        return {
            'yosys': yosys_ver(),
            'vpr': VPR.vpr_version(),
            }

def print_stats(t):
    s = t.family + '-' + t.device + '_' + t.toolchain + '_' + t.project_name
    print('Timing (%s)' % s)
    for k, v in t.runtimes.items():
        print('  % -16s %0.3f' % (k + ':', v))
    print('Max frequency: %0.3f MHz' % (t.max_freq() / 1e6,))
    print('Resource utilization')
    for k, v in sorted(t.resources().items()):
        print('  %- 20s %s' % (k + ':', v))

def write_metadata(t, out_dir):
    j = {
        'toolchain': t.toolchain,
        'family': t.family,
        'device': t.device,
        'project_name': t.project_name,
        # canonicalize
        'sources': [x.replace(os.getcwd(), '.') for x in t.srcs],
        'top': t.top,

        "runtime": t.runtimes,
        "max_freq": t.max_freq(),
        "resources": t.resources(),
        "verions": t.versions(),
        }
    json.dump(j, open(out_dir + '/meta.json', 'w'), sort_keys=True, indent=4)

def get_project(name):
    cwd = os.getcwd()

    projects = [
        {
        'srcs': [cwd + '/src/blinky.v'],
        'top': 'top',
        'name': 'blinky',
        },
    ]

    #srcs = filter(lambda x: x.find('_tb.v') < 0 and 'spiflash.v' not in x, glob.glob(cwd + "/src/picorv32/picosoc/*.v"))
    d = cwd + "/src/picorv32/"
    srcs = [
        d + "picosoc/picosoc.v",
        d + "picorv32.v",
        d + "picosoc/spimemio.v",
        d + "picosoc/simpleuart.v",
        d + "picosoc/hx8kdemo.v",
        ]
    projects.append({
        'srcs': srcs,
        'top': 'hx8kdemo',
        'name': 'picosoc-hx8kdemo',
        })

    projects = dict([(p['name'], p) for p in projects])
    return projects[name]

def run(family, device, toolchain, project, out_dir, verbose=False):
    assert family == 'ice40'
    assert device == 'hx8k'

    t = {
        'arachne': Arachne,
        'vpr': VPR,
        #'radiant': VPR,
        #'icecube': VPR,
        }[toolchain]()
    t.verbose = verbose

    if out_dir is None:
        out_dir = "build/" + family + '-' + device + '_' + toolchain + '_' + project
    if not os.path.exists("build"):
        os.mkdir("build")
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)
    print('Writing to %s' % out_dir)

    p = get_project(project)
    t.project(p['name'], family, device, p['srcs'], p['top'], out_dir)

    t.run()
    print_stats(t)
    write_metadata(t, out_dir)

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description=
        'Analyze tool runtimes'
    )

    parser.add_argument('--verbose', action='store_true', help='')
    parser.add_argument('--overwrite', action='store_true', help='')
    parser.add_argument('--family', default='ice40', help='Device family')
    parser.add_argument('--device', default='hx8k', help='Device')
    parser.add_argument('--toolchain', required=True, help='Tools to use')
    parser.add_argument('--project', required=True, help='Source code to run on')
    parser.add_argument('--out-dir', default=None, help='Output directory')
    args = parser.parse_args()

    run(args.family, args.device, args.toolchain, args.project, args.out_dir, verbose=args.verbose)

if __name__ == '__main__':
    main()