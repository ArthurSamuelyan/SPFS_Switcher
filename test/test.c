#include <stdlib.h>
#include <stdio.h>

#define DATA_SRC "data"

int main() {
    FILE* data_src;
    char* data = (char*)malloc( 1024 );
    pid_t _pid = getpid();
    char a = ' ';
    while( a != 's' ) {
        data_src = fopen( DATA_SRC, "r" );
        if( data_src == NULL ) {
            printf( "Error: no \"%s\" file found!\n", DATA_SRC );
            return -1; 
        }
        fscanf( data_src, "%s", data );
        fclose( data_src );

        printf( "Process[ %lu ]: data[ %s ].\n", _pid, data );
        
        scanf( "%c", &a );
    }
    return 0;
}
