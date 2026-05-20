#
# Used to test that run_test correctly handles various types of errors
# that can occur in a python test case.
#
import sys
import os

_,test_case = sys.argv[1].split('.')
test_case = test_case.replace('test_','')
if test_case != 'silent': print("testing fails tc:",test_case)

match test_case:
    case 'print-error':
        print("FAILED")
    case 'assert':
        assert False
    case 'exit':
        exit(2)
    case 'ok-no-msg':
        exit(0)
    case 'ok':
        print('Top test completed.')
        exit(0)
    case 'silent':
        exit(0)
    case 'kill':
        import signal
        os.kill(os.getpid(), signal.SIGKILL)
    case 'segv':
        import signal
        os.kill(os.getpid(), signal.SIGSEGV)
    case 'readonly':
        os.chmod(".", 0)
        for _ in range(1000000): print('---------------------------')
        exit(0)
    case other:
        print("there is no test named:",test_case)
        exit(2)
