from Queue import Queue
import random
import os
import petlib.pack
from processQueue import ProcessQueue
from client_core import ClientCore
from core import sample_from_exponential, group_layered_topology
from database_connect import DatabaseManager
from support_formats import Provider
from json_reader import JSONReader
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor, task, abstract
from twisted.python import log

import twisted.names.client
import cv2
import cPickle

class LoopixClient(DatagramProtocol):
    jsonReader = JSONReader(os.path.join(os.path.dirname(__file__), 'config.json'))
    config_params = jsonReader.get_client_config_params()
    output_buffer = Queue()
    process_queue = ProcessQueue()
    reactor = reactor
    resolvedAdrs = {}
    stream_length = 1000 #to chnage this consider adding more space to the body. 1 space for every digit
    stream_buffer = [None]*stream_length
    frames_received = 0
    frames_played = 0
    playing = False
    video_ended = False

    def __init__(self, sec_params, name, port, host, provider_id, privk=None, pubk=None):
        self.name = name
        self.port = port
        self.host = host
        self.privk = privk or sec_params.group.G.order().random()
        self.pubk = pubk or (self.privk * sec_params.group.G.generator())
        self.crypto_client = ClientCore((sec_params, self.config_params), self.name,
                                        self.port, self.host, self.privk, self.pubk)
        self.provider = Provider(name=provider_id)


    def startProtocol(self):
        log.msg("[%s] > Started" % self.name)
        self.get_network_info()
        self.get_provider_data()
        self.subscribe_to_provider()
        self.turn_on_packet_processing()
        self.make_loop_stream()
        self.make_drop_stream()
        self.make_real_stream()

    def get_network_info(self):
        self.dbManager = DatabaseManager(self.config_params.DATABASE_NAME)
        self.register_mixes(self.dbManager.select_all_mixnodes())
        self.register_providers(self.dbManager.select_all_providers())
        self.register_friends(self.dbManager.select_all_clients())
        self.provider = self.dbManager.select_provider_by_name(self.provider.name)
        log.msg("[%s] > Registered network information" % self.name)

    def get_provider_data(self):
        self.provider = self.dbManager.select_provider_by_name(self.provider.name)
        d = twisted.names.client.getHostByName(self.provider.host)
        d.addCallback(self.resolve_provider_address)

    def resolve_provider_address(self, result):
        self.provider = self.provider._replace(host = result)

    def subscribe_to_provider(self):
        lc = task.LoopingCall(self.send, ['SUBSCRIBE', self.name, self.host, self.port])
        lc.start(self.config_params.TIME_PULL, now=True)

    def register_mixes(self, mixes):
        self.pubs_mixes = group_layered_topology(mixes)

    def register_providers(self, providers):
        self.pubs_providers = providers

    def register_friends(self, clients):
        self.befriended_clients = clients

    def turn_on_packet_processing(self):
        self.retrieve_messages()
        self.reactor.callLater(20.0, self.get_and_addCallback, self.handle_packet)
        log.msg("[%s] > Turned on retrieving and processing of messages" % self.name)

    def retrieve_messages(self):
        lc = task.LoopingCall(self.send, ['PULL', self.name])
        lc.start(self.config_params.TIME_PULL, now=True)

    def get_and_addCallback(self, function):
        self.process_queue.get().addCallback(function)

    def datagramReceived(self, data, (host, port)):
        self.process_queue.put(data)

    def handle_packet(self, packet):
        self.read_packet(packet)
        try:
            self.reactor.callFromThread(self.get_and_addCallback, self.handle_packet)
        except Exception, exp:
            log.err("[%s] > Exception during scheduling next get: %s" % (self.name, str(exp)))

    def read_packet(self, packet):
        decoded_packet = petlib.pack.decode(packet)
        if not decoded_packet[0] == 'DUMMY':
            flag, decrypted_packet = self.crypto_client.process_packet(decoded_packet)
            if decrypted_packet[:5] == "Video":
                self.add_frame_to_buffer(decrypted_packet)
                if (self.frames_received == 200 or self.video_ended == True) and self.playing == False:
                    #self.reactor.callInThread(self.play_video)
                    self.play_video()
            return (flag, decrypted_packet)

    def send_message(self, message, receiver):
        path = self.construct_full_path(receiver)
        header, body = self.crypto_client.pack_real_message(message, receiver, path)
        self.send((header, body))

    def send(self, packet):
        encoded_packet = petlib.pack.encode(packet)
        if abstract.isIPAddress(self.provider.host):
            self.transport.write(encoded_packet, (self.provider.host, self.provider.port))

    def schedule_next_call(self, param, method):
        interval = sample_from_exponential(param)
        self.reactor.callLater(interval, method)

    def make_loop_stream(self):
        log.msg("[%s] > Sending loop packet." % self.name)
        self.send_loop_message()
        self.schedule_next_call(self.config_params.EXP_PARAMS_LOOPS, self.make_loop_stream)

    def send_loop_message(self):
        path = self.construct_full_path(self)
        header, body = self.crypto_client.create_loop_message(path)
        self.send((header, body))

    def make_drop_stream(self):
        log.msg("[%s] > Sending drop packet." % self.name)
        self.send_drop_message()
        self.schedule_next_call(self.config_params.EXP_PARAMS_DROP, self.make_drop_stream)

    def send_drop_message(self):
        random_receiver = random.choice(self.befriended_clients)
        path = self.construct_full_path(random_receiver)
        header, body = self.crypto_client.create_drop_message(random_receiver, path)
        self.send((header, body))

    def make_real_stream(self):
        if not self.output_buffer.empty():
            log.msg("[%s] > Sending message from buffer." % self.name)
            packet = self.output_buffer.get()
            self.send(packet)
        else:
            log.msg("[%s] > Sending substituting drop message." % self.name)
            self.send_drop_message()
        self.schedule_next_call(self.config_params.EXP_PARAMS_PAYLOAD, self.make_real_stream)

    def construct_full_path(self, receiver):
        mix_chain = self.take_random_mix_chain()
        return [self.provider] + mix_chain + [receiver.provider] + [receiver]

    def take_random_mix_chain(self):
        mix_chain = []
        num_all_layers = len(self.pubs_mixes)
        for i in range(num_all_layers):
            mix = random.choice(self.pubs_mixes[i])
            mix_chain.append(mix)
        return mix_chain

    def stopProtocol(self):
        log.msg("[%s] > Stopped" % self.name)

    def send_frames(self, cap, receiver, path):
        i = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                message = "Video "+ "ended"
                header, body = self.crypto_client.pack_video_message(message, receiver, path)
                #self.output_buffer.put((header, body))
                self.send((header, body))
                break;

            frame = cv2.resize(frame, (160, 120))
            pickle_frame = cPickle.dumps(frame,protocol=cPickle.HIGHEST_PROTOCOL)
            #minimize i digits to 3 with mod 1000. 
            video_frame = "Video" + str(i%self.stream_length) + "pickle" + pickle_frame
            header, body = self.crypto_client.pack_video_message(video_frame, receiver, path)
            #self.output_buffer.put((header, body))
            self.send((header, body))#put in buffer
            i = i + 1

    def send_video(self, filename, receiver):
        cap = cv2.VideoCapture(filename)
        if not cap:
            log.msg("[%s] Error loading video file" % filename)
            return False

        path = self.construct_full_path(receiver)

        log.msg("Sending Video")
        self.send_frames(cap, receiver, path)
        log.msg("Video ended")

        cap.release()
    
    def play_video(self):
        self.playing = True
        while self.frames_received%self.stream_length != self.frames_played:
            video_frame = self.stream_buffer[self.frames_played]
            if video_frame == None:#missing frame
                self.frames_played = (self.frames_played + 1)%self.stream_length
                continue

            self.stream_buffer[self.frames_played] = None
            self.frames_played = (self.frames_played + 1)%self.stream_length

            frame = cPickle.loads(video_frame)
            frame = cv2.resize(frame, (640, 480))
            cv2.imshow('frame',frame)
            if cv2.waitKey(50) & 0xFF == ord('q'):
                break

        self.playing = False

    def packet_to_indexed_frame(self, packet):
        pickle = packet.find("pickle",5,20)#faster find
        if pickle == -1:
            return None, None
        index = int(packet[5:pickle])
        video_frame = packet[pickle+6:]
        return video_frame, index  
        
    def add_frame_to_buffer(self, decrypted_packet):
        video_frame, index = self.packet_to_indexed_frame(decrypted_packet)
        if index == None:
            self.video_ended = True
        else:
            self.stream_buffer[index] = video_frame
            self.frames_received +=1
