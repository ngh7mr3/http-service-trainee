## Task

Create an HTTP-service which can rate limit requests from one IPv4 subnet.
Service should provide any static content without limiting.

### Requirements

- Language - Python or Go
- RFC 6585 service answer
- IP should be extracted from X-Forwarded-For header
- Subnet - /24 (mask 255.255.255.0)
- Rate limit - 100 requests per minute
- Timeout after limiting - 2 minutes

### Bonus

- Test coverage
- Start up the service by 'docker-compose up'
- Include subnet size, rate limit and timeout at service start
- Handler for manual resetting any limits by subnet prefix

## Setup
Firstly, you need to install aiohttp modules. This could be done with pip
```Bash
pip3 install aiohttp
pip3 install pytest-aiohttp
```
Note: pytest-aiohttp isn't compatible with pytest-asyncio. Use at your own risk.

This service will use Redis DB to process rate limiting logic. Installation could be done with command:
```Bash
apt-get install redis-server
```
After complete installation, make sure redis-server is running as a service
```Bash
systemctl status redis-server
```
Installation is over.

## Usage
You can simply start up service with:
```Bash
./server.py
```
You can setup service with custom parameters, for example:
```Bash
./server.py -p 8081 -t 180 -r 20 -m 22
```
This line of code will start a service on port 8081.
Timeout, rate limit (per minute) and mask will be set at: 180 seconds, 20 requests and 22 bit.
See `./server.py -h` for more details.

## Done

- Implemented raw aiohttp server with Redis
- Created basic logic for rate limiting
- Added possibility to include subnet size, rate limit, port and timeout at service start
- Created primitive handler to reset any limiting by subnet prefix
- Covered service code with small tests with pytest-aiohttp

## TODO

- Start up service with 'docker-compose up'
- Style all code in PEP 8
- Add custom route handler aka RouteDef with aiohttp.web.Application
- Reimplement timeout reset handler: providing secret keys in plain text isn't safe enough (use cookies or something else?)
- Create separate class for internal service settings (using global variables isn't best practice)

