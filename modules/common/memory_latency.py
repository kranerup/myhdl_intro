def memory_latency(input_flops, output_flops, divisor, wide=0, mport=0, merge=0):
    rlat = 1
    if wide or mport or merge: 
        if input_flops+output_flops>=divisor:
            # The overclocked memories have only a single cycle
            # of extra latency in the slow domain, even at 3cc 
            rlat += 1
    else:
        rlat += input_flops+output_flops
    print("Read latency", rlat, "divisor", divisor, "flops", input_flops+output_flops)
    return rlat
