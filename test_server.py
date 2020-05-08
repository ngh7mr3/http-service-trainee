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
REDIS_SESSION = 0
REDIS_TIMEOUT = 0
PATHS = ["/foo", "/bar", "/content"]

# main service settings: port, mask, timeout, max_requests
svc_settings = [8080, 24, 120, 100]
mask = [255, 255, 255, 0]


async def flush_db():
    REDIS_SESSION.flushdb()
    REDIS_TIMEOUT.flushdb()


@pytest.fixture
async def cli(aiohttp_client):
    global REDIS_SESSION, REDIS_TIMEOUT
    app = server.initialize_app(*svc_settings, 3, 4)
    REDIS_SESSION = app["session_db"]
    REDIS_TIMEOUT = app["timeout_db"]
    await flush_db()
    return await aiohttp_client(app)


async def test_without_provided_header(cli):
    resp = await cli.get("/")
    assert resp.status == 400

    resp = await cli.get("/foo")
    assert resp.status == 400

    resp = await cli.get("/asd")
    assert resp.status == 400


async def test_with_invalid_header(cli):
    header = {"X-Forwarded-For": "asd"}

    resp = await cli.get("/", headers=header)
    assert resp.status == 400

    resp = await cli.get("/foo", headers=header)
    assert resp.status == 400

    resp = await cli.get("/asd", headers=header)
    assert resp.status == 400


async def test_with_valid_header(cli):
    ip = [1, 2, 3, 4]
    masked_ip = await server.bitmask_ip(ip, mask)
    header = {"X-Forwarded-For": "1.2.3.4"}

    resp = await cli.get("/", headers=header)
    assert resp.status == 404
    assert masked_ip in REDIS_SESSION

    resp = await cli.get("/foo", headers=header)
    assert resp.status == 200
    assert masked_ip not in REDIS_TIMEOUT

    resp = await cli.get("/asd", headers=header)
    assert resp.status == 404
    assert masked_ip not in REDIS_TIMEOUT


async def test_ips_from_different_subnets(cli):
    ips = [[1, 1, 1, 1], [1, 1, 2, 1], [1, 2, 1, 1], [2, 1, 1, 1]]
    masked_ips = [await server.bitmask_ip(ip, mask) for ip in ips]

    ok_url_pack = PATHS
    not_found_url_pack = ["/", "/test", "/admin"]
    packs = [(200, ok_url_pack), (404, not_found_url_pack)]

    for ip, masked_ip in zip(ips, masked_ips):
        _ip = ".".join(map(str, ip))
        for code, url_pack in packs:
            for url in url_pack:
                # ok, this looks terrible, I know
                resp = await cli.get(url, headers={"X-Forwarded-For": _ip})
                assert resp.status == code
        # after getting 3 200s and 3 404s
        # ip from current subnet should be able
        # to create 100 - 6 = 94 requests
        assert int(REDIS_SESSION.get(masked_ip)) == 94


async def test_ips_from_one_subnet(cli):
    # testing for default subnet mask 255.255.255.0
    ips = ["1.2.3.100", "1.2.3.255", "1.2.3.0", "1.2.3.4"]
    masked_ip = "1.2.3.0"

    ok_url_pack = PATHS
    not_found_pack = ["/", "/set", "test"]
    packs = [(200, ok_url_pack), (404, not_found_pack)]

    for ip in ips:
        for code, url_pack in packs:
            for url in url_pack:
                resp = await cli.get(url, headers={"X-Forwarded-For": ip})
                assert resp.status == code

    # after 24 requests from subnet 1.2.3.0
    # we should be able to make 100-24=76 requests
    assert int(REDIS_SESSION.get(masked_ip)) == 76


async def test_timeout_for_one_ip(cli):
    ip = "1.2.3.4"
    url = "/foo"

    # processing 100+ requests under 1 minute
    # to get a timeout from the server

    for _ in range(100):
        resp = await cli.get(url, headers={"X-Forwarded-For": ip})
        assert resp.status == 200

    # after 101st request we should get timeout for 120 seconds
    resp = await cli.get(url, headers={"X-Forwarded-For": ip})
    assert resp.status == 429
    assert resp._headers["Retry-After"] == str(cli.server.app["timeout"])


async def test_timeout_for_one_subnet(cli):
    ips = ["1.2.3.100", "1.2.3.255", "1.2.3.0", "1.2.3.4"]
    masked_ip = "1.2.3.0"
    url = "/foo"

    # processing 25 requests for each ip
    # then test 1 request for each ip (requests: 101, 102, 103 and 104)
    # they should be timed out with 429 answer
    for ip in ips:
        for _ in range(25):
            resp = await cli.get(url, headers={"X-Forwarded-For": ip})
            assert resp.status == 200

    # make sure all ips will get timeout after extra requests
    for ip in ips:
        resp = await cli.get(url, headers={"X-Forwarded-For": ip})
        assert resp.status == 429


async def test_timeout_for_mixed_subnets(cli):
    subnets = [["1.2.3.1", "1.2.3.2"], ["9.8.7.1", "9.8.7.2"]]
    masked_ips = ["1.2.3.0", "9.8.7.0"]
    url = "/foo"

    for _ in range(50):
        for subnet in subnets:
            for ip in subnet:
                resp = await cli.get(url, headers={"X-Forwarded-For": ip})
                assert resp.status == 200

    # we've made 100 requests from each subnet
    for ip in masked_ips:
        assert ip in REDIS_SESSION and ip not in REDIS_TIMEOUT

    # let's make extra request from second subnet
    resp = await cli.get(url, headers={"X-Forwarded-For": subnets[1][0]})
    assert resp.status == 429
    assert masked_ips[1] in REDIS_TIMEOUT


async def test_timeout_reset_query(cli):
    header = {"X-Forwarded-For": "1.2.3.4"}
    url = "/reset_timeout"
    key = cli.server.app["secret_key"]
    bad_key = "bad_key"
    subnet = "1.1.1.1"
    bad_subnet = "1.a.asd.0001"

    # provide only key
    resp = await cli.get(f"{url}?key={key}", headers=header)
    assert resp.status == 400

    # provide only subnet
    resp = await cli.get(f"{url}?ip={subnet}", headers=header)
    assert resp.status == 400

    # provide bad key
    resp = await cli.get(f"{url}?key={bad_key}&ip={subnet}", headers=header)
    assert resp.status == 400

    # provide bad subnet
    resp = await cli.get(f"{url}?key={key}&ip={bad_subnet}", headers=header)
    assert resp.status == 400

    # provide valid key and subnet
    # but provided prefix isn't timed out
    resp = await cli.get(f"{url}?key={key}&ip={subnet}", headers=header)
    assert resp.status == 400

    # timeout given subnet
    REDIS_TIMEOUT.setex("1.1.1.0", cli.server.app["timeout"], 1)
    # trying to request something
    resp = await cli.get("/", headers={"X-Forwarded-For": subnet})
    assert resp.status == 429

    resp = await cli.get(f"{url}?key={key}&ip={subnet}", headers=header)
    assert resp.status == 200

    # trying to request after resetting timeout
    resp = await cli.get("/foo", headers={"X-Forwarded-For": subnet})
    assert resp.status == 200
