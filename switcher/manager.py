import ctypes
import socket
import os
#import shutil
import codecs

def DestroyDirectory( dir_path ):
    for file_name in os.listdir( dir_path ):
        file_path = os.path.join( dir_path, file_name )
        # We need to unmount SPFS first 
        # in order not to harm it's proxy dir
        if os.path.ismount( file_path ):
            pid = os.fork()
            if pid > 0:
                pid, status = os.waitpid( pid, 0 ) 
            else:
                os.execvp( "umount", [ "umount", "-l", file_path ] )
        # Removing files recursively
        try:
            os.unlink( file_path )
        except OSError:
            DestroyDirectory( file_path )
    # Removing the directory itself
    os.rmdir( dir_path )

class Manager:
    """Manager implements spfs-manager interface"""


    def __socket_path( self ):
        return "%s/%s" % ( self.work_dir, self.socket_file )

    def __init__( self, new_socket_file ):

        self.manager  = "spfs-manager"
        self.work_dir = "./work-dir"
        self.spfs_mnt = self.work_dir + "/spfs-mnt"
        self.log_dir  = "log-dir"
        self.socket_file = "control.sock"

        self.namespaces = ["pid"]        # Do we need it?

        #============================== unmounting spfs ==
	#pid = os.fork()
        #if pid > 0:
        #    pid, status = os.waitpid( pid, 0 )
        #else:
        #    os.execvp( "umount", [ "-l", self.spfs_mnt ] )
        #=================================================

	if( os.access( self.work_dir, os.F_OK ) ):
	    DestroyDirectory( self.work_dir )

        #============================== creating directories =====
        try: # do we need here try/except ?
            os.mkdir( self.work_dir, 0755 )
        except OSError:
            print "Work directory already exists!"
        self.work_dir = os.path.abspath( self.work_dir )

	try:
            os.mkdir( self.spfs_mnt, 0755 )
        except OSError:
            print self.spfs_mnt + " alreadt exists!"
        self.spfs_mnt = os.path.abspath( self.spfs_mnt )
        #=========================================================

        print "Socket: " + self.__socket_path()

        self.socket_path = new_socket_file # ???
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
                "--work-dir",    self.work_dir,
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
            print( "Request %s status %d." % ( req_type, int( codecs.encode( status, 'hex'), 16 ) ) )
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
