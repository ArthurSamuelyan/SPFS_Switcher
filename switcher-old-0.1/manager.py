import ctypes
import socket
import os

class Manager:
    """Manager implements spfs-manager interface"""

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    manager  = "spfs-manager"
    work_dir = "./work-dir"
    log_dir  = "./log-dir"
    namespaces = ["pid"]

    def __init__(self, socket_path):
        """Start spfs-manager"""
        if os.path.exists("%s/%s" % (Manager.work_dir, socket_path)):
            os.remove("%s/%s" % (Manager.work_dir, socket_path))

        pid = os.fork()
        if pid > 0:
            pid, status = os.waitpid(pid, 0)
        else:
            os.execvp(Manager.manager, [
                "spfs-manager",
                "-vvvv",
                "-d",
                "--socket-path", socket_path,
                "--work-dir",    Manager.work_dir,
                "--log-dir",     Manager.log_dir,
                "--exit-with-spfs"
            ])

        Manager.sock.connect("%s/%s" % (Manager.work_dir, socket_path))

    def __send_request(self, req_type, **kwargs):
        request = req_type
        for key in kwargs:
            request += "%s=%s;" % (key, kwargs[key])
        request += '\0'

        try:
            Manager.sock.send(request, socket.MSG_EOR)
            status = Manager.sock.recv(4)
            print status
            return 0

	except socket.timeout:
            Manager.sock.close()
            return -1

    def mount(self, **kwargs):
        mount = "mount;"
        self.__send_request(mount, **kwargs)

    def set_mode(self, **kwargs):
        req = "mode;"
        self.__send_request(req, **kwargs)

    def switch(self, **kwargs):
        req = "switch;"
        self.__send_request(req, **kwargs)
