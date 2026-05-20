from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator

# A MyHDL Struct is similar to an interface but it has helper
# functions that allows packing/unpacking the struct members
# to/from a single signal.
# A struct can also contain structs recursively.
class S(Struct):
    def __init__( self ):
        self.field_1 = signal(10)
        self.field_2 = signal(20)
        self.field_3 = signal()
        self.field_4 = signal(2)

# Here we want to assign to the structs members but then
# output a single signal that is the width of the sum of the members.
@module
def receiver(f1,f2,f3,f4,out):
    s = S()

    @always_comb
    def fieldassign():
        s.field_1.next = f1 
        s.field_2.next = f2 
        s.field_3.next = f3 
        s.field_4.next = f4 

    # Pack the struct members into a signal.
    ipack = pack_struct(s)
    iconn = pass_through(ipack,out) # assign to the output port

    return instances()

# Here we do the opposite. We receive a single signal that we
# want to access as a struct.
@module
def transmitter(insig,out):

    s = S()
    # Split the input signal into struct with its members,
    iunpack = unpack_struct( insig, s )

    @always_comb
    def unwrap():
        # Here we can now access the struct members.
        out.next = s.field_1 + s.field_2 + s.field_3 + s.field_4

    return instances()

def top(f1,f2,f3,f4,out):
    rec = copySignal(out)
    irec = receiver(f1,f2,f3,f4,rec)
    itr = transmitter(rec,out)
    return instances()

def generate_verilog():
    clk   = signal()
    reset = ResetSignal(0, active=0, isasync=False)
    s = S()
    out = signal(len(s))
    s1 = signal()
    s2 = signal()
    s3 = signal()
    s4 = signal()

    toVerilog.standard = 'systemverilog'
    itop = toVerilog( top, s1, s2, s3, s4, out )

if __name__ == "__main__":
    generate_verilog()
