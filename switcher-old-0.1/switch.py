#!/usr/bin/python
# -*- coding: UTF-8 -*-

import manager
import sys
import os
import argparse
import subprocess

def CreateParser():
    parser = argparse.ArgumentParser()
    parser.add_argument( '-p', '--pid', nargs='+', required=True )
    parser.add_argument( '-s', '--src', required=True )
    parser.add_argument( '-d', '--dst', required=True )
    return parser

def FreezerPath( freezer_name ):
    return "/sys/fs/cgroup/freezer/" + freezer_name

def TasksPath( freezer_name ):
    return FreezerPath( freezer_name ) + "/tasks"

def PutProcessesIntoFreezer( processes, freezer_name ):
    try:
        os.mkdir( FreezerPath( freezer_name ), 0755)
    except OSError:
        print freezer_name + " already exists!"
    else:
        print freezer_name + " created!"
    for _pid in processes:
        if os.path.exists( "/proc/" + _pid ):
            freezer_tasks = open( TasksPath( freezer_name ), 'a' )
            freezer_tasks.write( "%s\n" % ( _pid ) )
            try:
                freezer_tasks.close()
            except IOError:
                print( _pid + " [-]" )
            else:
                print( _pid + " [+]" )
        else:
            print( _pid + " [-]" )

def ParseTasks( freezer_name ):
    tasks_file = open( TasksPath( freezer_name ), 'r' )
    tasks = list()
    _pid = tasks_file.readline()
    while _pid:
        tasks.append( _pid[:-1] )
        _pid = tasks_file.readline()
    tasks_file.close()
    return tasks

def RsyncCall( abs_src, abs_dst ):
    proc = subprocess.Popen( "rsync -avzh %s/. %s" % ( abs_src, abs_dst ), shell=True, stdout=subprocess.PIPE )
    out = proc.communicate()

def FindMountPoint( abs_path ):
    while not os.path.ismount( abs_path ):
        abs_path = os.path.dirname( abs_path )
    return abs_path

def main():
    # preparing:

    parser = CreateParser()
    arguments = parser.parse_args( sys.argv[1:] )
    if( ( not os.path.isdir( arguments.src ) ) or ( not os.path.isdir( arguments.dst ) ) ):
        print( "Error: --src and --dst values must be directories!" )
        return
 
    print( arguments )

    freezer_name_a = "spfs_switcher_active"
    freezer_name_r = "spfs_switcher_retired" 

    abs_src = os.path.abspath( arguments.src )
    abs_dst = os.path.abspath( arguments.dst )

    mnt_src = FindMountPoint( abs_src )
    mnt_dst = FindMountPoint( abs_dst )

    if( mnt_src == mnt_dst ):
        print( "Error: --src and --dst directories must be on different mount points!" )
        return

    RsyncCall( abs_src, abs_dst )
    PutProcessesIntoFreezer( arguments.pid, freezer_name_a )
    RsyncCall( abs_src, abs_dst )

    mngr = manager.Manager("./control.sock")
    mngr.switch( source=abs_src, target=abs_dst, freeze_cgroup=FreezerPath( freezer_name_a ) )
    # mngr.mount(id=0, mountpoint="./mount-dir", mode="proxy", proxy_dir="./proxy-dir")

    PutProcessesIntoFreezer( ParseTasks( freezer_name_a ), freezer_name_r )


if __name__ == '__main__':
    main()
