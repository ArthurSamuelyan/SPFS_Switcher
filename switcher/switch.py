#!/usr/bin/python
# -*- coding: UTF-8 -*-

import manager
import sys
import os
import argparse
import subprocess

def FreezerPath( freezer_name ):
    return "/sys/fs/cgroup/freezer/" + freezer_name

def TasksPath( freezer_name ):
    return FreezerPath( freezer_name ) + "/tasks"

def ParseTasks( freezer_name ):
    tasks_file = open( TasksPath( freezer_name ), "r" )
    tasks = list()
    _pid = tasks_file.readline()
    while _pid:
        tasks.append( _pid[:-1] )
        _pid = tasks_file.readline()
    tasks_file.close()
    return tasks

def PutProcessesIntoFreezer( pids, freezer_name ):
    try:
        os.mkdir( FreezerPath( freezer_name ), 0755)
    except OSError:
        print "Freezer %s already exists!" % ( freezer_name )
    else:
        print "Freezer %s created!" % ( freezer_name )

    if len( pids ) == 0:
        return -1
    else:
        print "Putting processes into %s freezer:" % ( freezer_name )
        for _pid in pids:
            freezer_tasks = open( TasksPath( freezer_name ), "a" )
            freezer_tasks.write( "%s\n" % ( _pid ) )
            try:
                freezer_tasks.close()
            except IOError:
                print( _pid + " [-]" )
            else:
                print( _pid + " [+]" )
        if len( ParseTasks( freezer_name ) ) == 0:
            return -1
        else:
            return 0
        

def RsyncCall( abs_src, abs_dst ):
    proc = subprocess.Popen( "rsync -avzh %s/. %s" % ( abs_src, abs_dst ), shell=True, stdout=subprocess.PIPE )
    out = proc.communicate()

def FindMountPoint( abs_path ):
    while not os.path.ismount( abs_path ):
        abs_path = os.path.dirname( abs_path )
    return abs_path

def CheckTree( leaf, root ):
    leaf = os.path.abspath( leaf )
    root = os.path.abspath( root )
    while not leaf == "/":
        if leaf == root:
            return True
        leaf = os.path.dirname( leaf )
    if leaf == root:
        return True
    return False

def GetStatusString( pid, str_num ):
    status_file = "/proc/%s/status" % ( pid )
    if os.access( status_file, os.R_OK ):
        f = open( status_file, "r" )
        data = f.read()
        f.close()
        lines = data.split('\n')
        words = lines[ str_num ].split('\t')
        return words
    else:
        raise OSError


def CheckRoot( pid ): 
    try:
        words = GetStatusString( pid, 8 )
        if( words[ 1 ] == "0" ): # the process exists and is root
            return 0
        else: # process is non root
            return -1
    except OSError: # process does not exist
        return -2

def PickProcesses( pids, root_required=False ):
    chosen_pids = []
    rejected_pids = []
    for pid in pids:
        check = CheckRoot( pid )
        if check == 0 or ( check == -1 and not root_required ):
            chosen_pids.append( pid )
        else:
            rejected_pids.append( pid )
    # Print rejected PIDs:
    if len( rejected_pids ) > 0:
        print( "Theese PIDs are rejected, and will not be switched" )
        for r_pid in rejected_pids:
            print( r_pid + " [-]" )

    return chosen_pids



def CreateParser():
    parser = argparse.ArgumentParser()
    parser.add_argument( '-p', '--pid', nargs='+', required=True )
    parser.add_argument( '-s', '--src', required=True )
    parser.add_argument( '-d', '--dst', required=True )
    parser.add_argument( '-m', '--mnt', default="" )
    return parser

def main():
    # === Preparation: ====
    # Parse command line arguments:
    parser = CreateParser()
    arguments = parser.parse_args( sys.argv[1:] )
    if( ( not os.path.isdir( arguments.src ) ) or ( not os.path.isdir( arguments.dst ) ) ):
        print( "Error: --src and --dst values must be directories!" )
        return
    mntdefined = True
    if( arguments.mnt == "" ):
        mntdefined = False
    elif not os.path.isdir( arguments.mnt ):
        print( "Warning: --mnt argument is incorrect. Using work-dir/default-spfs-mnt instead." )
        mntdefined = False


    # We'll need two cgroups: spfs_switcher_active and spfs_switcher_retired
    # We'll give spfs_switcher_active controls to spfs-manager and it may freeze or unfreeze this cgroup
    # Because the only way to delete the process from a cgroup is to put it into another cgroup,
    # we'll create spfs_switcher_retired. This cgroup shall never be freezed. We'll put there processes from
    # spfs_switcher_active after unfreezing them via spfs-manager
    freezer_name_a = "spfs_switcher_active"
    freezer_name_r = "spfs_switcher_retired" 
    abs_src = os.path.abspath( arguments.src )
    abs_dst = os.path.abspath( arguments.dst )
    
    # Checking mount points. spfs-manager needs src and dst directories to be on different mount points.
    mnt_src = FindMountPoint( abs_src )
    mnt_dst = FindMountPoint( abs_dst )
    if( mnt_src == mnt_dst ):
        print( "Error: --src and --dst directories must be on different mount points!" )
        return

    if mntdefined:
        if CheckTree( leaf=abs_src, root=arguments.mnt ) or CheckTree( leaf=abs_dst, root=arguments.mnt ):
            print( "Warning: --mnt directory should not contain --src or --dst. Using work-dir/default-spfs-mnt instead." )
            mntdefined = False

    # Launching and preparing spfs-manager:
    mngr = manager.Manager( "./control.sock" )    # Shall we allow user to specify control socket location?
    if mntdefined:
        spfs_mnt = os.path.abspath( arguments.mnt )
    else:
        spfs_mnt = mngr.d_spfs_mnt
    # Mounting spfs into mnt_spfs on src directory:
    if mngr.mount( id=0, mountpoint=spfs_mnt, mode="proxy", proxy_dir=abs_src ) != 0:
        print "Failed to mount SPFS!"
        return
    # Creating spfs_switcher_active freezer cgroup and filling with given processes: 
    if PutProcessesIntoFreezer( PickProcesses( arguments.pid, root_required=(not mntdefined) ), freezer_name_a ) != 0:
        print "Nothing to switch!"
        return
    # Preliminary data syncing between src and dst (in order to speed up main data syncing): 
    print "Preliminary syncing started."
    RsyncCall( abs_src, abs_dst )
    # === Preparation complete. ===

    # === Switch: ===
    # 1: Switching processes src -> spfs-mnt:
    if mngr.switch( source=abs_src, target=spfs_mnt, freeze_cgroup=FreezerPath( freezer_name_a ) ) != 0:
	mngr.rollback()
        print "Switch aborted!"
        return

    # 2: Synchronize data:
    #    Freezing processes in cgroup:
    if mngr.set_mode( id=0, mode="stub" ) != 0:
	mngr.rollback()
        print "Switch aborted!"
        return

    #    Main data syncing:
    RsyncCall( abs_src, abs_dst )
    #    Unfreezing processes back:
    if mngr.set_mode( id=0, mode="proxy", proxy_dir=abs_src ) != 0: # was dst. Debug?
	mngr.rollback()
        print "Switch aborted!"
        return


    # 3: Switching processes spfs-mnt -> dst:
    if mngr.switch( source=spfs_mnt, target=abs_dst, freeze_cgroup=FreezerPath( freezer_name_a ) ) != 0:
	mngr.rollback()
        print "Switch aborted!"
        return

    # === Switch complete. ===

    # Cleaning spfs_switcher_active freezer:
    PutProcessesIntoFreezer( ParseTasks( freezer_name_a ), freezer_name_r )

    print "Switch complete!"


if __name__ == '__main__':
    main()
