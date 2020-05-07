#!/usr/bin/env python3
from aiohttp import web
from multidict import CIMultiDict
import asyncio
import argparse
import redis
import responses

async def bitmask_ip(ip_bytes, mask_bytes):
	raw_bytes = [str(i&j) for i,j in zip(ip_bytes, mask_bytes)]
	return '.'.join(raw_bytes)

async def validate_ip(ip: str):
	try:
		byte_list = ip.split('.')
		if len(byte_list) != 4:
			return False

		for byte in byte_list:
			if len(byte)>3 or len(byte)<1 or int(byte)>255 or int(byte)<0:
				return False
	except Exception:
		return False

	return map(int, byte_list)

async def content_handler(request):
	_body = request.app['html_body_200']
	return web.HTTPOk(body = str(_body), content_type = 'text/html')

async def reset_timeout_handler(request):
	try:
		key = request.query['key']
		ip  = request.query['ip']
	except KeyError:
		raise web.HTTPBadRequest(text = "Provide subnet prefix "
								"(or ip from specific subnet) "
								"and secret key to reset timeout. "
								"Ex.: /reset_timeout?key=foo&ip=1.2.3.4")
	# validating secret key
	if key != request.app['secret_key']:
		raise web.HTTPBadRequest(text = "Unauthorized")

	# validating given prefix/ip
	prefix = await validate_ip(ip)
	if prefix == False:
		raise web.HTTPBadRequest(text = "You should provide valid prefix/ip")
	
	# got valid prefix and valid secret key
	masked_prefix = await bitmask_ip(prefix, request.app['mask'])
	REDIS_TIMEOUT = request.app['timeout_db']

	if masked_prefix in REDIS_TIMEOUT:
		del REDIS_TIMEOUT[masked_prefix]
		return web.HTTPOk(text = "OK")
	else:
		raise web.HTTPBadRequest(text = "Provided prefix isn't timed out")

@web.middleware
async def ip_checkpoint(request, handler):
	# processing cases with only 1 ip address provided
	try:
		_ip = request.headers['X-Forwarded-For']
		request_ip = await validate_ip(_ip)
		if request_ip == False:
			raise web.HTTPBadRequest(text = f"Bad ip provided in header: {_ip}")
	except KeyError:
		print("Got header without forwarded ip")
		ans = "Can't find any IP provided in X-Forwarded-For header"
		raise web.HTTPBadRequest(text = ans)
	
	masked_ip = await bitmask_ip(request_ip, request.app['mask'])
	print(f"Got request from {masked_ip}")

	REDIS_SESSION = request.app['session_db']
	REDIS_TIMEOUT = request.app['timeout_db']

	current_timeout = REDIS_TIMEOUT.ttl(masked_ip)

	_body = request.app['html_body_429']
	_header = request.app['http_header']

	if current_timeout > -1:
		print(f"Seems like IP {masked_ip} is still timed out for {current_timeout}")
		_header['Retry-After'] = str(current_timeout)
		raise web.HTTPTooManyRequests(body = str(_body), headers = _header)

	elif masked_ip in REDIS_SESSION:
		if REDIS_SESSION.decrby(masked_ip, 1) < 0:
			print(f"{masked_ip} exceeded rate limit and got timeout...")
			REDIS_TIMEOUT.setex(masked_ip, request.app['timeout'], 1)

			# clear user session for case timeout ttl < session ttl
			del REDIS_SESSION[masked_ip]

			_header['Retry-After'] = str(request.app['timeout'])
			raise web.HTTPTooManyRequests(body = str(_body), headers = _header)
	else:
		print(f"New IP or last session expired")
		REDIS_SESSION.setex(masked_ip, 60, request.app['max_requests']-1)

	return await handler(request)

def initialize_app(port : int, mask : int, timeout : int, 
	max_requests : int, redis_session_db : int, redis_timeout_db : int):
	
	app = web.Application(middlewares = [ip_checkpoint])
	app.add_routes([web.route('*', '/foo', content_handler),
				web.route('*', '/bar', content_handler),
				web.route('*', '/content', content_handler)])
	app.add_routes([web.get('/reset_timeout', reset_timeout_handler)])

	# main settings
	app['port'] = port

	# store mask as list of integers ex. [255, 255, 255, 0]
	tmp_s = bin((1<<32) - (1<<32>>mask))[2:]
	app['mask'] = [int(i, 2) for i in [tmp_s[8*j:8*(j+1)] for j in range(4)]]

	app['timeout'] = timeout
	app['max_requests'] = max_requests
	app['session_db'] = redis.Redis(db = redis_session_db)
	app['timeout_db'] = redis.Redis(db = redis_timeout_db)

	# static utils
	app['html_body_200'] = responses.HTMLResponse200()
	app['html_body_429'] = responses.HTMLResponse429(max_requests)
	app['http_header'] = CIMultiDict()
	app['http_header']['Content-Type'] = 'text/html'
	app['secret_key'] = 'secret_key'

	return app

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-p', '--port', type=int, default=8080)
	parser.add_argument('-m', '--mask', type=int, default=24)
	parser.add_argument('-t', '--timeout', type=int, default=120)
	parser.add_argument('-r', '--requests', type=int, default=100)
	svc_settings = parser.parse_args()
	
	# we will use 1st and 2nd redis db for 'production'
	app = initialize_app(*(vars(svc_settings).values()), 1, 2)

	web.run_app(app, port = app['port'])
