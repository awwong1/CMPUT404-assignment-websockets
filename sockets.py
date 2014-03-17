#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle, Alexander Wong
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, render_template, make_response
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

class Client:
    def __init__(self):
        self.queue = queue.Queue()
    
    def put(self, value):
        self.queue.put_nowait(value)

    def get(self):
        return self.queue.get()

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

def set_listener(entity, value):
    '''
    do something with the update ! 
    '''
    message = json.dumps({entity: value})
    for client in clients:
        client.put(message)

myWorld = World()        
clients = list()
myWorld.add_set_listener( set_listener )
        
@app.route('/')
def hello():
    """
    Returns the template 'index.html'
    """
    return render_template("index.html")

def read_ws(ws,client):
    '''
    A greenlet function that reads from the websocket and updates the world
    '''
    while True:
        rawData = ws.receive()
        if rawData != None:
            values = json.loads(rawData)
            for key in values:
                myWorld.set(key, values[key])
        else:
            break
    return None

@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''
    Fufill the websocket URL of /subscribe, every update notify the
    websocket and read updates from the websocket
    '''
    client = Client()
    clients.append(client)
    
    event = gevent.spawn(read_ws, ws, client)
    try:
        while True:
            ws.send(client.get())
    except:
        pass
    finally:
        clients.remove(client)
        gevent.kill(event)

    return None


def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data != ''):
        return json.loads(request.data)
    else:
        return json.loads(request.form.keys()[0])

def flask_respond_json(data):
    response = make_response(json.dumps(data))
    response.headers['Content-Type']='application/json'
    return response

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''
    Update the entities
    '''
    update_values = flask_post_json(request);
    for k, v in update_values.iteritems():
        myWorld.update(entity, k, v)
    return flask_respond_json(myWorld.get(entity))    

@app.route("/world", methods=['POST','GET'])    
def world():
    '''
    Return the world
    '''
    return flask_respond_json(myWorld.world())

@app.route("/entity/<entity>")    
def get_entity(entity):
    '''
    This is the GET version of the entity interface,
    return a representation of the entity
    '''
    return flask_respond_json(myWorld.get(entity))


@app.route("/clear", methods=['POST','GET'])
def clear():
    '''
    Clear the world
    '''
    myWorld.clear()
    return flask_respond_json(myWorld.world())



if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
