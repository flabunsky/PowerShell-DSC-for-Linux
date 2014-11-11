#============================================================================
# Copyright (c) Microsoft Corporation. All rights reserved. See license.txt for license information.
#============================================================================
import os
import protocol
import socket
import struct
import sys
import traceback


DO_TRACE = True
DO_VERBOSE_TRACE  = False


def trace (text):
    if DO_TRACE:
        sys.stdout.write (text + '\n')

def verbose_trace (text):
    if DO_VERBOSE_TRACE:
        trace (text)

        
def read_uchar (fd):
    verbose_trace ('<read_uchar>')
    buf = fd.recv (1)
    if len (buf) < 1:
        return None
    val = struct.unpack ('@B',buf)[0]
    verbose_trace ('  val: '+str(int (val)))
    verbose_trace ('</read_uchar>')
    return val


def read_int (fd):
    verbose_trace ('<read_int>')
    buf = fd.recv (4)
    val = struct.unpack ('@i',buf)[0]
    verbose_trace ('  val: '+str(int (val)))
    verbose_trace ('</read_int>')
    return val


def read_string (fd):
    verbose_trace ('<read_string>')
    len = read_int (fd)
    verbose_trace ('  len: '+str(len))
    text = ''
    if 0 < len:
        buf = fd.recv (len)
        text = buf.decode ('utf8')
    verbose_trace ('  str: "'+text+'"')
    verbose_trace ('</read_string>')
    return text


def read_values (fd):
    verbose_trace ('<read_values>')
    d = dict ()
    argc = read_int (fd)
    verbose_trace ('  argc: '+str(argc))
    for i in range (argc):
        name = read_string (fd)
        # for python2.4x-2.5x unicode strings are illegal for **kwargs
        if sys.version < '2.6':
            arg_name = name.encode ('ascii','ignore')
        else:
            arg_name = name
        verbose_trace('  arg_name: "'+ arg_name+'"')
        arg_val = protocol.MI_Value.read (fd)
        d[arg_name] = arg_val
    verbose_trace ('</read_values>')
    return d


def read_request (fd):
    verbose_trace ('<read_request>')
    op_type = read_uchar (fd)
    if op_type == None:
        return None
    verbose_trace('  op_type: ' + str(op_type))
    op_name = read_string (fd)
    verbose_trace ('  op_name: "'+ op_name +'"')
    d = read_values (fd)
    verbose_trace ('</read_request>')
    return (op_type, op_name, d)

    
def write_int (fd, val):
    verbose_trace ('<write_int>')
    verbose_trace ('  val: '+str(val))
    buf = struct.pack ('@i', val)
    fd.send (buf)
    verbose_trace ('</write_int>')


def write_string (fd, st):
    verbose_trace ('<write_string>')
    verbose_trace ('  st: "'+ st + '"')
    verbose_trace (st)
    buf = struct.pack('@i', len (st))
    if type(buf) != str:
        buf += bytes (st,'utf8')
    else:
        buf += st
    fd.send (buf)
    verbose_trace ('</write_string>')


def write_dict (fd, d):
    verbose_trace ('<write_dict>')
    write_int (fd, len (d))
    verbose_trace ('  len: ' + str(len (d)))
    if sys.version > '2.9':
        for key, value in d.items ():
            trace ('  key: '+ key)
            if not hasattr(value,'value'):
                sys.stderr.write('\n  key: '+ key + ' is not mi_value\n' )
            trace ('  value: '+ str(value.value))
            if value.value is not None:
                write_string (fd, key)
                value.write (fd)
    else:
        for key, value in d.iteritems():
            trace ('  key: '+ key)
            trace ('  value: '+ str(value.value))
            if value.value is not None:
                write_string (fd, key)
                value.write (fd)
    verbose_trace ('</write_dict>')


def write_args (fd, args):
    verbose_trace ('<write_args>')
    if type (args) is dict:
        write_dict (fd, args)
    else:
        sys.stderr.write('write_args - was expecting dictionary for args!')
    verbose_trace ('</write_args>')


def write_success (fd, args = None):
    trace ('<write_success>')
    write_int (fd, 0)
    if args is not None:
        write_args (fd, args)
    trace ('</write_success>')


def write_failed (s, fail_code, text=''):
    trace ('<write_failed>')
    write_int (s, fail_code)
    write_string (s, text)
    trace ('</write_failed>')


def translate_input (d):
    """ This method is a convenience for a protocol chnage and should be
        removed when the handlers are updated."""
    verbose_trace ('<translate_input>')
    oldStyleD = dict ()
    if sys.version > '2':
        for key, value in d.items():
            oldStyleD[key] = value.value
    else:
        for key, value in d.iteritems():
            oldStyleD[key] = value.value
    verbose_trace ('</translate_input>')
    return oldStyleD


def callMOF (req):
    oldStyleDict = translate_input (req[2])
    trace ('MOF=' + repr ((req[0], req[1], oldStyleDict)))
    op = ('Test','Set','Get')
    if req[1] not in globals().keys():
        sys.stderr.write('Unable to find module: ' + md)
        return None
    the_module = globals ()[req[1]]
    method_name = op[req[0]] + '_Marshall'
    if not method_name in the_module.__dict__.keys():
        sys.stderr.write ('Unable to find method: ' + method_name)
        return None
    trace('calling '+ req[1] + '.' + method_name + ' ' + repr (oldStyleDict))
    ret = the_module.__dict__[method_name](**oldStyleDict)
    sys.stderr.write (repr(ret))
    return ret

    
def handle_request (fd, req):
    trace ('<handle_request>')
    r = callMOF (req)
    if len (r) < 2 :
        ret = None
        rval = r[0]
    else:
        rval = r[0]
        ret = r[1]
    if rval == 0:
        write_success (fd, ret)
    else:
        write_failed (fd, rval, 'Error occurred processing '+ repr (req))
    trace ('</handle_request>')



def main (argv):
    fd = socket.fromfd (int (argv[1]), socket.AF_UNIX, socket.SOCK_STREAM)
    read = 1
    out = ''
    while 0 < read:
        try:
            req = read_request (fd)
            if req == None:
                read = -1
            else:
                trace ('Main: request len is '+str(len (req)))
                handle_request (fd, req)
        except socket.error:
            read = -1;
            sys.stderr.write('exception encountered')

##############################
try:
    try:
        trace ('socket: '+str(sys.argv[1]))
        
        if 'OMI_HOME' in os.environ and len(os.environ['OMI_HOME']):
            omi_home=os.environ['OMI_HOME']
        else:
            omi_home='/opt/omi-1.0.8'
        if not os.path.isdir(omi_home):
            sys.stderr.write("omi home not found.  Please set OMI_HOME")
            sys.exit(1)
        pid_path=omi_home+'/var/run/python/'+repr(os.getuid())
        
        if not os.path.isdir(pid_path):
            os.system('mkdir -p ' + pid_path)
        pid_file=pid_path+'/dsc_python_client.pid'
        try:        
            F = open(pid_file,'w')
            F.write(str(os.getpid()) + "\n")
            F.flush()
            F.close()
        except:
             sys.stderr.write('Unable to create '+pid_file)
        trace ('using python version '+ sys.version) 
        sys.path.insert(0,'') # put the cwd in the path so we can find our module
        if sys.version < '2.6':
            trace ('/lib/Scripts/2.4x-2.5x')
            os.chdir(omi_home+'/lib/Scripts/2.4x-2.5x')
        elif sys.version < '3':
            trace ('/lib/Scripts/2.6x-2.7x')
            os.chdir(omi_home+'/lib/Scripts/2.6x-2.7x')
        else:
            trace ('/lib/Scripts/3.x')
            os.chdir (omi_home+'/lib/Scripts/3.x')
        from Scripts import *
        
        if __name__ == '__main__':
                main (sys.argv)
    
    
    except:
        sys.stderr.write ('\nException: ')
        sys.stderr.write (repr(sys.exc_info())+'\n')
        traceback.print_tb (sys.exc_info()[2])
        sys.stderr.write ('\n')

finally:
    sys.stderr.write ('Exiting - closing socket\n' )
    (socket.fromfd(int (sys.argv[1]), socket.AF_UNIX, socket.SOCK_STREAM)).close()
