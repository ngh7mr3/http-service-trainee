import pytest
import pytest_aiohttp
import server
import redis
from aiohttp import web

# Testing only default behaviour of the server
# Rate limit = 100 requests per minute
# Timeout = 120 seconds
# Subnet prefix = 255.255.255.0

# We will use another dbs, instead of 'production' db=1 and db=2
# Let's reassign them in the server module and create new handle
REDIS_SESSION = redis.Redis(db=3)
REDIS_TIMEOUT = redis.Redis(db=4)
server.REDIS_SESSION = REDIS_SESSION
server.REDIS_TIMEOUT = REDIS_TIMEOUT

@pytest.fixture
async def cli(aiohttp_client, aiohttp_raw_server):
	app = await aiohttp_raw_server(server.handler)
	client = await aiohttp_client(app)
	return client

async def flush_db():
	REDIS_SESSION.flushdb()
	REDIS_TIMEOUT.flushdb()

async def test_without_provided_header(cli):
	resp = await cli.get('/')
	assert resp.status == 400
	
	resp = await cli.get('/foo')
	assert resp.status == 400
	
	resp = await cli.get('/asd')
	assert resp.status == 400

async def test_with_invalid_header(cli):
	header = {'X-Forwarded-For': 'asd'}

	resp = await cli.get('/', headers = header)
	assert resp.status == 400

	resp = await cli.get('/foo', headers = header)
	assert resp.status == 400

	resp = await cli.get('/asd', headers = header)
	assert resp.status == 400

async def test_with_valid_header(cli):
	ip = '1.2.3.4'
	masked_ip = await server.bitmask_ip(ip)
	header = {'X-Forwarded-For': ip}

	resp = await cli.get('/', headers = header)
	assert resp.status == 404
	assert masked_ip in REDIS_SESSION
	
	resp = await cli.get('/foo', headers = header)
	assert resp.status == 200
	assert masked_ip not in REDIS_TIMEOUT

	resp = await cli.get('/asd', headers = header)
	assert resp.status == 404
	assert masked_ip not in REDIS_TIMEOUT

	await flush_db()

async def test_ips_from_different_subnets(cli):
	ips = ['1.1.1.1', '1.1.2.1', '1.2.1.1', '2.1.1.1']
	masked_ips = [await server.bitmask_ip(ip) for ip in ips]
	
	ok_url_pack = server.PATHS
	not_found_url_pack = ['/', '/test', '/admin']
	packs = [(200, ok_url_pack), (404, not_found_url_pack)]
	
	for ip, masked_ip in zip(ips, masked_ips):
		for code, url_pack in packs:
			for url in url_pack:
				#ok, this looks terrible, I know
				resp = await cli.get(url, headers = {'X-Forwarded-For' : ip})
				assert resp.status == code
		# after getting 3 200s and 3 404s
		# ip from current subnet should be able
		# to create 100 - 6 = 94 requests
		assert int(REDIS_SESSION.get(masked_ip)) == 94

	await flush_db()


