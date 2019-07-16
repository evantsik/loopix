from database_connect import DatabaseManager
import sys
import core
import petlib.pack
import os.path
import sqlite3

if not os.path.isfile('../example/example.db'):
    dbManager = DatabaseManager('../example/example.db')
    dbManager.create_mixnodes_table('Mixnodes')
    dbManager.create_providers_table('Providers')
    dbManager.create_users_table('Users')

dbManager = DatabaseManager('../example/example.db')
#python setup_exampledb.py 9999 '127.0.0.1' 'Mix1' 0 9998 '127.0.0.1' 'Mix2' 1 9997 '127.0.0.1' 'Mix3' 2
def startMixes():
    for i in range(3):
        port = int(sys.argv[1 + (i*4)])
        host = sys.argv[2 + (i*4)]
        name = sys.argv[3 + (i*4)]
        group = int(sys.argv[4 + (i*4)])
        setup = core.setup()
        G, o, g, o_bytes = setup
        secret = o.random()
        file("../example/secretMixnode%d.prv"%(i+1), "wb").write(petlib.pack.encode(secret))
        pub = secret * g
        file("../example/publicMixnode%d.bin"%(i+1), "wb").write(petlib.pack.encode(["mixnode", name, port, host, group, pub]))
        dbManager.insert_row_into_table('Mixnodes',
                [None, name, port, host,
                sqlite3.Binary(petlib.pack.encode(pub)), group])

#python setup_exampledb.py 9995 '127.0.0.1' 'Provider1' 9994 '127.0.0.1' 'Provider2'
def startProviders():
    for i in range(2):
        port = int(sys.argv[1 + (i*3)])
        host = sys.argv[2 + (i*3)]
        name = sys.argv[3 + (i*3)]

        setup = core.setup()
        G, o, g, o_bytes = setup

        secret = o.random()
        file("../example/secretProvider%d.prv"%(i+1), "wb").write(petlib.pack.encode(secret))

        pub = secret * g
        file("../example/publicProvider%d.bin"%(i+1), "wb").write(petlib.pack.encode(["provider", name, port, host, pub]))
        dbManager.insert_row_into_table('Providers',
            [None, name, port, host,
            sqlite3.Binary(petlib.pack.encode(pub))])

#python setup_exampledb.py 9993 '127.0.0.1' 'Client1' 'Provider1' 9992 '127.0.0.1' 'Client2' 'Provider2'
def startClients():
    for i in range(2):
        port = int(sys.argv[1 + (i*4)])
        host = sys.argv[2 + (i*4)]
        name = sys.argv[3 + (i*4)]
        prvinfo = str(sys.argv[4 + (i*4)])

        setup = core.setup()
        G, o, g, o_bytes = setup

        secret = o.random()
        file("../example/secretClient%d.prv"%(i+1), "wb").write(petlib.pack.encode(secret))

        pub = secret * g
        file("../example/publicClient%d.bin"%(i+1), "wb").write(petlib.pack.encode(["client", name, port, host, pub, prvinfo]))
        dbManager.insert_row_into_table('Users',
            [None, name, port, host,
            sqlite3.Binary(petlib.pack.encode(pub)),
            prvinfo])


if(int(sys.argv[1])) == 9999:
    startMixes()
elif (int(sys.argv[1])) == 9995:
    startProviders()
elif (int(sys.argv[1])) == 9993:
    startClients()