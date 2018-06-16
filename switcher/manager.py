import ctypes
import socket
import sys, os
import codecs
import signal, psutil

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


    #def __socket_path( self ):
    #    return "%s/%s" % ( self.work_dir, self.socket_file )

    def __init__( self, new_socket_file ):

        # TODO: rewrite using "os.join"
        self.manager  = "spfs-manager"
        self.swd = os.path.join( os.getcwd(), "work-dir" ) # SWD = Switcher Work Directory
        self.work_dir = os.path.join( self.swd, "manager-work-dir" )
        self.spfs_mnt = os.path.join( self.swd, "spfs-mnt" )
        self.log_dir  = "log-dir"
        self.socket_file = "control.sock"
        self.socket_path = os.path.join( self.work_dir, self.socket_file )
        self.history = [] # NEW FEATURE

        # Refreshing wokr-dir:
	if( os.access( self.swd, os.F_OK ) ):
	    DestroyDirectory( self.swd )

        if( os.path.exists( self.swd ) ):
            print "Failed to clean switcher work directory!"
            sys.exit()
        
        os.mkdir( self.swd, 0755 )

        os.mkdir( self.work_dir, 0755 )
        self.work_dir = os.path.abspath( self.work_dir )

        os.mkdir( self.spfs_mnt, 0755 )
        self.spfs_mnt = os.path.abspath( self.spfs_mnt )
        # ===================

        print "SPFS manager socket: " + self.socket_path

        #if os.path.exists( self.socket_path ):
        #    os.remove( self.socket_path )

        pid = os.fork()
        if pid > 0:
            pid, status = os.waitpid(pid, 0)
        else:
            # shall we use subprocess here?
            os.execvp( self.manager, [
                "spfs-manager",
                "-vvvv",
                "-d",
                "--socket-path", self.socket_file, # relative
                "--work-dir",    self.work_dir,
                "--log-dir",     self.log_dir, # relative
                "--exit-with-spfs"
            ] )

    def __send_premade_request( self, req_type, request ):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.sock.connect( self.socket_path )
        try:
            self.sock.send( request, socket.MSG_EOR )
            status_str = self.sock.recv(4)
            status = int( codecs.encode( status_str, 'hex'), 16 )
            print( "SPFS manager: %s status %d." % ( req_type, status ) )
            self.sock.close()
            if status == 0:
                return 0
            else:
                return 1
	except socket.timeout:
            self.sock.close()
            return -1

    def __send_request( self, req_type, **kwargs ):
        history_string = [] # NEW FEATURE
        history_string.append( req_type ) #
        history_string.append( kwargs ) #
        self.history.append( history_string ) #

        request = req_type
        for key in kwargs:
            request += "%s=%s;" % (key, kwargs[key])
        request += '\0'
        return self.__send_premade_request( req_type, request )

    def mount( self, **kwargs ):
        req = "mount;"
	return self.__send_request( req, **kwargs )

    def set_mode( self, **kwargs ):
        req = "mode;"
        return self.__send_request( req, **kwargs )

    def switch( self, **kwargs ):
        req = "switch;"
        return self.__send_request( req, **kwargs )

    def rollback( self ):
        print "Rollback started."
        self.history.reverse()
        if self.history[ 0 ][ 0 ] == "mode;":
            print "\"mode\" rollback was not provided :("
        for h_line in self.history[ 1: ]: # the last command was failure, we don't reverse it
            if h_line[ 0 ] == "switch;":
                request = "switch;source=%s;target=%s;freeze_cgroup=%s;\0" % ( h_line[ 1 ][ "target" ], h_line[ 1 ][ "source" ], h_line[ 1 ][ "freeze_cgroup" ] )
                if self.__send_premade_request( h_line[ 0 ], request ) != 0:
                    print "Rollback failed!"
                    return -1
        print "Rollback completed."
        return 0;
