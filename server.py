#!/usr/bin/env python3
from aiohttp import web
from multidict import CIMultiDict
import asyncio
import argparse
import redis
import responses

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--port', type=int, default=8080)
parser.add_argument('-m', '--mask', type=int, default=24)
parser.add_argument('-t', '--timeout', type=int, default=120)
parser.add_argument('-r', '--requests', type=int, default=100)
service_settings = parser.parse_args()

# main service settings
tmp_s = bin((2**32-1) & ~(2**(32-service_settings.mask)-1))[2:]
SERVICE_IP = '127.0.0.1'
SERVICE_PORT = service_settings.port
SERVICE_MASK = [int(i, 2) for i in [tmp_s[8*j:8*(j+1)] for j in range(4)]]
SERVICE_TIMEOUT = service_settings.timeout
MAX_REQUESTS= service_settings.requests
SECRET_KEY = 'foobar' # hardcoded keys aren't the best practice

# using default redis-server at localhost:6379
REDIS_SESSION = redis.Redis(db=1) 
REDIS_TIMEOUT = redis.Redis(db=2)

PATHS = ['/foo', '/bar', '/foobar']
HTMLBody200 = responses.HTMLResponse200()
HTMLBody404 = responses.HTMLResponse404()
HTMLBody429 = responses.HTMLResponse429(MAX_REQUESTS)
HTTPHeader429 = CIMultiDict()
HTTPHeader429['Content-Type'] = 'text/html'

async def bitmask_ip(ip: str) -> str:
	ip_bytes = map(int, ip.split('.'))
	raw_bytes = [str(i&j) for i,j in zip(ip_bytes, SERVICE_MASK)]
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

	return True

async def process_request(request: web.BaseRequest, ip: str):
	masked_ip = await bitmask_ip(ip)
	print(f"Got request from {masked_ip}")

	current_timeout = REDIS_TIMEOUT.ttl(masked_ip)

	if current_timeout > -1:
		print(f"Seems like IP {masked_ip} is still timed out for {current_timeout}")
		HTTPHeader429['Retry-After'] = str(current_timeout)
		return web.HTTPTooManyRequests(body = str(HTMLBody429), 
									headers = HTTPHeader429)
	elif masked_ip in REDIS_SESSION:
		if REDIS_SESSION.decrby(masked_ip, 1) < 0:
			print(f"{masked_ip} exceeded rate limit and got timeout...")
			REDIS_TIMEOUT.setex(masked_ip, SERVICE_TIMEOUT, 1)

			# clear user session for case timeout ttl < session ttl
			del REDIS_SESSION[masked_ip]

			HTTPHeader429['Retry-After'] = str(SERVICE_TIMEOUT)
			return web.HTTPTooManyRequests(body = str(HTMLBody429), 
										headers = HTTPHeader429)
		else:
			print(f"Everything is ok with {masked_ip}, processing request...")
	else:
		print(f"New IP or last session expired")
		REDIS_SESSION.setex(masked_ip, 60, MAX_REQUESTS-1)

	if request.path in PATHS:
		# here should be route hadler aka RouteDef
		return web.HTTPOk(body = str(HTMLBody200), content_type = 'text/html')
	elif request.path == '/reset-timeout':
		try:
			key = request.query['key']
			subnet_prefix = request.query['ip']
		except KeyError:
			raise web.HTTPBadRequest(text = "Provide subnet prefix "
											"(or ip from specific subnet) "
											"and secret key to reset timeout. "
											"Ex.: /reset-timeout?key=foo&ip=1.2.3.4")
		if key != SECRET_KEY:
			raise web.HTTPBadRequest(text = "Unauthorized")

		# validating given prefix/ip
		if not await validate_ip(subnet_prefix):
			raise web.HTTPBadRequest(text = "You should provide valid prefix/ip")

		# got valid prefix and valid secret key
		masked_prefix = await bitmask_ip(subnet_prefix)
		if masked_prefix in REDIS_TIMEOUT:
			del REDIS_TIMEOUT[masked_prefix]
			return web.HTTPOk(body = str(HTMLBody200), content_type = 'text/html')
		else:
			raise web.HTTPBadRequest(text = "Provided prefix isn't timed out")
	else:
		raise web.HTTPNotFound(body = str(HTMLBody404), content_type = 'text/html')

async def handler(request):
	try:
		# processing cases when there's only 1 address provided
		request_ip = request.headers['X-Forwarded-For']
		if not await validate_ip(request_ip):
			raise web.HTTPBadRequest(text = "Bad ip provided in header")
	except KeyError:
		print("Got header without forwarded ip")
		ans = "Can't find any IP provided in X-Forwarded-For header"
		raise web.HTTPBadRequest(text = ans)

	return await process_request(request, request_ip)

async def main():
	server = web.Server(handler)
	runner = web.ServerRunner(server)
	await runner.setup()
	
	site = web.TCPSite(runner, SERVICE_IP, SERVICE_PORT)
	await site.start()

	print(f"===== SERVING on http://{SERVICE_IP}:{SERVICE_PORT}/ =====")
	await asyncio.sleep(100*3600)

if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	try:
		loop.run_until_complete(main())
	except KeyboardInterrupt:
		pass
	loop.close()
