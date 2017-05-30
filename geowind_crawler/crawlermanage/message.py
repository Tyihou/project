# -*- encoding: utf-8 -*-
import redis

'''
    消息发送订阅
    author:yangkui
'''
class Message(object):

    channels = []

    def __init__(self, host):
        self.host = host
        self.rc = redis.Redis(host=host)
        self.ps = self.rc.pubsub()

    def subscribe(self, channel):
        self.channels.append(channel)
        self.ps.subscribe(channel)

    def publish(self, subscriber, message):
        self.rc.publish(subscriber, message)

if __name__ == '__main__':
    message = Message('127.0.0.1')
    message.subscribe('crawler')
    message.subscribe('aaa')
    message.publish('crawler', 'op=stoptask&taskid=592ceac49c1da96d222995d9')