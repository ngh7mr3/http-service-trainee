#!/usr/bin/env python3
from aiohttp import web
import asyncio
import argparse
import redis

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--port', type=int, default=8080)
parser.add_argument('-m', '--mask', type=int, default=24)
parser.add_argument('-t', '--timeout', type=int, default=120)
parser.add_argument('-r', '--requests', type=int, default=100)
service_settings = parser.parse_args()

tmp_s = bin((2**32-1) & ~(2**(32-service_settings.mask)-1))[2:]
SERVICE_PORT = service_settings.port
SERVICE_MASK = [int(i, 2) for i in [tmp_s[8*j:8*(j+1)] for j in range(4)]]
SERVICE_TIMEOUT = service_settings.timeout
REQUESTS_PER_MIN = service_settings.requests

# using default redis-server at localhost:6379
REDIS_SESSION = redis.Redis(db=1) 
REDIS_TIMEOUT = redis.Redis(db=2)

# TODO:
# - create RFC 429 HTTP answer with html body
# - add handler to clear timeout for specifix prefix
# - add tests (pytest-aiohttp)
# - add docker (?)

async def bitmask_ip(ip: str) -> str:
	ip_bytes = map(int, ip.split('.'))
	raw_bytes = [str(i&j) for i,j in zip(ip_bytes, SERVICE_MASK)]
	return '.'.join(raw_bytes)

async def process_ip(ip: str):
	masked_ip = await bitmask_ip(ip)
	print(f"Got request from {masked_ip}")

	if masked_ip in REDIS_TIMEOUT:
		print(f"Seems like IP {masked_ip} is timed out")
		return web.HTTPTooManyRequests()
	elif masked_ip in REDIS_SESSION:
		if REDIS_SESSION.decrby(masked_ip, 1) < 0:
			print(f"{masked_ip} exceeded rate limit and got timeout...")
			REDIS_TIMEOUT.setex(masked_ip, SERVICE_TIMEOUT, 1)
			return web.HTTPTooManyRequests()
		else:
			print(f"Everything is ok with {masked_ip}, processing request...")
			return web.HTTPOk()
	else:
		print(f"New IP or last session expired")
		REDIS_SESSION.setex(masked_ip, 60, REQUESTS_PER_MIN-1)
		return web.HTTPOk()

async def handler(request):
	try:
		request_ip = request._message.headers['X-Forwarded-For']
	except KeyError:
		print("Got header without forwarded ip")
		request_ip = '0.0.0.0'

	return await process_ip(request_ip)

async def main():
	server = web.Server(handler)
	runner = web.ServerRunner(server)
	await runner.setup()

	site = web.TCPSite(runner, '127.0.0.1', SERVICE_PORT)
	await site.start()

	print(f"===== SERVING on http://127.0.0.1:{SERVICE_PORT}/ =====")
	await asyncio.sleep(100*3600)

if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	try:
		loop.run_until_complete(main())
	except KeyboardInterrupt:
		pass
	loop.close()
