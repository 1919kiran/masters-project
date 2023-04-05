import time
import threading
from multiprocessing import Process, Pool, Queue

import pika
from sharedqueue import SharedQueue
import queue


class Node(threading.Thread):
    def __init__(self, node_id, fileset):
        try:
            super().__init__()
            self.node_id = node_id
            self.fileset = fileset
            self.max_capacity = 10
            self.request_amount = 0
            self.forwarding_bandwidth = 0
            self.theta = 0.3
            self.phi = 0.8
            self.alpha = 70
            self.eps = 100
            self.accesses = []
            self.tcp_connection = []
            self.connection = None
            self.local_queue = SharedQueue()
            # self.tbdf_queue = []
            # self.storage = {}
        except Exception as e:
            print(f"Error while initializing Node{node_id}")

    def run(self):
        puller_thread = threading.Thread(target=self.pull_from_queue)
        processor_thread = threading.Thread(target=self.dequeue_from_local_queue)
        background_thread = threading.Thread(target=self.calculations)
        puller_thread.start()
        processor_thread.start()
        background_thread.start()

    def callback(self, ch, method, properties, body):
        self.local_queue.put(body)

    def pull_from_queue(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
        channel = self.connection.channel()
        for file in self.fileset:
            queue_name = f"queue_{file}"
            channel.queue_declare(queue=queue_name)
            channel.queue_bind(queue=queue_name, exchange="amq.direct", routing_key=queue_name)
            channel.basic_consume(queue=queue_name, auto_ack=True, on_message_callback=self.callback)
            print(f"Node{self.node_id} subscribed to {queue_name}")
        channel.start_consuming()

    def dequeue_from_local_queue(self):
        while True:
            try:
                self.local_queue.get()
                time.sleep(0.10)
            except Exception as e:
                continue

    def calculations(self):
        while True:
            # print(f"Node{self.node_id} access amount = {self.local_queue.qsize()}")
            # print(f"Node{self.node_id} node load = {self.calculate_node_load()}")
            print(f"Node{self.node_id} ohs = {self.calculate_overheating_similarity()}")
            time.sleep(5)

    def __str__(self):
        return f"Node ID is {self.node_id}\nFile set: {self.fileset}"

    def add_access(self, file_id, timestamp, frequency):
        self.accesses.append((file_id, timestamp, frequency))

    def calculate_weights(self):
        weights = {}
        current_time = time.time()
        for file_id, timestamp, frequency in self.accesses:
            time_diff = current_time - timestamp
            weight = frequency * pow(2, -time_diff / self.time_window)
            if file_id in weights:
                weights[file_id] += weight
            else:
                weights[file_id] = weight
        return weights

    def calculate_node_load(self):
        self.request_amount = self.local_queue.qsize() + self.forwarding_bandwidth
        return self.request_amount / self.max_capacity

    def calculate_overheating_similarity(self):
        q1 = self.calculate_node_load()
        overheating_similarity = (q1 - self.theta) / (
                self.phi - self.theta) if self.theta <= q1 <= self.phi else 0 if q1 < self.theta else 1
        return overheating_similarity

    def overheating_similarity_membership(self, curr_ohs):
        beta = 1
        print("beta ", beta)
        ohs_member = 100 // (1 + (1 / beta * pow((curr_ohs - self.phi), 2)))
        print("ohs member", ohs_member)
        return 1 if self.alpha <= ohs_member else 0

    def accept_input(self, filename):
        # self.request_queue.put(Request(filename))
        print("File Served", filename)  # background
        if filename in self.storage:
            self.storage[filename] += 1
        else:
            self.storage[filename] = 1
        self.tcp_connection.append(filename)
        self.local_files_access_amount += 1
        curr_ohs = self.calculate_overheating_similarity()
        print("curr ohs ", curr_ohs)
        self.ohsmap[self.node_id] = curr_ohs
        if curr_ohs > self.phi:
            print("Node Overloaded")
            print("___________")
            return
        if self.overheating_similarity_membership(curr_ohs):
            self.create_replica()
        else:
            print("Replica creation not required")
            print("___________")

    def build_priority_queue(self, filename, weight):
        print("Creating replica")
        self.weight_pq.put((weight, filename))

        print("___________")

    def create_replica(self):
        self.build_priority_queue()
