# loopix
setup_exampledb.py:
create file "example" in the parent directory
python setup_exampledb.py 9999 '127.0.0.1' 'Mix1' 0 9998 '127.0.0.1' 'Mix2' 1 9997 '127.0.0.1' 'Mix3' 2
python setup_exampledb.py 9995 '127.0.0.1' 'Provider1' 9994 '127.0.0.1' 'Provider2'
python setup_exampledb.py 9993 '127.0.0.1' 'Client1' 'Provider1' 9992 '127.0.0.1' 'Client2' 'Provider2'

run_all.py:
python run_all.py mix 1
python run_all.py mix 2
python run_all.py mix 3
python run_all.py provider 1
python run_all.py provider 2
python run_all.py client 1
python run_all.py client 2