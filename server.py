#!/usr/bin/env python3
from aiohttp import web
import asyncio
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--port', type=int, default=8080)
app_settings = parser.parse_args()

async def handler(request):
	return web.Response(text="OK")

async def main(loop):
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
		loop.run_until_complete(main(loop))
	except KeyboardInterrupt:
		pass
	loop.close()
