import ctypes
import socket
import os

class Manager:
    """Manager implements spfs-manager interface"""


    def __socket_path( self ):
        return "%s/%s" % ( self.work_dir_path, self.socket_file )

    def __init__( self, new_socket_file ):

        self.manager  = "spfs-manager"
        self.work_dir_path = "./work-dir"
        self.log_dir  = "log-dir"
        self.socket_file = "control.sock"

        self.namespaces = ["pid"]        # Do we need it?

        try:
            os.mkdir( self.work_dir_path, 0755 )
        except OSError:
            print "Work directory already exists!"
        self.work_dir_path = os.path.abspath( self.work_dir_path )

        print self.__socket_path()

        self.socket_path = new_socket_file
        if os.path.exists( self.__socket_path() ):
            os.remove( self.__socket_path() )

        pid = os.fork()
        if pid > 0:
            pid, status = os.waitpid(pid, 0)
        else:
            os.execvp( self.manager, [
                "spfs-manager",
                "-vvvv",
                "-d",
                "--socket-path", self.socket_file,
                "--work-dir",    self.work_dir_path,
                "--log-dir",     self.log_dir,
                "--exit-with-spfs"
            ] )


    def __send_request( self, req_type, **kwargs ):
        request = req_type
        for key in kwargs:
            request += "%s=%s;" % (key, kwargs[key])
        request += '\0'

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.sock.connect( self.__socket_path() )
        try:
            self.sock.send(request, socket.MSG_EOR)
            status = self.sock.recv(4)
            print status
            # print( "%u:%u:%u:%u" % ( status[ 0 ], status[ 1 ], status[ 2 ], status[ 3 ] )
            self.sock.close()
            return 0
	except socket.timeout:
            self.sock.close()
            return -1

    def mount( self, **kwargs ):
        req = "mount;"
        return self.__send_request( req, **kwargs )

    def set_mode( self, **kwargs ):
        req = "mode;"
        return self.__send_request( req, **kwargs )

    def switch( self, **kwargs ):
        req = "switch;"
        return self.__send_request( req, **kwargs )
