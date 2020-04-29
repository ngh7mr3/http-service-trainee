#!/usr/bin/env python3
from aiohttp import web
import asyncio
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--port', type=int, default=8080)
parser.add_argument('-m', '--mask', type=int, default=24)
parser.add_argument('-t', '--timeout', type=int, default=120)
app_settings = parser.parse_args()

# TODO:
# - add async handler for db
# - add handler to clear timeout for specifix prefix
# - add tests (pytest-aiohttp)

async def handler(request):
	#request_ip = request._message.headers['X-Forwarded-For']
	#print(request._message.headers)
	#print(request_ip)
	return web.Response(text="OK")

async def main():
	server = web.Server(handler)
	runner = web.ServerRunner(server)
	await runner.setup()
	site = web.TCPSite(runner, '0.0.0.0', app_settings.port)
	await site.start()
	print(f"===== SERVING on http://0.0.0.0:{app_settings.port}/ =====")
	await asyncio.sleep(100*3600)

if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	try:
		loop.run_until_complete(main())
	except KeyboardInterrupt:
		pass
	loop.close()
