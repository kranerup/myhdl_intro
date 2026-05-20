"""
Create MyHDL struct from type database
"""

from myhdl import Struct, SignalType
from modules.common.signal import signal


def create_struct(data, flat_list = []):
    """
    Create MyHDL Struct from type database entry (from *_types.yml).
    myhdl.unpack_struct and myhdl.pack_struct can then be used to convert
    between the generated struct and flat bit-vectors.

    The data structure is assumed to be a dict:
    {
        "name": str
        "members": [
            {
                "hi": int,
                "lo": int,
                "name": str,
                "width": int,
            },
            ...
        ],
        "width": int,
    }

    """

    fields = {}
    match data:
        case {
            "name": str(_),
            "members": list(members),
            "width": int(width),
        }:
            totw = 0
            for m in members:
                match m:
                    case {
                        "hi": int(_),
                        "lo": int(lo),
                        "name": str(n),
                        "width": int(w),
                        "structure": dict(s),
                    }:
                        if n in flat_list:
                            fields[lo] = (n, w)
                        else:
                            ss = create_struct(s, flat_list)
                            fields[lo] = (n, ss)
                        totw += w
                    case {
                        "hi": int(_),
                        "lo": int(lo),
                        "name": str(n),
                        "width": int(w),
                    }:
                        fields[lo] = (n, w)
                        totw += w
                    case _:
                        raise TypeError(f"Malformed struct member: {m}")
            assert totw == width, f"totw={totw} width={width}"
        case _:
            raise TypeError(f"Expected dict, got {data}")

    class S(Struct):
        _fields = [fields[k] for k in (sorted(fields))]

        def __init__(self):
            for n, w in self._fields:
                if isinstance(w, int):
                    setattr(self, n, signal(w))
                else:
                    setattr(self, n, w())

        def names(self):

            return [ x
                     for x in vars(self)
                     if isinstance(vars(self)[x], (SignalType, Struct)) ]
            

    return S


    
def reg_to_struct( r ):
    """ Create MyHDL Struct from a simple register class 'reg'.
         This just creates a type dict compatible with create_struct
        so that function can be reused.
    """
    typedict = {}
    typedict['name'] = r.name
    typedict['members'] = []

    w = 0
    for idx,v in enumerate(r.fields):
        fd = { 'hi':0, 'lo':idx, 'name': v.name, 'width': v.bits }
        w += v.bits
        typedict['members'].append( fd ) 

    typedict['width'] = w
    t = create_struct( typedict )()
    return t

def reg_to_struct_type( r ):
    """ Create MyHDL Struct from a simple register class 'reg'.
         This just creates a type dict compatible with create_struct
        so that function can be reused.
    """
    typedict = {}
    typedict['name'] = r.name
    typedict['members'] = []

    w = 0
    for idx,v in enumerate(r.fields):
        fd = { 'hi':0, 'lo':idx, 'name': v.name, 'width': v.bits }
        w += v.bits
        typedict['members'].append( fd ) 

    typedict['width'] = w
    t = create_struct( typedict )
    return t

