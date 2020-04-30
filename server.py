#!/usr/bin/env python3
from aiohttp import web
import asyncio
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--port', type=int, default=8080)
parser.add_argument('-m', '--mask', type=int, default=24)
parser.add_argument('-t', '--timeout', type=int, default=120)
service_settings = parser.parse_args()

tmp_s = bin((2**32-1) & ~(2**(32-service_settings.mask)-1))[2:]
SERVICE_PORT = service_settings.port
SERVICE_MASK = [int(i, 2) for i in [tmp_s[8*j:8*(j+1)] for j in range(4)]]
SERVICE_TIMEOUT = service_settings.timeout

# TODO:
# - add async handler for db
#	Redis seeems to be the best practice, so let's use async python wrapper for it
# - add handler to clear timeout for specifix prefix
# - add tests (pytest-aiohttp)
# - add docker (?)

async def bitmask_ip(ip: str) -> str:
	ip_bytes = map(int, ip.split('.'))
	raw_bytes = [str(i&j) for i,j in zip(ip_bytes, SERVICE_MASK)]
	return '.'.join(raw_bytes)

async def handler(request):
	# assume ip provided with every request
	request_ip = request._message.headers['X-Forwarded-For']
	masked_ip = await bitmask_ip(request_ip)
	print(request._message.headers)
	print(f"Header IP: {request_ip}, Masked IP: {masked_ip}")
	return web.Response(text="OK")

async def main():
	server = web.Server(handler)
	runner = web.ServerRunner(server)
	await runner.setup()

	site = web.TCPSite(runner, '0.0.0.0', SERVICE_PORT)
	await site.start()

	print(f"===== SERVING on http://0.0.0.0:{SERVICE_PORT}/ =====")
	await asyncio.sleep(100*3600)

if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	try:
		loop.run_until_complete(main())
	except KeyboardInterrupt:
		pass
	loop.close()
