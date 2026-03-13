#! /usr/bin/python

# THE BEER-WARE LICENSE" (Revision 42):
# <xfguo@xfguo.org> wrote this file. As long as you retain this notice you
# can do whatever you want with this stuff. If we meet some day, and you think
# this stuff is worth it, you can buy me a beer in return Xiongfei(Alex) Guo.

'''
Created on 2010-4-23
Modified 2026-3-13

@author: Alex Guo
@author: Arman Barraghi
'''

import re
import sys
from pathlib import Path

class TestbenchGenerator(object):
    '''
    verilog test bench auto generation
    '''

    def __init__(self, vfile_name = None, ofile_name = None):
        self.vfile_name = vfile_name
        self.vfile = None
        self.ofile_name = ofile_name
        if(ofile_name == None):
            self.ofile = sys.stdout
        self.vcont = ""
        self.mod_name = ""
        self.pin_list = []
        self.clock_name = 'clk'
        self.reset_name = 'rst'
        
        if vfile_name == None:
            sys.stderr.write("ERROR: You haven't specfified an input file name.\n")
            sys.exit(1)
        else:
            self.open()
        self.parser()
        self.open_outputfile()

    def open(self, vfile_name = None):
        if vfile_name != None:
            self.vfile_name = vfile_name
            
        try:
            self.vfile = open(self.vfile_name, 'r')
            self.vcont = self.vfile.read() 
        except Exception as e:
            print ("ERROR: Open and read file error.\n ERROR:    %s" % e)
            sys.exit(1)
            
    def open_outputfile(self, ofile_name = None):
        try:
            # Determine the target output file path string
            target_name = None
            if ofile_name is not None:
                target_name = ofile_name
            elif self.ofile_name is not None:
                target_name = self.ofile_name
            else:
                target_name = "tb_%s.v" % self.mod_name
                print("You haven't specified an output file name, use '%s' instead." % target_name)
            
            if target_name != "tb_%s.v" % self.mod_name:
                 print("Output file is '%s'." % target_name)

            # Use pathlib to handle directory creation
            target_path = Path(target_name)
            
            # Create parent directories if they don't exist
            # parents=True allows creating nested directories (e.g., a/b/c)
            # exist_ok=True prevents errors if the directory is already there
            target_path.parent.mkdir(parents=True, exist_ok=True)

            self.ofile = open(target_path, 'w')

        except Exception as e:
            print ("ERROR: open and write output file error. \n ERROR:    %s" % e)
            sys.exit(1)
                
    def clean_other(self, cont):
        ## clean '// ...'
        cont = re.sub(r"//[^\n^\r]*", '\n', cont)
        ## clean '/* ... */'
        cont = re.sub(r"/\*.*\*/", '', cont)
        ## clean tables
        cont = re.sub(r'    +', ' ', cont)
        return cont
        
    def parser(self):
        print ("Parsing...")
        mod_pattern = r"module[\s]+(\S*)[\s]*\([^\)]*\)[\s\S]*"  
        
        module_result = re.findall(mod_pattern, self.clean_other(self.vcont))
        self.mod_name = module_result[0]
        
        self.parser_inoutput()
        self.find_clk_rst()
             
    def parser_inoutput(self):
        pin_list = self.clean_other(self.vcont) 
        
        comp_pin_list = []
        # Use lookahead to handle multiple signals per declaration and missing semicolons
        regex = r'(input|output|inout)\s+(.*?)(?=[;)]|\binput\b|\boutput\b|\binout\b|$)'
        
        for match in re.finditer(regex, pin_list, re.DOTALL):
            direction = match.group(1)
            body = match.group(2)
            
            # Extract optional range (e.g., [31:0])
            range_str = ""
            r_match = re.search(r'(\[[^\]]+\])', body)
            if r_match:
                range_str = r_match.group(1)
                body = body.replace(range_str, '')
                
            # Clean up 'reg' and 'wire' keywords
            body = re.sub(r'\b(reg|wire)\b', '', body)
            
            # Process each comma-separated signal
            for sig in body.split(','):
                sig = sig.strip()
                if not sig:
                    continue
                
                if direction == 'input':
                    type_name = 'reg'
                elif direction == 'output':
                    type_name = 'wire'
                elif direction == 'inout':
                    type_name = 'wire'
                else:
                    type_name = 'ERROR'

                comp_pin_list.append((direction, sig, range_str, type_name))
        
        self.pin_list = comp_pin_list
        
    def print_dut(self):
        max_len = 0
        for cpin_name in self.pin_list:
            pin_name = cpin_name[1]
            if len(pin_name) > max_len:
                max_len = len(pin_name)
        
        self.printo( "%s uut (\n" % self.mod_name )
        
        align_cont = self.align_print(list(map(lambda x:("", "." + x[1], "(", x[1], '),'), self.pin_list)), 4)
        align_cont = align_cont[:-2] + "\n"
        self.printo( align_cont )
        
        self.printo( ");\n" )
        
    def print_wires(self):
        self.printo(self.align_print(list(map(lambda x:(x[3], x[2], x[1], ';'), self.pin_list)), 4))
        self.printo("\n")
    
    def print_clock_gen(self):
        fsdb = "    $dumpfile(\"db_tb_%s.vcd\");\n    $dumpvars(0, tb_%s);\n" % (self.mod_name, self.mod_name)

        clock_gen_text = "\nparameter PERIOD = 10;\n\ninitial begin\n%s    CLK = 1'b0;\n    #(PERIOD/2);\n    forever\n        #(PERIOD/2) CLK = ~CLK;\nend\n\n" % fsdb
        self.printo(re.sub('CLK', self.clock_name, clock_gen_text))
        
    def find_clk_rst(self):
        for pin in self.pin_list:
            if re.match(r'[\S]*(clk|clock)[\S]*', pin[1]):
                self.clock_name = pin[1]
                print ("I think your clock signal is '%s'." % pin[1])
                break

        for pin in self.pin_list:
            if re.match(r'rst|reset', pin[1]):
                self.reset_name = pin[1]
                print ("I think your reset signal is '%s'." % pin[1])
                break

    def print_module_head(self):
        cur_dir = Path(self.vfile_name).resolve()
        #print(cur_dir)
        root_dir = Path(re.search(r'[\w/]*uArch_x86_proj', str(cur_dir)).group())
        #print(root_dir)
        rel_path = cur_dir.relative_to(root_dir)
        #print(rel_path)
        self.printo("`timescale 1ns / 1ps\n`include \"%s\"\nmodule tb_%s;\n\n" % (str(rel_path), self.mod_name))
        
    def print_module_end(self):
        self.printo("endmodule\n")

    def printo(self, cont):
        self.ofile.write(cont)

    def close(self):
        if self.vfile != None:
            self.vfile.close()
        print ("Output finished.\n\n")

    def align_print(self, content, indent):
        """ Align pretty print."""

        row_len = len(content)
        col_len = len(content[0])
        align_cont = [""] * row_len
        for i in range(col_len):
            col = list(map(lambda x:x[i], content))
            max_len = max(map(len, col), default=0)
            for i in range(row_len):
                l = len(col[i])
                align_cont[i] += "%s%s" % (col[i], (indent + max_len - l) * ' ')
        
        # remove space in line end
        align_cont = map(lambda s:re.sub('[ ]*$', '', s), align_cont)
        return "\n".join(align_cont) + "\n"
        

if __name__ == "__main__":
    print ('''***************** tbgen - Auto generate a testbench. *****************
Author: Xiongfei(Alex) Guo <xfguo@credosemi.com>
Author: Arman Barraghi <abarraghi@gmail.com>
License: Beerware
''')
    ofile_name = None
    if len(sys.argv) == 1:
        sys.stderr.write("ERROR: You haven't specified an input file name.\n")
        print ("Usage: tbgen <input_verilog_file_path> [<output_testbench_file_path>]")
        sys.exit(1)
    elif len(sys.argv) == 3:
        ofile_name = sys.argv[2]
        
    tbg = TestbenchGenerator(sys.argv[1], ofile_name)

    tbg.print_module_head()
    tbg.print_wires()
    tbg.print_dut()
    tbg.print_clock_gen()
    tbg.print_module_end()
    tbg.close()
