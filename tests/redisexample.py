import redis

# connect to Redis
server = redis.Redis(host="127.0.0.1", port=6379)

assert server.ping() is True
# should return True
server.delete('MyKey')

#assert len(server.keys()) == 0
# should return [] since we haven't added any keys yet

assert server.get('MyKey') is None
# should return nothing since we haven't added the key yet

assert server.set('MyKey', 'I love Python') is True
# should return True

assert server.keys()==[b'MyKey']
# should return [b'MyKey']

assert server.get('MyKey')==b'I love Python'
# should return "b'I love Python'"

assert server.delete('MyKey')==1
# should return 1 as success code

assert server.get('MyKey') is None
# should return nothing because we just deleted the key