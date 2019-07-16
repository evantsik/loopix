import os
import sys
current_path = os.getcwd()
print "Current path %s" % current_path
sys.path += [current_path]

from loopix_provider import LoopixProvider
from loopix_client import LoopixClient
from loopix_mixnode import LoopixMixNode
from twisted.internet import reactor
from twisted.application import service, internet
import petlib.pack
from sphinxmix.SphinxParams import SphinxParams


name = str(sys.argv[1])
i = int(sys.argv[2])
body = 57800
#recieving only 8192, lets fix it
#body = 1024
if name == 'client':
    secret = petlib.pack.decode(file("../example/secretClient%d.prv"%i, "rb").read())
    sec_params = SphinxParams(header_len=1024, body_len=body)
    try:
        data = file("../example/publicClient%d.bin"%i, "rb").read()
        _, name, port, host, _, prvinfo = petlib.pack.decode(data)

        client = LoopixClient(sec_params, name, port, host, provider_id = prvinfo, privk = secret)
        udp_server = internet.UDPServer(port, client)
        application = service.Application("Client")
        udp_server.setServiceParent(application)
        reactor.listenUDP(port, client, maxPacketSize=58855)
        reactor.run()

    except Exception, e:
        print str(e)

elif name == 'provider':
    secret = petlib.pack.decode(file("../example/secretProvider%d.prv"%i, "rb").read())
    _, name, port, host, _ = petlib.pack.decode(file("../example/publicProvider%d.bin"%i, "rb").read())
    sec_params = SphinxParams(header_len=1024, body_len=body)

    try:
        provider = LoopixProvider(sec_params, name, port, host, privk=secret, pubk=None)
        reactor.listenUDP(port, provider, maxPacketSize=58855)
        reactor.run()
        udp_server = internet.UDPServer(port, provider)
        application = service.Application("Provider")
        udp_server.setServiceParent(application)

    except Exception, e:
        print str(e)

elif name == 'mix':
    secret = petlib.pack.decode(file("../example/secretMixnode%d.prv"%i, "rb").read())
    sec_params = SphinxParams(header_len=1024, body_len=body)
    try:
        data = file("../example/publicMixnode%d.bin"%i, "rb").read()
        _, name, port, host, group, _ = petlib.pack.decode(data)
        mix = LoopixMixNode(sec_params, name, port, host, group, privk=secret, pubk=None)
        reactor.listenUDP(port, mix, maxPacketSize=58855)
        reactor.run()
        udp_server = internet.UDPServer(port, mix)
        application = service.Application("Mixnode")
        udp_server.setServiceParent(application)

    except Exception, e:
        print str(e)