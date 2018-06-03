#!/usr/bin/python

import os
import sys

def main():
    while 1:
        print( "Test [ PID = %s :: RESOURCES = %s ]" % ( os.getpid(), os.path.abspath( '.' ) ) )
        text = sys.stdin.readline()
        if( text[ 0 ] == 's' ):
            break   

if __name__ == '__main__':
	main()
