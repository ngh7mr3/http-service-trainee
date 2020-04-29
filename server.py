#!/usr/bin/env python3
from aiohttp import web

routes = web.RouteTableDef()

@routes.get('/')
async def handler(request):
	print(request)
	return web.Response(text='test')

app = web.Application()
app.add_routes(routes)
web.run_app(app)
