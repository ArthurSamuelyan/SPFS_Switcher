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
    # ===Preparation:==================================================================================
    # ===Parse command line arguments:
    parser = CreateParser()
    arguments = parser.parse_args( sys.argv[1:] )
    if( ( not os.path.isdir( arguments.src ) ) or ( not os.path.isdir( arguments.dst ) ) ):
        print( "Error: --src and --dst values must be directories!" )
        return
 
    print( arguments ) # debug

    # ===We'll need two cgroups: spfs_switcher_active and spfs_switcher_retired
    # ===We'll give spfs_switcher_active controls to spfs-manager and it may freeze or unfreeze this cgroup
    # ===Because the only way to delete the process from a cgroup is to put it into another cgroup,
    # ===we'll create spfs_switcher_retired. This cgroup shall never be freezed. We'll put there processes from
    # ===spfs_switcher_active after unfreezing them via spfs-manager
    freezer_name_a = "spfs_switcher_active"
    freezer_name_r = "spfs_switcher_retired" 
    abs_src = os.path.abspath( arguments.src )
    abs_dst = os.path.abspath( arguments.dst )
    
    # ===Checking mount points. spfs-manager needs src and dst directories to be on different mount points.
    mnt_src = FindMountPoint( abs_src )
    mnt_dst = FindMountPoint( abs_dst )
    if( mnt_src == mnt_dst ):
        print( "Error: --src and --dst directories must be on different mount points!" )
        return

    # ===Launching and preparing spfs-manager:
    mngr = manager.Manager( "./control.sock" )    # Shall we allow user to specify control socket location?

    mnt_spfs = mngr.work_dir_path + "/spfs-mnt"   # Shall we allow user to specify mnt directory?
    try:
        os.mkdir( mnt_spfs, 0755 )
    except OSError:
        print( mnt_spfs + " already exists." )

    mnt_spfs = os.path.abspath( mnt_spfs )

    # ===Mounting spfs into mnt_spfs on src directory:
    mngr.mount( id=0, mountpoint=mnt_spfs, mode="proxy", proxy_dir=abs_src )
    # ===Creating spfs_switcher_active freezer cgroup and filling with given processes: 
    PutProcessesIntoFreezer( arguments.pid, freezer_name_a )
    # ===Preliminary data syncing between src and dst (in order to speed up main data syncing): 
    RsyncCall( abs_src, abs_dst )
    # ===Preparation complete.=========================================================================

    # ===Switch:=======================================================================================
    # ===1: Switching processes src -> mnt_spfs:
    mngr.switch( source=abs_src, target=mnt_spfs, freeze_cgroup=FreezerPath( freezer_name_a ) )

    # ===2: Synchronize data:
    # ===   Freezing processes in cgroup:
    mngr.set_mode( id=0, mode="stub" )
    # ===   Main data syncing:
    RsyncCall( abs_src, abs_dst )
    # ===   Unfreezing processes back:
    mngr.set_mode( id=0, mode="proxy", proxy_dir=abs_dst )

    # ===3: Switching processes mnt_spfs -> dst:
    mngr.switch( source=mnt_spfs, target=abs_dst, freeze_cgroup=FreezerPath( freezer_name_a ) )
    # ===Switch complete.==============================================================================

    # Cleaning spfs_switcher_active freezer:
    PutProcessesIntoFreezer( ParseTasks( freezer_name_a ), freezer_name_r )


if __name__ == '__main__':
    main()
